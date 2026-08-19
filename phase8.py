"""Phase 8 : le Conseil a lu trois relevés.

Interdit tout mot du vocabulaire des formes dans le texte donne au
modele (apprentissage ET evaluation), le prouve (compte de fuites
residuelles = 0), reentraine a l'identique (ModeleTCN, residus,
GroupNorm -- le montage compatible phase 6 + phase 7) et rend la chute,
globale et par classe.
"""
import copy
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader

from commun import RACINE
from formes import (
    JeuFormes,
    assembler_lot,
    charger_jeu_formes,
    construire_classes,
    construire_vocabulaire,
    decouper,
    tokeniser,
)
from modele import ModeleTCN

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
GRAINE = 42
EPOCHS = 10
BATCH = 64

CLASSES_FINALES = [
    "changing", "chevron", "cigar", "circle", "cone", "cross", "cylinder", "diamond",
    "disk", "egg", "fireball", "flash", "formation", "light", "oval", "rectangle",
    "sphere", "teardrop", "triangle",
]
MOTS_SOURCES_FUSION = ["round", "changed"]

# variantes d'ecriture et pluriels, a la main -- un mot par forme (et par mot
# fusionne), plus ses formes courantes. Le tokeniseur casse deja les mots
# composes ("cigar-shaped" -> "cigar" + "shaped") : bannir la racine suffit,
# "shaped" seul n'est pas revelateur (il accompagne n'importe quelle forme).
VARIANTES = {
    "changing": ["changing", "changes", "change"],
    "chevron": ["chevron", "chevrons"],
    "cigar": ["cigar", "cigars"],
    "circle": ["circle", "circles", "circular"],
    "cone": ["cone", "cones", "conical"],
    "cross": ["cross", "crosses"],
    "cylinder": ["cylinder", "cylinders", "cylindrical"],
    "diamond": ["diamond", "diamonds"],
    "disk": ["disk", "disks", "disc", "discs"],
    "egg": ["egg", "eggs"],
    "fireball": ["fireball", "fireballs"],
    "flash": ["flash", "flashes", "flashing", "flashed"],
    "formation": ["formation", "formations"],
    "light": ["light", "lights", "lighted", "lighting"],
    "oval": ["oval", "ovals", "ovoid"],
    "rectangle": ["rectangle", "rectangles", "rectangular"],
    "sphere": ["sphere", "spheres", "spherical"],
    "teardrop": ["teardrop", "teardrops"],
    "triangle": ["triangle", "triangles", "triangular"],
    "round": ["round", "rounds", "rounded"],
    "changed": ["changed"],
}


def construire_mots_interdits():
    interdits = set()
    for base in CLASSES_FINALES + MOTS_SOURCES_FUSION:
        interdits.update(VARIANTES[base])
    return interdits


def taux_presence(jeu):
    """Reproduit les chiffres du Conseil : le mot de la forme est-il present
    tel quel (sous-chaine, insensible a la casse) dans le texte ?"""
    def contient(texte, mot):
        return mot.lower() in texte.lower()

    overall = jeu.apply(lambda r: contient(r["comments"], r["shape"]), axis=1).mean()
    par_forme = {}
    for forme in ("triangle", "light", "circle"):
        sous = jeu[jeu["shape"] == forme]
        par_forme[forme] = sous["comments"].apply(lambda t: contient(t, forme)).mean()
    return overall, par_forme


def filtrer_texte(texte, interdits):
    mots = tokeniser(texte)
    return " ".join(m for m in mots if m not in interdits)


def compte_fuites(comments_filtres, interdits):
    n = 0
    for t in comments_filtres:
        if any(m in interdits for m in tokeniser(t)):
            n += 1
    return n


def entrainer(train, val, word2idx, label2idx):
    torch.manual_seed(GRAINE)
    modele = ModeleTCN(
        taille_vocab=len(word2idx), n_classes=len(label2idx), residuel=True, norme_par_exemple=True
    )
    optim = torch.optim.Adam(modele.parameters(), lr=1e-3)
    perte_fn = nn.CrossEntropyLoss()
    dl_tr = DataLoader(JeuFormes(train, word2idx, label2idx), batch_size=BATCH, shuffle=True, collate_fn=assembler_lot)
    jeu_val = JeuFormes(val, word2idx, label2idx)
    Xval, yval = assembler_lot([jeu_val[i] for i in range(len(jeu_val))])

    meilleur_acc, meilleur_etat = -1, None
    debut = time.time()
    for _ in range(EPOCHS):
        modele.train()
        for xb, yb in dl_tr:
            optim.zero_grad()
            perte = perte_fn(modele(xb), yb)
            perte.backward()
            optim.step()
        modele.eval()
        with torch.no_grad():
            acc = (modele(Xval).argmax(dim=1) == yval).float().mean().item()
        if acc > meilleur_acc:
            meilleur_acc, meilleur_etat = acc, copy.deepcopy(modele.state_dict())
    modele.load_state_dict(meilleur_etat)
    return modele, meilleur_acc, time.time() - debut


