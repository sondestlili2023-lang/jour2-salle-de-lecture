"""Phase 11 : le Conseil mélange vos mots.

Le mecanisme d'attention de la phase 10 ne regarde que le CONTENU des
mots (question/etiquette/contenu sont calcules a partir du seul vecteur
du mot) : rien dans son calcul ne depend de la position. Ce fichier le
prouve, chiffres a l'appui, puis corrige -- sans toucher au mecanisme
lui-meme -- en injectant un vecteur de position dans les entrees.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn

from commun import RACINE
from formes import tokeniser
from phase10 import DIM, GRAINE, RELEVE, UneTeteAttention, afficher_matrice

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)


def construire_table_mots(mots):
    torch.manual_seed(GRAINE)
    vocab = {m: i for i, m in enumerate(sorted(set(mots)))}
    return nn.Embedding(len(vocab), DIM), vocab


def entrees_sans_position(mots, table, vocab):
    ids = torch.tensor([vocab[m] for m in mots])
    return table(ids)


def entrees_avec_position(mots, table, vocab, table_position):
    ids = torch.tensor([vocab[m] for m in mots])
    positions = torch.arange(len(mots))
    return table(ids) + table_position(positions)


def nouvelle_tete():
    torch.manual_seed(GRAINE + 1)
    tete = UneTeteAttention(DIM)
    for p in tete.parameters():
        nn.init.normal_(p, std=0.5)
    return tete


def ecart_par_mot(sortie_a, mots_a, sortie_b, mots_b):
    """Compare la sortie de chaque MOT (par identite, pas par position) entre
    deux ordres differents de la meme phrase."""
    ecarts = []
    for i, m in enumerate(mots_a):
        j = mots_b.index(m)
        ecarts.append((sortie_a[i] - sortie_b[j]).abs().max().item())
    return max(ecarts), ecarts


def main():
    torch.manual_seed(0)
    mots = tokeniser(RELEVE)
    permutation = torch.randperm(len(mots)).tolist()
    mots_melanges = [mots[i] for i in permutation]

    print("=== Phase 11 : le Conseil mélange vos mots ===")
    print(f"Phrase correcte  : {mots}")
    print(f"Phrase melangee  : {mots_melanges}")

    table, vocab = construire_table_mots(mots)
    tete = nouvelle_tete()

    # --- AVANT correction : pas de position ---------------------------------
    x_correct = entrees_sans_position(mots, table, vocab)
    x_melange = entrees_sans_position(mots_melanges, table, vocab)
    sortie_correcte, poids_correcte = tete(x_correct)
    sortie_melangee, poids_melangee = tete(x_melange)
    sortie_correcte, sortie_melangee = sortie_correcte.detach(), sortie_melangee.detach()

    ecart_max_avant, detail_avant = ecart_par_mot(sortie_correcte, mots, sortie_melangee, mots_melanges)
    print("\n[AVANT correction -- pas d'information de position]")
    print("Ecart (valeur absolue max) entre la sortie de chaque mot, ordre correct vs melange :")
    for m, e in zip(mots, detail_avant):
        print(f"  {m:>10} : {e:.8f}")
    print(f"Ecart maximal sur les 6 mots : {ecart_max_avant:.8f}  (attendu : ~0)")

    # --- APRES correction : position injectee dans les ENTREES --------------
    torch.manual_seed(GRAINE + 2)
    table_position = nn.Embedding(len(mots), DIM)
    nn.init.normal_(table_position.weight, std=0.5)

    x_correct_pos = entrees_avec_position(mots, table, vocab, table_position)
    x_melange_pos = entrees_avec_position(mots_melanges, table, vocab, table_position)
    sortie_correcte_pos, poids_correcte_pos = tete(x_correct_pos)  # MEME tete, non modifiee
    sortie_melangee_pos, poids_melangee_pos = tete(x_melange_pos)
    sortie_correcte_pos, sortie_melangee_pos = sortie_correcte_pos.detach(), sortie_melangee_pos.detach()

    ecart_max_apres, detail_apres = ecart_par_mot(sortie_correcte_pos, mots, sortie_melangee_pos, mots_melanges)
    print("\n[APRES correction -- position ajoutee au vecteur d'entree, tete inchangee]")
    for m, e in zip(mots, detail_apres):
        print(f"  {m:>10} : {e:.8f}")
    print(f"Ecart maximal sur les 6 mots : {ecart_max_apres:.8f}  (attendu : nettement non nul)")

    print(f"\nRESUME -- ecart avant : {ecart_max_avant:.8f}   ecart apres : {ecart_max_apres:.8f}   "
          f"(x{ecart_max_apres/max(ecart_max_avant,1e-12):.0f})")

    # --- Figures : matrices avant / apres, meme phrase (ordre correct) ------
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, poids, titre in [
        (axes[0], poids_correcte.detach(), "Avant -- sans position"),
        (axes[1], poids_correcte_pos.detach(), "Après -- avec position"),
    ]:
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
    fig.suptitle("Phase 11 -- meme phrase (ordre correct), avant/après injection de position")
    fig.tight_layout()
    chemin = FIGURES_DIR / "phase11_avant_apres.png"
    fig.savefig(chemin, dpi=150)
    print(f"\nFigure enregistree : {chemin}")


if __name__ == "__main__":
    main()
