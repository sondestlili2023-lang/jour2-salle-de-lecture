"""Phase 7 : quatre relevés a la fois.

Reprend le montage de la phase 6 (ModeleTCN, avec residus) et le relance
a 4 relevés par lot au lieu de 64. La panne attendue vient de la
BatchNorm de chaque BlocDilate : ses statistiques (moyenne/variance) sont
calculees sur le lot en cours. Avec 64 exemples, ces statistiques sont
une bonne estimation de la population ; avec 4, elles sont bruitees, et
chaque exemple se retrouve normalise en fonction de qui d'autre est tombe
dans son lot -- une dependance qui n'aurait jamais du exister.
"""
import copy
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from commun import RACINE
from formes import JeuFormes, assembler_lot, charger_jeu_formes, construire_classes, construire_vocabulaire, decouper
from modele import ModeleTCN

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
GRAINE = 42
EPOCHS = 8
# Lot=4 sur les 51 223 relevés d'entrainement ferait ~12 800 pas/epoque (au lieu
# de ~800 a lot=64) : un sous-echantillon garde la demonstration jouable en
# quelques minutes sans changer la nature du phenomene observe (stable/instable).
N_TRAIN_DEMO = 8000
EPOCHS_DEMO = 5


def entrainer(train, val, word2idx, label2idx, batch, norme_par_exemple, epochs=EPOCHS, n_train_max=None):
    if n_train_max is not None and len(train) > n_train_max:
        train = train.sample(n=n_train_max, random_state=GRAINE).reset_index(drop=True)
    torch.manual_seed(GRAINE)
    modele = ModeleTCN(
        taille_vocab=len(word2idx), n_classes=len(label2idx), residuel=True, norme_par_exemple=norme_par_exemple
    )
    optim = torch.optim.Adam(modele.parameters(), lr=1e-3)
    perte_fn = nn.CrossEntropyLoss()
    dl_tr = DataLoader(JeuFormes(train, word2idx, label2idx), batch_size=batch, shuffle=True, collate_fn=assembler_lot)
    jeu_val = JeuFormes(val, word2idx, label2idx)
    Xval, yval = assembler_lot([jeu_val[i] for i in range(len(jeu_val))])

    hist_tr, meilleur_acc, meilleur_etat = [], -1, None
    debut = time.time()
    for _ in range(epochs):
        modele.train()
        pertes = []
        for xb, yb in dl_tr:
            optim.zero_grad()
            perte = perte_fn(modele(xb), yb)
            perte.backward()
            optim.step()
            pertes.append(perte.item())
        hist_tr.append(sum(pertes) / len(pertes))
        modele.eval()
        with torch.no_grad():
            acc = (modele(Xval).argmax(dim=1) == yval).float().mean().item()
        if acc > meilleur_acc:
            meilleur_acc, meilleur_etat = acc, copy.deepcopy(modele.state_dict())
    modele.load_state_dict(meilleur_etat)
    duree = time.time() - debut
    return modele, hist_tr, meilleur_acc, duree


def evaluer_test(modele, test, word2idx, label2idx):
    jeu_test = JeuFormes(test, word2idx, label2idx)
    Xtest, ytest = assembler_lot([jeu_test[i] for i in range(len(jeu_test))])
    modele.eval()
    with torch.no_grad():
        return (modele(Xtest).argmax(dim=1) == ytest).float().mean().item()


def test_relevé_unique(word2idx, label2idx):
    """Que se passe-t-il avec l'ancien montage (BatchNorm) si on doit un jour
    predire sur un seul relevé (lot de taille 1) ?"""
    torch.manual_seed(GRAINE)
    modele = ModeleTCN(taille_vocab=len(word2idx), n_classes=len(label2idx), norme_par_exemple=False)
    x_un = torch.randint(2, len(word2idx), (1, 10))

    print("\n--- Et pour predire sur un seul relevé (lot de taille 1), avec l'ancien montage (BatchNorm) ? ---")
    modele.eval()
    try:
        with torch.no_grad():
            modele(x_un)
        print("  En mode eval() : ca marche -- BatchNorm utilise ses statistiques figees (moyenne/variance")
        print("  apprises pendant l'entrainement), pas celles du lot courant. Pas de probleme a l'inference.")
    except Exception as e:
        print(f"  En mode eval() : echoue -- {e}")

    modele.train()
    try:
        modele(x_un)
        print("  En mode train() : ca marche (inattendu).")
    except Exception as e:
        print(f"  En mode train() : ECHOUE -- {type(e).__name__}: {e}")
        print("  La variance d'UN SEUL exemple n'est pas definie : si jamais ce montage devait continuer")
        print("  a s'entrainer (ou etre affine) un relevé a la fois, il plante purement et simplement.")


