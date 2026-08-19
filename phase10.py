"""Phase 10 : chaque mot interroge les autres.

Le mecanisme d'attention (une seule tete), code entierement a la main :
rien que des tenseurs, des produits matriciels, un softmax et des couches
lineaires. Aucun bloc "attention" tout pret, aucune bibliotheque de
modele preentraine.

Relevé de depart : un vrai relevé du fichier (indice 86260), choisi pour
sa reprise sans ambiguite -- "her" reprend "ship" (mother ship), un cas
d'ecole de pronom-antecedent.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn

from commun import RACINE
from formes import tokeniser

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
GRAINE = 42
DIM = 16  # dimension des vecteurs d'entree ET des vecteurs Q/K/V -- pour que
          # la sortie ait exactement la meme forme que l'entree.

RELEVE = "1 mother ship with her smaller ones"  # indice 86260 du fichier, shape=disk


def construire_entrees(mots):
    """Vecteurs d'entree : une table de correspondance mot -> vecteur (un
    nn.Embedding, l'equivalent d'une couche lineaire appliquee a un
    one-hot), initialisee au hasard -- rien n'est entraine ici."""
    torch.manual_seed(GRAINE)
    vocab = {m: i for i, m in enumerate(sorted(set(mots)))}
    table = nn.Embedding(len(vocab), DIM)
    ids = torch.tensor([vocab[m] for m in mots])
    return table(ids)  # (n_mots, DIM)


class UneTeteAttention(nn.Module):
    """Trois couches lineaires (question, etiquette, contenu), un produit
    matriciel pour les scores, un softmax, un second produit matriciel
    pour le melange. Rien d'autre."""

    def __init__(self, dim):
        super().__init__()
        self.vers_question = nn.Linear(dim, dim, bias=False)
        self.vers_etiquette = nn.Linear(dim, dim, bias=False)
        self.vers_contenu = nn.Linear(dim, dim, bias=False)
        self.dim = dim

    def forward(self, x):
        questions = self.vers_question(x)   # (n, dim)
        etiquettes = self.vers_etiquette(x)  # (n, dim)
        contenus = self.vers_contenu(x)      # (n, dim)

        scores = questions @ etiquettes.T / (self.dim ** 0.5)  # (n, n)
        poids = torch.softmax(scores, dim=-1)                  # (n, n), chaque ligne somme a 1
        sortie = poids @ contenus                              # (n, dim)
        return sortie, poids


def afficher_matrice(poids, mots, chemin, titre):
    n = len(mots)
    fig, ax = plt.subplots(figsize=(1.1 * n + 2, 1.1 * n + 1))
    im = ax.imshow(poids, cmap="Blues", vmin=0, vmax=poids.max().item())
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(mots, rotation=45, ha="right")
    ax.set_yticklabels(mots)
    ax.set_xlabel("mot regarde (etiquette / contenu)")
    ax.set_ylabel("mot qui interroge (question)")
    for i in range(n):
        for j in range(n):
            v = poids[i, j].item()
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                     color="white" if v > poids.max().item() / 2 else "black", fontsize=9)
    ax.set_title(titre)
    fig.colorbar(im, ax=ax, shrink=0.8, label="poids d'attention")
    fig.tight_layout()
    fig.savefig(chemin, dpi=150)


def main():
    mots = tokeniser(RELEVE)
    print("=== Phase 10 : chaque mot interroge les autres ===")
    print(f"Relevé (indice 86260, shape=disk) : \"{RELEVE}\"")
    print(f"Tokenise : {mots}")

    x = construire_entrees(mots)
    print(f"\nVecteurs d'entree : forme {tuple(x.shape)}")

    tete = UneTeteAttention(DIM)
    torch.manual_seed(GRAINE + 1)  # graine differente pour les poids de la tete, x deja fixe
    for p in tete.parameters():
        nn.init.normal_(p, std=0.5)
    sortie, poids = tete(x)

    print(f"Sortie de l'attention : forme {tuple(sortie.shape)} (== forme de l'entree : {tuple(x.shape) == tuple(sortie.shape)})")

    sommes = poids.sum(dim=1)
    print("\nSomme de chaque ligne de la matrice de poids (doit valoir 1) :")
    for m, s in zip(mots, sommes.tolist()):
        print(f"  {m:>10} : {s:.6f}")

    idx_her = mots.index("her")
    ligne_her = poids[idx_her]
    idx_max = ligne_her.argmax().item()
    print(f"\nLe pronom 'her' (position {idx_her}) s'appuie le plus sur le mot '{mots[idx_max]}' "
          f"(position {idx_max}, poids={ligne_her[idx_max].item():.4f}) -- ligne {idx_her}, colonne {idx_max} de la matrice.")
    print("(Le modele n'est pas entraine : cette valeur n'a aucune raison d'etre 'juste'. "
          "Ce qui compte ici, c'est de savoir OU regarder dans la matrice, pas ce qu'elle vaut.)")

    chemin = FIGURES_DIR / "phase10_attention.png"
    afficher_matrice(poids.detach(), mots, chemin,
                      "Phase 10 -- matrice d'attention (une tete, non entrainee)")
    print(f"\nFigure enregistree : {chemin}")


if __name__ == "__main__":
    main()
