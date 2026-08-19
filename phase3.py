"""Phase 3 : battre le service statistique.

Deux montages, exactement la meme decoupe (formes.py), exactement les
memes 19 classes :
- le linéaire du service statistique : sac-de-mots (comptages) -> une
  seule couche lineaire.
- le notre (ModeleConv) : embedding -> conv1d -> batchnorm -> relu ->
  max-pool -> lineaire.

Compares aussi a la reference "toujours repondre la forme la plus
frequente".
"""
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from commun import RACINE
from formes import (
    JeuFormes,
    assembler_lot,
    charger_jeu_formes,
    construire_classes,
    construire_vocabulaire,
    decouper,
    tokeniser,
    vecteurs_comptage,
)
from modele import ModeleConv, ModeleLineaire

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
GRAINE = 42
EPOCHS = 10
BATCH = 64


def evaluer(modele, X, y, est_sequence):
    modele.eval()
    with torch.no_grad():
        logits = modele(X)
        preds = logits.argmax(dim=1)
        perte = nn.functional.cross_entropy(logits, y).item()
        acc = (preds == y).float().mean().item()
    return perte, acc, preds


def entrainer_lineaire(Xtr, ytr, Xval, yval, taille_vocab, n_classes):
    modele = ModeleLineaire(taille_vocab, n_classes)
    optim = torch.optim.Adam(modele.parameters(), lr=1e-3)
    perte_fn = nn.CrossEntropyLoss()
    jeu_tr = DataLoader(TensorDataset(Xtr, ytr), batch_size=BATCH, shuffle=True)

    hist_train, hist_val = [], []
    debut = time.time()
    for epoch in range(1, EPOCHS + 1):
        modele.train()
        pertes_epoch = []
        for xb, yb in jeu_tr:
            optim.zero_grad()
            logits = modele(xb)
            perte = perte_fn(logits, yb)
            perte.backward()
            optim.step()
            pertes_epoch.append(perte.item())
        perte_tr = sum(pertes_epoch) / len(pertes_epoch)
        perte_val, acc_val, _ = evaluer(modele, Xval, yval, est_sequence=False)
        hist_train.append(perte_tr)
        hist_val.append(perte_val)
        print(f"  [lineaire] epoch {epoch}/{EPOCHS}  perte_train={perte_tr:.4f}  perte_val={perte_val:.4f}  acc_val={acc_val:.4f}")
    duree = time.time() - debut
    return modele, hist_train, hist_val, duree


def entrainer_conv(train_df, val_df, word2idx, label2idx, epochs=EPOCHS):
    import copy

    n_classes = len(label2idx)
    modele = ModeleConv(taille_vocab=len(word2idx), n_classes=n_classes)
    optim = torch.optim.AdamW(modele.parameters(), lr=1e-3, weight_decay=1e-5)
    perte_fn = nn.CrossEntropyLoss()

    jeu_tr = JeuFormes(train_df, word2idx, label2idx)
    jeu_val = JeuFormes(val_df, word2idx, label2idx)
    dl_tr = DataLoader(jeu_tr, batch_size=BATCH, shuffle=True, collate_fn=assembler_lot)
    Xval, yval = assembler_lot([jeu_val[i] for i in range(len(jeu_val))])

    hist_train, hist_val = [], []
    meilleur_acc, meilleur_etat, meilleure_epoch = -1, None, 0
    debut = time.time()
    for epoch in range(1, epochs + 1):
        modele.train()
        pertes_epoch = []
        for xb, yb in dl_tr:
            optim.zero_grad()
            logits = modele(xb)
            perte = perte_fn(logits, yb)
            perte.backward()
            optim.step()
            pertes_epoch.append(perte.item())
        perte_tr = sum(pertes_epoch) / len(pertes_epoch)
        perte_val, acc_val, _ = evaluer(modele, Xval, yval, est_sequence=True)
        hist_train.append(perte_tr)
        hist_val.append(perte_val)
        print(f"  [conv]     epoch {epoch}/{epochs}  perte_train={perte_tr:.4f}  perte_val={perte_val:.4f}  acc_val={acc_val:.4f}")
        if acc_val > meilleur_acc:
            meilleur_acc, meilleure_epoch = acc_val, epoch
            meilleur_etat = copy.deepcopy(modele.state_dict())
    duree = time.time() - debut
    modele.load_state_dict(meilleur_etat)
    print(f"  [conv]     meilleure epoque retenue (arret anticipe) : {meilleure_epoch} (acc_val={meilleur_acc:.4f})")
    return modele, hist_train, hist_val, duree, Xval, yval


def tracer(hist_train, hist_val, titre, chemin):
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(hist_train, label="perte apprentissage")
    ax.plot(hist_val, label="perte validation")
    ax.set_xlabel("Epoque")
    ax.set_ylabel("Perte (cross-entropy)")
    ax.set_title(titre)
    ax.legend()
    fig.tight_layout()
    fig.savefig(chemin, dpi=150)
    print(f"Figure enregistree : {chemin}")


