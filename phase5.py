"""Phase 5 : le budget de calcul.

Reatteindre le score de ModeleConv en phase 3 (accuracy test 0,550, meme
decoupe, memes 19 classes), en nettement moins de temps machine. Chaque
reglage est mesure seul, contre exactement la meme base de depart (celle
de la phase 3) -- jamais deux changements a la fois, sinon on ne sait pas
lequel a agi. Le reglage final combine seulement les leviers qui se sont
montres gagnants a l'isolement.
"""
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from commun import RACINE
from formes import (
    JeuFormes,
    assembler_lot,
    charger_jeu_formes,
    construire_classes,
    construire_vocabulaire,
    decouper,
    encoder,
)
from modele import ModeleConv

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
GRAINE = 42
EPOCHS = 8
BATCH_BASE = 64


class JeuFormesPrecalcule(Dataset):
    """Meme chose que JeuFormes, mais les sequences sont tokenisees et
    encodees UNE SEULE FOIS a la construction, pas a chaque __getitem__."""

    def __init__(self, df, word2idx, label2idx, longueur_max=40):
        self.sequences = [
            torch.tensor(encoder(t, word2idx, longueur_max)) for t in df["comments"]
        ]
        self.labels = [label2idx[s] for s in df["shape"]]

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, i):
        return self.sequences[i], self.labels[i]


def entrainer(train, val, word2idx, label2idx, precalcule=False, batch=BATCH_BASE, lr=1e-3, epochs=EPOCHS,
              arret_anticipe=False):
    """Boucle d'entrainement generique, chronometree epoque par epoque
    (temps ecoule depuis le debut, pas nombre de passages).

    Avec arret_anticipe=True, garde le meilleur point de controle (val_acc
    maximale) plutot que le dernier -- comme en phase 3 -- et rend le temps
    ecoule jusqu'a CETTE epoque, pas jusqu'a la fin du budget d'epoques.
    """
    import copy

    torch.manual_seed(GRAINE)
    modele = ModeleConv(taille_vocab=len(word2idx), n_classes=len(label2idx))
    optim = torch.optim.Adam(modele.parameters(), lr=lr)
    perte_fn = nn.CrossEntropyLoss()

    classe_dataset = JeuFormesPrecalcule if precalcule else JeuFormes
    dl_tr = DataLoader(
        classe_dataset(train, word2idx, label2idx), batch_size=batch, shuffle=True, collate_fn=assembler_lot
    )
    jeu_val = classe_dataset(val, word2idx, label2idx)
    Xval, yval = assembler_lot([jeu_val[i] for i in range(len(jeu_val))])

    temps, accs = [], []
    meilleur_acc, meilleur_etat, meilleur_temps = -1, None, None
    debut = time.time()
    for _ in range(epochs):
        modele.train()
        for xb, yb in dl_tr:
            optim.zero_grad()
            perte = perte_fn(modele(xb), yb)
            perte.backward()
            optim.step()
        modele.eval()
        with torch.no_grad():
            acc = (modele(Xval).argmax(dim=1) == yval).float().mean().item()
        t = time.time() - debut
        temps.append(t)
        accs.append(acc)
        if acc > meilleur_acc:
            meilleur_acc, meilleur_temps = acc, t
            if arret_anticipe:
                meilleur_etat = copy.deepcopy(modele.state_dict())
    duree_totale = temps[-1]
    if arret_anticipe:
        modele.load_state_dict(meilleur_etat)
        return modele, temps, accs, duree_totale, meilleur_temps
    return modele, temps, accs, duree_totale, duree_totale


def temps_pour_atteindre(temps, accs, cible):
    for t, a in zip(temps, accs):
        if a >= cible:
            return t
    return None  # jamais atteint dans le budget d'epoques


def evaluer_test(modele, test, word2idx, label2idx, precalcule=False):
    classe_dataset = JeuFormesPrecalcule if precalcule else JeuFormes
    jeu_test = classe_dataset(test, word2idx, label2idx)
    Xtest, ytest = assembler_lot([jeu_test[i] for i in range(len(jeu_test))])
    modele.eval()
    with torch.no_grad():
        return (modele(Xtest).argmax(dim=1) == ytest).float().mean().item()


