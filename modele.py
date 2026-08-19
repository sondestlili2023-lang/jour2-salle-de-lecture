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

    def __init__(self, taille_vocab, n_classes, dim_embed=64, dim_cachee=128, noyau=3):
        super().__init__()
        self.embed = nn.Embedding(taille_vocab, dim_embed, padding_idx=0)
        self.conv = nn.Conv1d(dim_embed, dim_cachee, kernel_size=noyau, padding=noyau // 2)
        self.norme = nn.BatchNorm1d(dim_cachee)
        self.sortie = nn.Linear(dim_cachee, n_classes)

    def forward(self, sequences):
        x = self.embed(sequences)  # (batch, longueur, dim_embed)
        x = x.transpose(1, 2)  # (batch, dim_embed, longueur)
        x = self.conv(x)  # (batch, dim_cachee, longueur)
        x = self.norme(x)
        x = torch.relu(x)
        x, _ = x.max(dim=2)  # max-pool global sur la longueur -> (batch, dim_cachee)
        return self.sortie(x)
