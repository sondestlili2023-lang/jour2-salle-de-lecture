"""Les deux montages de l'acte 2 : le lineaire du service statistique, et le notre.

Definis une seule fois ici et reutilises par les phases 2 a 7, pour que
"le montage de la phase 3" reste litteralement le meme objet partout
(la phase 4 le casse, la phase 5 le rend plus rapide, la phase 6 et la
phase 7 le modifient explicitement et le disent).
"""
import torch
import torch.nn as nn


class ModeleLineaire(nn.Module):
    """Le modele du service statistique : un comptage de mots, une seule couche lineaire."""

    def __init__(self, taille_vocab, n_classes):
        super().__init__()
        self.lineaire = nn.Linear(taille_vocab, n_classes)

    def forward(self, sac_de_mots):
        return self.lineaire(sac_de_mots)


class ModeleConv(nn.Module):
    """Embedding -> une couche de convolution 1D -> BatchNorm -> ReLU -> max-pool global -> lineaire.

    Recoit une sequence d'identifiants de mots (batch, longueur), pas un
    sac-de-mots : la convolution voit l'ordre local des mots (fenetre de
    `noyau` mots), ce qu'un comptage ne voit jamais.
    """

    def __init__(self, taille_vocab, n_classes, dim_embed=100, dim_cachee=128, noyau=3, dropout=0.4):
        super().__init__()
        self.embed = nn.Embedding(taille_vocab, dim_embed, padding_idx=0)
        self.conv = nn.Conv1d(dim_embed, dim_cachee, kernel_size=noyau, padding=noyau // 2)
        self.norme = nn.BatchNorm1d(dim_cachee)
        self.dropout = nn.Dropout(dropout)
        # max-pool ET moyenne-pool concatenes : le max retient le mot le plus
        # saillant, la moyenne retient le ton general de la phrase.
        self.sortie = nn.Linear(dim_cachee * 2, n_classes)

    def forward(self, sequences):
        x = self.embed(sequences)  # (batch, longueur, dim_embed)
        x = x.transpose(1, 2)  # (batch, dim_embed, longueur)
        x = self.conv(x)  # (batch, dim_cachee, longueur)
        x = self.norme(x)
        x = torch.relu(x)
        x_max, _ = x.max(dim=2)
        x_moy = x.mean(dim=2)
        x = torch.cat([x_max, x_moy], dim=1)
        x = self.dropout(x)
        return self.sortie(x)


class BlocDilate(nn.Module):
    """Une couche de convolution dilatee CAUSALE, avec ou sans raccourci residuel.

    Le padding n'est ajoute qu'a gauche (F.pad, pas le padding symetrique
    de nn.Conv1d) : la sortie a la position p ne depend que des positions
    <= p. Avec un padding symetrique, la derniere position d'un relevé ne
    "voit" a gauche que la moitie du champ de vision cumule -- l'autre
    moitie part dans le vide a droite, au-dela de la fin du relevé. Le
    padding causal fait pointer tout le champ de vision cumule vers
    l'arriere, la ou se trouvent les mots a voir.
    """

    def __init__(self, dim, dilation, noyau=3, residuel=True):
        super().__init__()
        self.pad_gauche = (noyau - 1) * dilation
        self.conv = nn.Conv1d(dim, dim, kernel_size=noyau, dilation=dilation)
        self.norme = nn.BatchNorm1d(dim)
        self.residuel = residuel

    def forward(self, x):
        x_pad = nn.functional.pad(x, (self.pad_gauche, 0))
        y = torch.relu(self.norme(self.conv(x_pad)))
        return x + y if self.residuel else y


class ModeleTCN(nn.Module):
    """Embedding -> pile de convolutions dilatees (champ de vision cumule
    couvrant tout le relevé le plus long) -> max+moyenne-pool -> lineaire.

    Aucune couche ne "lit mot apres mot en attendant le precedent" : toutes
    les positions d'une couche sont calculees de front (comme ModeleConv),
    seule la profondeur de la pile fait grandir ce qu'une position finit
    par "voir" du reste du relevé.
    """

    def __init__(self, taille_vocab, n_classes, dim_embed=100, dim_cachee=128, dilations=(1, 2, 4, 8, 16),
                 dropout=0.4, residuel=True):
        super().__init__()
        self.embed = nn.Embedding(taille_vocab, dim_embed, padding_idx=0)
        self.projection = nn.Conv1d(dim_embed, dim_cachee, kernel_size=1)
        self.couches = nn.ModuleList([BlocDilate(dim_cachee, d, residuel=residuel) for d in dilations])
        self.dropout = nn.Dropout(dropout)
        self.sortie = nn.Linear(dim_cachee * 2, n_classes)

    def forward(self, sequences):
        x = self.embed(sequences).transpose(1, 2)  # (batch, dim_embed, longueur)
        x = self.projection(x)  # (batch, dim_cachee, longueur)
        for couche in self.couches:
            x = couche(x)
        x_max, _ = x.max(dim=2)
        x_moy = x.mean(dim=2)
        x = torch.cat([x_max, x_moy], dim=1)
        x = self.dropout(x)
        return self.sortie(x)

    def champ_de_vision_cumule(self, noyau=3):
        """Table couche par couche : ce que chaque couche ajoute au champ de
        vision d'une position de sortie, et le total cumule."""
        total = 1  # la projection 1x1 ne fait pas grandir le champ de vision
        table = []
        for couche in self.couches:
            dilation = couche.conv.dilation[0]
            ajout = (noyau - 1) * dilation
            total += ajout
            table.append((dilation, ajout, total))
        return table
