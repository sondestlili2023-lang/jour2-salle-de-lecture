"""Phase 12 : le Conseil demande la facture.

Chronometre la tete d'attention de la phase 11 (code inchange) sur des
sequences synthetiques de 32, 64, 128, 256 et 512 jetons. Peu importe le
contenu des jetons ici : seule leur nombre compte pour une mesure de
cout de calcul.
"""
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch

from commun import RACINE
from phase10 import DIM, UneTeteAttention

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
GRAINE = 42
LONGUEURS = [32, 64, 128, 256, 512]
N_MESURES = 30  # par longueur ; on garde la mediane, pas un tir unique
N_ECHAUFFEMENT = 5


def chronometrer(tete, longueur):
    torch.manual_seed(GRAINE)
    x = torch.randn(longueur, DIM)

    for _ in range(N_ECHAUFFEMENT):
        tete(x)

    temps = []
    for _ in range(N_MESURES):
        debut = time.perf_counter()
        _, poids = tete(x)
        temps.append(time.perf_counter() - debut)
    temps.sort()
    mediane = temps[len(temps) // 2]
    return mediane, poids.shape[0] * poids.shape[1]


def main():
    torch.manual_seed(GRAINE + 1)
    tete = UneTeteAttention(DIM)

    print("=== Phase 12 : le Conseil demande la facture ===")
    print(f"{'longueur':>9} {'temps median (ms)':>20} {'cases de la matrice':>22}")
    resultats = []
    for L in LONGUEURS:
        t, n_cases = chronometrer(tete, L)
        resultats.append((L, t, n_cases))
        print(f"{L:>9} {1000*t:>20.4f} {n_cases:>22}")

    print("\n--- Facteur d'une longueur a la longueur double ---")
    for (L1, t1, _), (L2, t2, _) in zip(resultats, resultats[1:]):
        print(f"  {L1:>4} -> {L2:>4}  (x{L2//L1} en longueur) : temps x{t2/t1:.2f}, cases x{(L2*L2)/(L1*L1):.2f}")

    print("\n--- A quelle longueur ce montage devient-il inutilisable ? (extrapolation, pas intuition) ---")
    L1, t1, _ = resultats[-2]  # 256
    L2, t2, _ = resultats[-1]  # 512 -- les deux mesures les moins polluees par le cout fixe
    a = t2 / (L2 ** 2)  # ajustement a*L^2 sur le point le plus fiable
    for seuil_ms, label in [(100, "perceptible par un humain"), (1000, "une seconde d'attente")]:
        L_seuil = ((seuil_ms / 1000) / a) ** 0.5
        print(f"  Seuil {seuil_ms} ms ({label}) atteint vers L ~= {L_seuil:.0f} jetons (extrapolation en L^2 depuis {L1}/{L2})")
    print(f"  Le relevé le plus long de toute la transmission ne fait que 35 jetons (phase 6) : ")
    print(f"  ce montage, seul, ne sera jamais le goulot d'etranglement pour UN relevé. Le risque")
    print(f"  n'apparait que si on lui fait lire plusieurs centaines de relevés a la fois (acte 4).")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    xs = [r[0] for r in resultats]
    ys = [1000 * r[1] for r in resultats]
    ax.plot(xs, ys, marker="o")
    ax.set_xlabel("Longueur du relevé (jetons)")
    ax.set_ylabel("Temps median d'un passage avant (millisecondes)")
    ax.set_title("Phase 12 -- cout de l'attention, une seule tete, en fonction de la longueur")
    fig.tight_layout()
    chemin = FIGURES_DIR / "phase12_facture.png"
    fig.savefig(chemin, dpi=150)
    print(f"\nFigure enregistree : {chemin}")


if __name__ == "__main__":
    main()
