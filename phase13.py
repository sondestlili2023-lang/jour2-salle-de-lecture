"""Phase 13 : deux regards sur le même relevé.

Deux tetes d'attention (phase10.UneTeteAttention, inchangee) tournent en
parallele sur le meme relevé (memes entrees, position incluse -- phase
11), avec des poids Q/K/V initialises differemment. Leurs sorties sont
recollees (concatenation + une couche lineaire de projection). On mesure
si elles regardent vraiment autre chose, avec un cas de controle (deux
tetes qui partent identiques) pour donner un sens au chiffre.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn

from commun import RACINE
from formes import tokeniser
from phase10 import DIM, RELEVE, UneTeteAttention
from phase11 import construire_table_mots, entrees_avec_position

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
GRAINE = 42


def nouvelle_tete(graine):
    torch.manual_seed(graine)
    tete = UneTeteAttention(DIM)
    for p in tete.parameters():
        nn.init.normal_(p, std=0.5)
    return tete


def distance_tv(poids_a, poids_b):
    """Distance de variation totale, moyennee sur les lignes : pour chaque
    mot qui interroge, la moitie de la masse de probabilite qu'il faudrait
    deplacer pour passer d'une distribution d'attention a l'autre. Bornee
    entre 0 (identiques) et 1 (aucun recouvrement) -- lisible sans calcul
    supplementaire, contrairement a une simple moyenne de differences."""
    return (0.5 * (poids_a - poids_b).abs().sum(dim=1)).mean().item()


def afficher_cote_a_cote(poids_a, poids_b, mots, titres, chemin, suptitre):
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, poids, titre in zip(axes, [poids_a, poids_b], titres):
        n = len(mots)
        im = ax.imshow(poids, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(n)); ax.set_yticks(range(n))
        ax.set_xticklabels(mots, rotation=45, ha="right"); ax.set_yticklabels(mots)
        for i in range(n):
            for j in range(n):
                v = poids[i, j].item()
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                         color="white" if v > 0.5 else "black", fontsize=8)
        ax.set_title(titre)
    fig.suptitle(suptitre)
    fig.tight_layout()
    fig.savefig(chemin, dpi=150)


def main():
    mots = tokeniser(RELEVE)
    table, vocab = construire_table_mots(mots)
    torch.manual_seed(GRAINE + 2)
    table_position = nn.Embedding(len(mots), DIM)
    nn.init.normal_(table_position.weight, std=0.5)
    x = entrees_avec_position(mots, table, vocab, table_position)

    print("=== Phase 13 : deux regards sur le même relevé ===")
    print(f"Relevé : {mots}")

    # --- Deux tetes reellement differentes ---------------------------------
    tete_1 = nouvelle_tete(GRAINE + 10)
    tete_2 = nouvelle_tete(GRAINE + 20)
    sortie_1, poids_1 = tete_1(x)
    sortie_2, poids_2 = tete_2(x)

    projection = nn.Linear(2 * DIM, DIM)
    torch.manual_seed(GRAINE + 30)
    nn.init.normal_(projection.weight, std=0.3)
    sortie_recollee = projection(torch.cat([sortie_1, sortie_2], dim=1))
    print(f"\nSortie tete 1 : {tuple(sortie_1.shape)}  |  Sortie tete 2 : {tuple(sortie_2.shape)}")
    print(f"Recollees (concatenation + projection lineaire) : {tuple(sortie_recollee.shape)} (== forme de l'entree)")

    desaccord = distance_tv(poids_1.detach(), poids_2.detach())
    print(f"\nDesaccord (distance de variation totale, moyenne sur les 6 mots) entre tete 1 et tete 2 : {desaccord:.4f}")

    # --- Cas de controle : deux tetes qui partent identiques ----------------
    tete_a = nouvelle_tete(GRAINE + 99)
    tete_b = nouvelle_tete(GRAINE + 99)  # meme graine -> memes poids
    _, poids_a = tete_a(x)
    _, poids_b = tete_b(x)
    desaccord_controle = distance_tv(poids_a.detach(), poids_b.detach())
    print(f"Desaccord du cas de controle (deux tetes identiques au depart) : {desaccord_controle:.6f}")

    print(f"\nLe controle est exactement 0 (deux tetes identiques, meme entree -> sorties identiques,")
    print(f"aucune division ne serait honnete ici) ; le desaccord reel ({desaccord:.4f}) est donc entierement")
    print(f"imputable a la difference d'initialisation entre tete 1 et tete 2, rien d'autre.")

    chemin = FIGURES_DIR / "phase13_deux_tetes.png"
    afficher_cote_a_cote(
        poids_1.detach(), poids_2.detach(), mots,
        [f"Tête 1", f"Tête 2"], chemin,
        f"Phase 13 -- deux têtes, même relevé (désaccord TV = {desaccord:.3f}, contrôle = {desaccord_controle:.3f})",
    )
    print(f"\nFigure enregistree : {chemin}")

    print("\nLes deux tetes ne sont pas entrainees : leurs differences viennent uniquement de leur")
    print("initialisation aleatoire, pas d'un quelconque apprentissage de deux relations differentes.")
    print("Entrainees, un desaccord de cette ampleur permettrait de conclure qu'elles se sont")
    print("specialisees sur des pistes distinctes (ex: l'une suit qui-fait-quoi, l'autre quelle")
    print("couleur va avec quel objet) -- ici, on ne peut conclure que sur la MECANIQUE : des tetes")
    print("differemment initialisees produisent des matrices differentes, le multi-tete a un effet reel.")


if __name__ == "__main__":
    main()
