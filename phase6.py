"""Phase 6 : le champ de vision du modele.

La salle des calculs interdit desormais tout montage qui lit un
temoignage mot par mot en attendant le precedent (donc pas de RNN/LSTM/
GRU -- ModeleConv de la phase 3 n'en utilisait de toute facon pas). Mais
une seule couche de convolution (noyau=3) ne voit que 3 mots autour de
chaque position : bien avant le pooling global, une position de sortie
n'a vu qu'une fraction du relevé. Ce fichier construit une pile de
convolutions dilatees (ModeleTCN, modele.py) dont le champ de vision
cumule depasse la longueur du relevé le plus long, le prouve par le
calcul et par l'experience, puis entraine le montage.
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
from formes import (
    JeuFormes,
    assembler_lot,
    charger_jeu_formes,
    construire_classes,
    construire_vocabulaire,
    decouper,
    encoder,
    tokeniser,
)
from modele import ModeleTCN

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
GRAINE = 42
EPOCHS = 8
BATCH = 64
LONGUEUR_MAX = 40


def longueurs(jeu):
    lens = jeu["comments"].map(lambda t: len(tokeniser(t)))
    return int(lens.max()), float(lens.median())


def verification_experimentale(relevé, word2idx):
    """Change le premier mot d'un relevé reel et montre que la representation
    du DERNIER token, avant le pooling, en est affectee -- pas seulement la
    sortie finale (que le pooling ferait de toute facon bouger trivialement)."""
    torch.manual_seed(GRAINE)
    modele = ModeleTCN(taille_vocab=len(word2idx), n_classes=19)  # poids frais, non entraine : propriete structurelle
    modele.eval()

    ids_originaux = encoder(relevé, word2idx, LONGUEUR_MAX)
    mots = tokeniser(relevé)[: LONGUEUR_MAX]
    ids_modifies = ids_originaux.copy()
    ids_modifies[0] = word2idx.get("light", word2idx["<unk>"]) if mots[0] != "light" else word2idx["<unk>"]

    def representation_avant_pool(ids):
        x = modele.embed(torch.tensor([ids])).transpose(1, 2)
        x = modele.projection(x)
        for couche in modele.couches:
            x = couche(x)
        return x[0, :, -1]  # position du DERNIER token, tous canaux

    with torch.no_grad():
        rep_orig = representation_avant_pool(ids_originaux)
        rep_mod = representation_avant_pool(ids_modifies)
        logits_orig = modele(torch.tensor([ids_originaux]))
        logits_mod = modele(torch.tensor([ids_modifies]))

    ecart_representation = (rep_orig - rep_mod).abs().max().item()
    ecart_logits = (logits_orig - logits_mod).abs().max().item()
    return mots, ecart_representation, ecart_logits


def entrainer(modele_classe, train, val, word2idx, label2idx, **kwargs):
    torch.manual_seed(GRAINE)
    modele = modele_classe(taille_vocab=len(word2idx), n_classes=len(label2idx), **kwargs)
    optim = torch.optim.Adam(modele.parameters(), lr=1e-3)
    perte_fn = nn.CrossEntropyLoss()
    dl_tr = DataLoader(JeuFormes(train, word2idx, label2idx), batch_size=BATCH, shuffle=True, collate_fn=assembler_lot)
    jeu_val = JeuFormes(val, word2idx, label2idx)
    Xval, yval = assembler_lot([jeu_val[i] for i in range(len(jeu_val))])

    hist_tr, hist_val, meilleur_acc, meilleur_etat = [], [], -1, None
    debut = time.time()
    for _ in range(EPOCHS):
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
            logits = modele(Xval)
            hist_val.append(perte_fn(logits, yval).item())
            acc = (logits.argmax(dim=1) == yval).float().mean().item()
        if acc > meilleur_acc:
            meilleur_acc, meilleur_etat = acc, copy.deepcopy(modele.state_dict())
    modele.load_state_dict(meilleur_etat)
    duree = time.time() - debut
    return modele, hist_tr, hist_val, meilleur_acc, duree


def evaluer_test(modele, test, word2idx, label2idx):
    jeu_test = JeuFormes(test, word2idx, label2idx)
    Xtest, ytest = assembler_lot([jeu_test[i] for i in range(len(jeu_test))])
    modele.eval()
    with torch.no_grad():
        return (modele(Xtest).argmax(dim=1) == ytest).float().mean().item()


def main():
    jeu, _ = charger_jeu_formes()
    train, val, test = decouper(jeu)
    word2idx = construire_vocabulaire(train["comments"], freq_min=3)
    label2idx = construire_classes(jeu["shape"])

    print("=== Phase 6 : le champ de vision du modele ===")
    lmax, lmed = longueurs(jeu)
    print(f"Longueur (jetons) -- max acceptee en entree : {LONGUEUR_MAX}, max reellement observee : {lmax}, mediane : {lmed}")

    print("\n--- Champ de vision cumule, couche par couche (ModeleTCN, noyau=3) ---")
    modele_ref = ModeleTCN(taille_vocab=len(word2idx), n_classes=len(label2idx))
    table = modele_ref.champ_de_vision_cumule()
    print(f"{'couche':>6} {'dilation':>9} {'ajoute':>7} {'total cumule':>13}")
    for i, (dilation, ajout, total) in enumerate(table, start=1):
        print(f"{i:>6} {dilation:>9} {ajout:>7} {total:>13}")
    total_final = table[-1][2]
    print(f"\nTotal cumule ({total_final}) > longueur max acceptee ({LONGUEUR_MAX}) : "
          f"{'OUI' if total_final > LONGUEUR_MAX else 'NON'}")

    print("\n--- Verification experimentale (modele non entraine, poids frais) ---")
    long_releve = jeu.loc[jeu["comments"].map(lambda t: len(tokeniser(t))).idxmax(), "comments"]
    mots, ecart_rep, ecart_logits = verification_experimentale(long_releve, word2idx)
    print(f"Relevé ({len(mots)} jetons) : {' '.join(mots)}")
    print(f"1er mot change ('{mots[0]}' -> autre mot).")
    print(f"Ecart max sur la representation du DERNIER token (avant pooling) : {ecart_rep:.6f}")
    print(f"Ecart max sur les logits finaux                                  : {ecart_logits:.6f}")
    print("Un ecart non nul sur la representation du dernier token prouve que le champ de")
    print("vision cumule atteint bien la premiere position -- pas seulement le pooling global.")

    print("\n--- Entrainement : la pile degrade-t-elle le score sans raccourcis residuels ? ---")
    modele_sans_res, htr_s, hval_s, acc_val_s, duree_s = entrainer(
        ModeleTCN, train, val, word2idx, label2idx, residuel=False
    )
    acc_test_s = evaluer_test(modele_sans_res, test, word2idx, label2idx)
    print(f"Sans residus    : val_acc={acc_val_s:.4f}  test_acc={acc_test_s:.4f}  ({duree_s:.1f}s)")

    modele_avec_res, htr_r, hval_r, acc_val_r, duree_r = entrainer(
        ModeleTCN, train, val, word2idx, label2idx, residuel=True
    )
    acc_test_r = evaluer_test(modele_avec_res, test, word2idx, label2idx)
    print(f"Avec residus    : val_acc={acc_val_r:.4f}  test_acc={acc_test_r:.4f}  ({duree_r:.1f}s)")
    print("Reference phase 3 (ModeleConv, 1 couche, pas de champ de vision complet) : test_acc=0.5502")

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(hval_s, label="perte val -- sans raccourcis residuels", marker="x")
    ax.plot(hval_r, label="perte val -- avec raccourcis residuels", marker="o")
    ax.set_xlabel("Epoque")
    ax.set_ylabel("Perte de validation")
    ax.set_title("Phase 6 -- empiler des couches dilatees : effet des residus")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "phase6_residus.png", dpi=150)
    print("\nFigure enregistree : figures/phase6_residus.png")


if __name__ == "__main__":
    main()