def demonstration_pipeline(texte, word2idx, modele_conv):
    print("\n--- Du texte brut au premier nombre qui entre dans le reseau ---")
    print(f"Texte brut     : {texte}")
    mots = tokeniser(texte)
    print(f"Tokenise       : {mots}")
    ids = [word2idx.get(w, word2idx['<unk>']) for w in mots]
    print(f"Identifiants   : {ids}")
    with torch.no_grad():
        vecteurs = modele_conv.embed(torch.tensor(ids))
    print(f"1er mot '{mots[0]}' -> vecteur d'embedding (dim {vecteurs.shape[1]}), 5 premieres valeurs :")
    print(f"  {vecteurs[0][:5].tolist()}")


def main():
    torch.manual_seed(GRAINE)
    jeu, detail = charger_jeu_formes()
    train, val, test = decouper(jeu)
    word2idx = construire_vocabulaire(train["comments"], freq_min=3)
    label2idx = construire_classes(jeu["shape"])
    n_classes = len(label2idx)

    print("=== Phase 3 : battre le service statistique ===")
    print(f"Classes retenues        : {n_classes}")
    print(f"Relevés retenus         : {detail['n_final']} (train={len(train)}, val={len(val)}, test={len(test)})")
    print(f"Vocabulaire (train, freq>=3) : {len(word2idx)} mots")
    print("Regles : trous et fourre-tout ecartes, round->circle et changed->changing fusionnes,")
    print("classes < 50 relevés ecartees (voir formes.py / RAPPORT.md).")

    ytr = torch.tensor([label2idx[s] for s in train["shape"]])
    yval = torch.tensor([label2idx[s] for s in val["shape"]])
    ytest = torch.tensor([label2idx[s] for s in test["shape"]])

    # --- Reference : toujours la forme la plus frequente -----------------
    classe_majoritaire = train["shape"].value_counts().idxmax()
    idx_maj = label2idx[classe_majoritaire]
    acc_majoritaire = (ytest == idx_maj).float().mean().item()
    print(f"\nReference (toujours '{classe_majoritaire}') -- accuracy test : {acc_majoritaire:.4f}")

    # --- Lineaire (service statistique) -----------------------------------
    print("\nEntrainement du lineaire (sac-de-mots) ...")
    Xtr = vecteurs_comptage(train["comments"].tolist(), word2idx)
    Xval = vecteurs_comptage(val["comments"].tolist(), word2idx)
    Xtest = vecteurs_comptage(test["comments"].tolist(), word2idx)
    modele_lin, htr_lin, hval_lin, duree_lin = entrainer_lineaire(Xtr, ytr, Xval, yval, len(word2idx), n_classes)
    _, acc_lin, _ = evaluer(modele_lin, Xtest, ytest, est_sequence=False)
    print(f"Lineaire -- accuracy test : {acc_lin:.4f} (entrainement : {duree_lin:.1f}s)")
    tracer(htr_lin, hval_lin, "Phase 3 -- lineaire (sac-de-mots)", FIGURES_DIR / "phase3_lineaire.png")

    # --- Le notre (ModeleConv) --------------------------------------------
    print("\nEntrainement du notre (ModeleConv) ...")
    modele_conv, htr_conv, hval_conv, duree_conv, Xval_seq, yval_seq = entrainer_conv(train, val, word2idx, label2idx)
    jeu_test = JeuFormes(test, word2idx, label2idx)
    Xtest_seq, ytest_seq = assembler_lot([jeu_test[i] for i in range(len(jeu_test))])
    _, acc_conv, _ = evaluer(modele_conv, Xtest_seq, ytest_seq, est_sequence=True)
    print(f"ModeleConv -- accuracy test : {acc_conv:.4f} (entrainement : {duree_conv:.1f}s)")
    tracer(htr_conv, hval_conv, "Phase 3 -- ModeleConv (le notre)", FIGURES_DIR / "phase3_conv.png")

    print("\n--- Trois scores cote a cote (accuracy, jeu de test, meme decoupe/classes) ---")
    print(f"Toujours '{classe_majoritaire}'      : {acc_majoritaire:.4f}")
    print(f"Lineaire (service statistique) : {acc_lin:.4f}")
    print(f"ModeleConv (le notre)          : {acc_conv:.4f}")

    demonstration_pipeline(test["comments"].iloc[0], word2idx, modele_conv)

    torch.save(
        {"word2idx": word2idx, "label2idx": label2idx, "state_dict": modele_conv.state_dict()},
        RACINE / "data" / "phase3_modele_conv.pt",
    )
    print("\nModele sauvegarde : data/phase3_modele_conv.pt (non versionne)")


if __name__ == "__main__":
    main()