def evaluer_complet(modele, test, word2idx, label2idx, idx2label):
    jeu_test = JeuFormes(test, word2idx, label2idx)
    Xtest, ytest = assembler_lot([jeu_test[i] for i in range(len(jeu_test))])
    modele.eval()
    with torch.no_grad():
        preds = modele(Xtest).argmax(dim=1)
    acc_globale = (preds == ytest).float().mean().item()
    macro_f1 = f1_score(ytest.numpy(), preds.numpy(), average="macro")

    acc_par_classe = {}
    for idx, nom in idx2label.items():
        masque = ytest == idx
        if masque.sum() > 0:
            acc_par_classe[nom] = (preds[masque] == ytest[masque]).float().mean().item()
    return acc_globale, macro_f1, acc_par_classe


def main():
    jeu, _ = charger_jeu_formes()
    interdits = construire_mots_interdits()

    print("=== Phase 8 : le Conseil a lu trois relevés ===")
    print(f"\nMots interdits ({len(interdits)}) : {sorted(interdits)}")

    overall, par_forme = taux_presence(jeu)
    print("\n--- Verification des chiffres du Conseil (mot de la forme present, sous-chaine) ---")
    print(f"triangle : {100*par_forme['triangle']:.1f}% (Conseil : 34,7%)")
    print(f"light    : {100*par_forme['light']:.1f}% (Conseil : 72,6%)")
    print(f"circle   : {100*par_forme['circle']:.1f}% (Conseil : 9,9%)")

    train, val, test = decouper(jeu)
    label2idx = construire_classes(jeu["shape"])
    idx2label = {i: c for c, i in label2idx.items()}

    # --- AVANT : texte brut ------------------------------------------------
    print("\n[AVANT -- texte brut, vocabulaire des formes autorise]")
    word2idx_avant = construire_vocabulaire(train["comments"], freq_min=3)
    modele_avant, val_acc_avant, duree_avant = entrainer(train, val, word2idx_avant, label2idx)
    acc_g_avant, f1_avant, par_classe_avant = evaluer_complet(modele_avant, test, word2idx_avant, label2idx, idx2label)
    print(f"  val_acc={val_acc_avant:.4f}  test accuracy globale={acc_g_avant:.4f}  macro-F1={f1_avant:.4f}  ({duree_avant:.1f}s)")

    # --- Filtrage ------------------------------------------------------------
    for d in (train, val, test):
        d["comments_filtre"] = d["comments"].map(lambda t: filtrer_texte(t, interdits))
    n_fuites = compte_fuites(list(train["comments_filtre"]) + list(val["comments_filtre"]) + list(test["comments_filtre"]), interdits)
    print(f"\n--- Preuve d'effectivite ---\nRelevés contenant encore un mot interdit apres filtrage : {n_fuites} (attendu : 0)")

    # --- APRES : texte filtre --------------------------------------------
    print("\n[APRES -- vocabulaire des formes interdit]")
    train2 = train.assign(comments=train["comments_filtre"])
    val2 = val.assign(comments=val["comments_filtre"])
    test2 = test.assign(comments=test["comments_filtre"])
    word2idx_apres = construire_vocabulaire(train2["comments"], freq_min=3)
    modele_apres, val_acc_apres, duree_apres = entrainer(train2, val2, word2idx_apres, label2idx)
    acc_g_apres, f1_apres, par_classe_apres = evaluer_complet(modele_apres, test2, word2idx_apres, label2idx, idx2label)
    print(f"  val_acc={val_acc_apres:.4f}  test accuracy globale={acc_g_apres:.4f}  macro-F1={f1_apres:.4f}  ({duree_apres:.1f}s)")

    print("\n--- Chute ---")
    print(f"Accuracy globale : {acc_g_avant:.4f} -> {acc_g_apres:.4f}  (chute de {100*(acc_g_avant-acc_g_apres):.1f} points)")
    print(f"Macro-F1         : {f1_avant:.4f} -> {f1_apres:.4f}  (chute de {100*(f1_avant-f1_apres):.1f} points)")

    print("\n--- Score par classe (accuracy), avant -> apres, trie par chute ---")
    chutes = sorted(par_classe_avant.keys(), key=lambda c: par_classe_avant[c] - par_classe_apres.get(c, 0), reverse=True)
    for c in chutes:
        av, ap = par_classe_avant[c], par_classe_apres.get(c, float("nan"))
        print(f"  {c:>10} : {av:.3f} -> {ap:.3f}  (chute {100*(av-ap):.1f} pts)")

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(chutes))
    ax.bar(x - 0.2, [par_classe_avant[c] for c in chutes], width=0.4, label="avant (mots autorisés)")
    ax.bar(x + 0.2, [par_classe_apres.get(c, 0) for c in chutes], width=0.4, label="après (mots interdits)")
    ax.set_xticks(x)
    ax.set_xticklabels(chutes, rotation=45, ha="right")
    ax.set_ylabel("Accuracy (test, par classe)")
    ax.set_title("Phase 8 -- accuracy par classe, avant/après interdiction du vocabulaire")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "phase8_par_classe.png", dpi=150)
    print("\nFigure enregistree : figures/phase8_par_classe.png")

    torch.save(
        {"word2idx": word2idx_apres, "label2idx": label2idx, "interdits": interdits, "state_dict": modele_apres.state_dict()},
        RACINE / "data" / "phase8_modele.pt",
    )
    print("Modele enregistre : data/phase8_modele.pt (non versionne)")


if __name__ == "__main__":
    main()