def main():
    jeu, _ = charger_jeu_formes()
    train, val, test = decouper(jeu)
    word2idx = construire_vocabulaire(train["comments"], freq_min=3)
    label2idx = construire_classes(jeu["shape"])

    print("=== Phase 5 : le budget de calcul ===")
    CIBLE = 0.54  # niveau atteint par la phase 3 (val 0,5514, test 0,5502) -- seuil de comparaison

    print("\n[Base -- identique a la phase 3 : lot=64, tokenisation a la volee, lr=1e-3]")
    _, t_base8, a_base8, duree_base8, _ = entrainer(train, val, word2idx, label2idx, precalcule=False, batch=64, lr=1e-3)
    print(f"  temps/epoque ~{duree_base8/EPOCHS:.2f}s, val_acc finale={a_base8[-1]:.4f}, duree totale={duree_base8:.1f}s")

    print("\n[Levier A seul -- sequences precalculees une fois (lot=64, lr=1e-3)]")
    _, t_a, a_a, duree_a, _ = entrainer(train, val, word2idx, label2idx, precalcule=True, batch=64, lr=1e-3)
    print(f"  duree totale={duree_a:.1f}s (x{duree_base8/duree_a:.2f} plus rapide), val_acc finale={a_a[-1]:.4f}")

    print("\n[Levier B seul -- lot=256 (tokenisation a la volee, lr=1e-3)]")
    _, t_b, a_b, duree_b, _ = entrainer(train, val, word2idx, label2idx, precalcule=False, batch=256, lr=1e-3)
    print(f"  duree totale={duree_b:.1f}s (x{duree_base8/duree_b:.2f} plus rapide), val_acc finale={a_b[-1]:.4f}")

    print("\n[Levier C seul -- lr=3e-3 (lot=64, tokenisation a la volee)]")
    _, t_c, a_c, duree_c, _ = entrainer(train, val, word2idx, label2idx, precalcule=False, batch=64, lr=3e-3)
    print(f"  duree totale={duree_c:.1f}s (x{duree_base8/duree_c:.2f} plus rapide -- attendu ~1, seul le score peut changer), val_acc finale={a_c[-1]:.4f}")

    # --- Comparaison finale : base et recette, chacune avec arret anticipe,
    # jusqu'a ce que le score de la phase 3 (0,5502 test) soit au moins egale.
    EPOCHS_LONG = 16
    print(f"\n[Base longue, arret anticipe, jusqu'a {EPOCHS_LONG} epoques]")
    modele_base, t_base, a_base, duree_base, t_meilleur_base = entrainer(
        train, val, word2idx, label2idx, precalcule=False, batch=64, lr=1e-3, epochs=EPOCHS_LONG, arret_anticipe=True
    )
    acc_test_base = evaluer_test(modele_base, test, word2idx, label2idx, precalcule=False)
    print(f"  meilleure val_acc={max(a_base):.4f} atteinte a t={t_meilleur_base:.1f}s ; accuracy test={acc_test_base:.4f}")

    print(f"\n[Recette combinee -- precalcul + lot=256 + lr=2,5e-3, arret anticipe, jusqu'a {EPOCHS_LONG} epoques]")
    modele_r, t_r, a_r, duree_r, t_meilleur_r = entrainer(
        train, val, word2idx, label2idx, precalcule=True, batch=256, lr=2.5e-3, epochs=EPOCHS_LONG, arret_anticipe=True
    )
    acc_test_recette = evaluer_test(modele_r, test, word2idx, label2idx, precalcule=True)
    print(f"  meilleure val_acc={max(a_r):.4f} atteinte a t={t_meilleur_r:.1f}s ; accuracy test={acc_test_recette:.4f}")

    facteur = t_meilleur_base / t_meilleur_r
    print(f"\nTemps pour atteindre le meilleur score (arret anticipe) :")
    print(f"  base    : {t_meilleur_base:.1f}s -- accuracy test {acc_test_base:.4f}")
    print(f"  recette : {t_meilleur_r:.1f}s -- accuracy test {acc_test_recette:.4f}")
    print(f"  facteur : x{facteur:.2f}")
    print(f"  reference phase 3 : accuracy test 0.5502")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t_base, a_base, marker="o", label=f"base (phase 3) -- meilleur a {t_meilleur_base:.1f}s")
    ax.plot(t_r, a_r, marker="o", label=f"recette (phase 5) -- meilleur a {t_meilleur_r:.1f}s")
    ax.axvline(t_meilleur_base, color="tab:blue", linestyle=":", linewidth=1)
    ax.axvline(t_meilleur_r, color="tab:orange", linestyle=":", linewidth=1)
    ax.set_xlabel("Temps ecoule (secondes)")
    ax.set_ylabel("Accuracy (validation)")
    ax.set_title("Phase 5 -- meme resultat, temps ecoule au lieu d'epoques")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "phase5_temps.png", dpi=150)
    print("\nFigure enregistree : figures/phase5_temps.png")


if __name__ == "__main__":
    main()
