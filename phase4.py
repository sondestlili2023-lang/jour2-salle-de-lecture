"""Phase 4 : le carnet de pannes.

Reprend le montage de la phase 3 (ModeleConv, meme decoupe, memes
classes) et le casse volontairement trois fois, une panne a la fois, en
repartant a chaque fois d'un modele neuf. Trois pannes de nature
differente, chacune correspondant a un symptome que le Bureau a deja vu.
"""
import copy

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from commun import RACINE
from formes import JeuFormes, assembler_lot, charger_jeu_formes, construire_classes, construire_vocabulaire, decouper
from modele import ModeleConv

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
GRAINE = 42
EPOCHS = 5
BATCH = 64


def preparer():
    jeu, _ = charger_jeu_formes()
    train, val, test = decouper(jeu)
    word2idx = construire_vocabulaire(train["comments"], freq_min=3)
    label2idx = construire_classes(jeu["shape"])
    return train, val, test, word2idx, label2idx


def nouveau_modele(word2idx, label2idx):
    torch.manual_seed(GRAINE)
    return ModeleConv(taille_vocab=len(word2idx), n_classes=len(label2idx))


# --- Reference saine ------------------------------------------------------

def entrainement_sain(train, val, word2idx, label2idx):
    modele = nouveau_modele(word2idx, label2idx)
    optim = torch.optim.Adam(modele.parameters(), lr=1e-3)
    perte_fn = nn.CrossEntropyLoss()
    dl_tr = DataLoader(JeuFormes(train, word2idx, label2idx), batch_size=BATCH, shuffle=True, collate_fn=assembler_lot)
    Xval, yval = assembler_lot([JeuFormes(val, word2idx, label2idx)[i] for i in range(len(val))])

    hist_tr, hist_val = [], []
    for _ in range(EPOCHS):
        modele.train()
        pertes = []
        for xb, yb in dl_tr:
            optim.zero_grad()
            logits = modele(xb)
            perte = perte_fn(logits, yb)
            perte.backward()
            optim.step()
            pertes.append(perte.item())
        hist_tr.append(sum(pertes) / len(pertes))
        modele.eval()
        with torch.no_grad():
            perte_val = perte_fn(modele(Xval), yval).item()
        hist_val.append(perte_val)
    return modele, hist_tr, hist_val, Xval, yval


# --- Panne 1 : oubli de model.eval() a l'evaluation ------------------------

def panne_1(train, val, word2idx, label2idx):
    """Geste : evaluer sans jamais appeler modele.eval() (dropout + batchnorm restent actifs)."""
    modele = nouveau_modele(word2idx, label2idx)
    optim = torch.optim.Adam(modele.parameters(), lr=1e-3)
    perte_fn = nn.CrossEntropyLoss()
    dl_tr = DataLoader(JeuFormes(train, word2idx, label2idx), batch_size=BATCH, shuffle=True, collate_fn=assembler_lot)
    Xval, yval = assembler_lot([JeuFormes(val, word2idx, label2idx)[i] for i in range(len(val))])

    hist_val_correct, hist_val_buggy = [], []
    for _ in range(EPOCHS):
        modele.train()
        for xb, yb in dl_tr:
            optim.zero_grad()
            perte = perte_fn(modele(xb), yb)
            perte.backward()
            optim.step()

        # LA PANNE : evaluation appelee juste apres l'entrainement, sans modele.eval() --
        # le modele est encore en mode train() (dropout actif, batchnorm sur stats du lot
        # courant). Feree en petits lots pour que l'effet ne se moyenne pas silencieusement
        # sur les 10 977 exemples du set de validation pris d'un bloc.
        with torch.no_grad():
            pertes_buggy = []
            for i in range(0, len(yval), 4):
                xb, yb = Xval[i : i + 4], yval[i : i + 4]
                if len(yb) < 2:
                    continue
                pertes_buggy.append(perte_fn(modele(xb), yb).item())
        hist_val_buggy.append(sum(pertes_buggy) / len(pertes_buggy))

        # La bonne facon de faire : modele.eval() avant d'evaluer.
        modele.eval()
        with torch.no_grad():
            perte_val_correct = perte_fn(modele(Xval), yval).item()
        hist_val_correct.append(perte_val_correct)

    # test rapide (< 1 minute) : meme entree, deux passages, sortie identique ?
    modele.train()
    with torch.no_grad():
        sortie_1 = modele(Xval)
        sortie_2 = modele(Xval)
    deterministe = torch.allclose(sortie_1, sortie_2)
    return hist_val_correct, hist_val_buggy, deterministe


# --- Panne 2 : mauvais dictionnaire de decodage -----------------------------

def panne_2(train, val, word2idx, label2idx):
    """Geste : decoder les predictions avec un idx->label reconstruit dans un autre ordre
    que celui utilise pour encoder les cibles a l'entrainement (ex : trie par frequence
    au lieu de trie alphabetique -- un classique de label-encoder regenere entre deux
    versions du code)."""
    modele = nouveau_modele(word2idx, label2idx)
    optim = torch.optim.Adam(modele.parameters(), lr=1e-3)
    perte_fn = nn.CrossEntropyLoss()
    dl_tr = DataLoader(JeuFormes(train, word2idx, label2idx), batch_size=BATCH, shuffle=True, collate_fn=assembler_lot)
    Xval, yval = assembler_lot([JeuFormes(val, word2idx, label2idx)[i] for i in range(len(val))])

    idx2label_correct = {i: c for c, i in label2idx.items()}
    classes_par_frequence = train["shape"].value_counts().index.tolist()
    idx2label_buggy = {i: c for i, c in enumerate(classes_par_frequence)}  # ordre different

    hist_perte, hist_acc_correcte, hist_acc_buggy = [], [], []
    for _ in range(EPOCHS):
        modele.train()
        pertes = []
        for xb, yb in dl_tr:
            optim.zero_grad()
            logits = modele(xb)
            perte = perte_fn(logits, yb)
            perte.backward()
            optim.step()
            pertes.append(perte.item())
        hist_perte.append(sum(pertes) / len(pertes))

        modele.eval()
        with torch.no_grad():
            preds = modele(Xval).argmax(dim=1)
        acc_correcte = (preds == yval).float().mean().item()
        noms_predits_bug = [idx2label_buggy[p.item()] for p in preds]
        noms_vrais = [idx2label_correct[y.item()] for y in yval]
        acc_buggy = sum(a == b for a, b in zip(noms_predits_bug, noms_vrais)) / len(noms_vrais)
        hist_acc_correcte.append(acc_correcte)
        hist_acc_buggy.append(acc_buggy)

    return hist_perte, hist_acc_correcte, hist_acc_buggy