def main():
    jeu, _ = charger_jeu_formes()
    train, val, test = decouper(jeu)
    word2idx = construire_vocabulaire(train["comments"], freq_min=3)
    label2idx = construire_classes(jeu["shape"])

    print("=== Phase 7 : quatre relevés a la fois ===")

    print(f"\n(Demonstration sur un sous-echantillon de {N_TRAIN_DEMO} relevés d'entrainement, {EPOCHS_DEMO} epoques :")
    print(" lot=4 sur les 51 223 relevés complets ferait ~12 800 pas/epoque, injouable en session interactive.")
    print(" Le phenomene demontre -- stable/instable selon la normalisation -- ne depend pas de la taille du jeu.)")

    print("\n[Avant correction -- lot=4, BatchNorm (montage de la phase 6)]")
    _, htr_avant, acc_avant, duree_avant = entrainer(
        train, val, word2idx, label2idx, batch=4, norme_par_exemple=False, epochs=EPOCHS_DEMO, n_train_max=N_TRAIN_DEMO
    )
    print(f"  perte train : {[round(x,3) for x in htr_avant]}")
    print(f"  meilleure val_acc : {acc_avant:.4f}  ({duree_avant:.1f}s)")

    print("\n[Apres correction -- lot=4, GroupNorm (normalisation par exemple)]")
    modele_apres4, htr_apres4, acc_apres4, duree_apres4 = entrainer(
        train, val, word2idx, label2idx, batch=4, norme_par_exemple=True, epochs=EPOCHS_DEMO, n_train_max=N_TRAIN_DEMO
    )
    acc_test_apres4 = evaluer_test(modele_apres4, test, word2idx, label2idx)
    print(f"  perte train : {[round(x,3) for x in htr_apres4]}")
    print(f"  meilleure val_acc : {acc_apres4:.4f}  test_acc : {acc_test_apres4:.4f}  ({duree_apres4:.1f}s)")

    print("\n[Meme correction (GroupNorm), meme sous-echantillon, relancee au lot de la phase 6 (64) -- coute-t-elle quelque chose ?]")
    modele_apres64, htr_apres64, acc_apres64, duree_apres64 = entrainer(
        train, val, word2idx, label2idx, batch=64, norme_par_exemple=True, epochs=EPOCHS_DEMO, n_train_max=N_TRAIN_DEMO
    )
    acc_test_apres64 = evaluer_test(modele_apres64, test, word2idx, label2idx)
    print(f"  meilleure val_acc : {acc_apres64:.4f}  test_acc : {acc_test_apres64:.4f}  ({duree_apres64:.1f}s)")

    print("\n[Reference : meme sous-echantillon, lot=64, BatchNorm (montage de la phase 6 tel quel)]")
    modele_ref64, htr_ref64, acc_ref64, duree_ref64 = entrainer(
        train, val, word2idx, label2idx, batch=64, norme_par_exemple=False, epochs=EPOCHS_DEMO, n_train_max=N_TRAIN_DEMO
    )
    acc_test_ref64 = evaluer_test(modele_ref64, test, word2idx, label2idx)
    print(f"  meilleure val_acc : {acc_ref64:.4f}  test_acc : {acc_test_ref64:.4f}  ({duree_ref64:.1f}s)")

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(htr_avant, label="lot=4, BatchNorm (avant correction)", marker="x")
    ax.plot(htr_apres4, label="lot=4, GroupNorm (apres correction)", marker="o")
    ax.set_xlabel("Epoque")
    ax.set_ylabel("Perte (entrainement)")
    ax.set_title("Phase 7 -- lot de 4 : avant/apres correction")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "phase7_lot4.png", dpi=150)
    print("\nFigure enregistree : figures/phase7_lot4.png")

    test_relevé_unique(word2idx, label2idx)


if __name__ == "__main__":
    main()