# --- Panne 3 : optimizer.step() jamais appele -------------------------------

def panne_3(train, val, word2idx, label2idx):
    """Geste : calculer perte.backward() mais oublier optim.step() (les poids ne bougent jamais)."""
    modele = nouveau_modele(word2idx, label2idx)
    optim = torch.optim.Adam(modele.parameters(), lr=1e-3)
    perte_fn = nn.CrossEntropyLoss()
    dl_tr = DataLoader(JeuFormes(train, word2idx, label2idx), batch_size=BATCH, shuffle=True, collate_fn=assembler_lot)

    poids_avant = modele.sortie.weight.detach().clone()
    hist_tr = []
    for _ in range(EPOCHS):
        modele.train()
        pertes = []
        for xb, yb in dl_tr:
            optim.zero_grad()
            perte = perte_fn(modele(xb), yb)
            perte.backward()
            # LA PANNE : optim.step() n'est jamais appele
            pertes.append(perte.item())
        hist_tr.append(sum(pertes) / len(pertes))
    poids_apres = modele.sortie.weight.detach().clone()

    # test rapide (< 1 minute) : un poids a-t-il bouge ?
    poids_inchanges = torch.equal(poids_avant, poids_apres)
    return hist_tr, poids_inchanges


def main():
    train, val, test, word2idx, label2idx = preparer()
    print("=== Phase 4 : le carnet de pannes ===")

    print("\n[reference saine]")
    _, hist_tr_sain, hist_val_sain, _, _ = entrainement_sain(train, val, word2idx, label2idx)
    print("perte train :", [round(x, 3) for x in hist_tr_sain])
    print("perte val   :", [round(x, 3) for x in hist_val_sain])

    print("\n[panne 1 -- oubli de model.eval()]")
    hv_correct, hv_buggy, deterministe = panne_1(train, val, word2idx, label2idx)
    print("perte val (correcte, model.eval()) :", [round(x, 3) for x in hv_correct])
    print("perte val (buguee, model.train())  :", [round(x, 3) for x in hv_buggy])
    print(f"Test rapide -- deux passages identiques sur la meme entree -> sortie identique : {deterministe}")
    print("(False = dropout/batchnorm encore actifs = modele.eval() jamais appele)")

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(hv_correct, label="perte val -- modele.eval() (correct)", marker="o")
    ax.plot(hv_buggy, label="perte val -- modele.train() oublie (bug)", marker="x")
    ax.set_xlabel("Epoque")
    ax.set_ylabel("Perte (cross-entropy)")
    ax.set_title("Panne 1 -- meme donnees, mode du modele different")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "phase4_panne1.png", dpi=150)

    print("\n[panne 2 -- mauvais dictionnaire de decodage]")
    hp, hac, hab = panne_2(train, val, word2idx, label2idx)
    print("perte train (indices, correcte)      :", [round(x, 3) for x in hp])
    print("accuracy (indices, correcte)         :", [round(x, 3) for x in hac])
    print("accuracy (noms decodes avec le bug)  :", [round(x, 3) for x in hab])

    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.plot(hp, color="tab:gray", linestyle="--", label="perte train (indices)")
    ax1.set_xlabel("Epoque")
    ax1.set_ylabel("Perte")
    ax2 = ax1.twinx()
    ax2.plot(hac, color="tab:green", marker="o", label="accuracy (decodage correct)")
    ax2.plot(hab, color="tab:red", marker="x", label="accuracy (decodage buggy)")
    ax2.set_ylabel("Accuracy")
    lignes = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lignes, [l.get_label() for l in lignes], loc="center right")
    ax1.set_title("Panne 2 -- la perte baisse, l'accuracy decodee reste cassee")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "phase4_panne2.png", dpi=150)

    print("\n[panne 3 -- optim.step() jamais appele]")
    ht, poids_inchanges = panne_3(train, val, word2idx, label2idx)
    print("perte train :", [round(x, 3) for x in ht])
    print(f"Test rapide -- poids de sortie identiques avant/apres entrainement : {poids_inchanges}")
    print("(True = aucune mise a jour n'a jamais eu lieu = optim.step() jamais appele)")

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(hist_tr_sain, label="perte train -- saine", marker="o")
    ax.plot(ht, label="perte train -- optim.step() oublie (bug)", marker="x")
    ax.set_xlabel("Epoque")
    ax.set_ylabel("Perte (cross-entropy)")
    ax.set_title("Panne 3 -- la perte ne bouge plus")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "phase4_panne3.png", dpi=150)

    print("\nFigures enregistrees : phase4_panne1.png, phase4_panne2.png, phase4_panne3.png")


if __name__ == "__main__":
    main()
