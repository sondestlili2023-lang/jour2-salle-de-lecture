"""Phase 2 : le test d'acceptation du Bureau.

Avant de lancer le moindre entrainement sur les 73 177 relevés, le montage
(ModeleConv de modele.py) doit prouver qu'il peut au moins apprendre 8
relevés par coeur, sans une seule erreur. On ne cherche ni generalisation
ni honnetete : on verifie juste que la plomberie (embedding, convolution,
retropropagation, optimiseur) fonctionne, avant d'y engager des heures de
calcul sur la transmission entiere.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn

from commun import RACINE
from formes import assembler_lot, charger_jeu_formes, construire_classes, construire_vocabulaire, encoder
from modele import ModeleConv

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

GRAINE = 42
MAX_ITER = 2000


def choisir_8():
    """8 relevés reels, choisis pour couvrir 8 formes differentes (pas 8 fois 'light')."""
    jeu, _ = charger_jeu_formes()
    huit = jeu.groupby("shape", group_keys=False).head(1).sample(
        n=8, random_state=GRAINE
    ) if jeu["shape"].nunique() >= 8 else None
    # un exemplaire de 8 classes distinctes, tire de facon reproductible
    premiers = jeu.drop_duplicates(subset="shape").sample(n=8, random_state=GRAINE)
    return premiers.reset_index(drop=True)


def main():
    torch.manual_seed(GRAINE)
    huit = choisir_8()
    print("=== Phase 2 : test d'acceptation (8 relevés) ===")
    for _, r in huit.iterrows():
        print(f"[{r['shape']:>10}] {r['comments']}")

    word2idx = construire_vocabulaire(huit["comments"], freq_min=1)
    label2idx = construire_classes(huit["shape"])
    idx2label = {i: c for c, i in label2idx.items()}

    sequences = [torch.tensor(encoder(t, word2idx, longueur_max=40)) for t in huit["comments"]]
    labels = torch.tensor([label2idx[s] for s in huit["shape"]])
    lot, cibles = assembler_lot(list(zip(sequences, labels)))

    modele = ModeleConv(taille_vocab=len(word2idx), n_classes=len(label2idx))
    optimiseur = torch.optim.Adam(modele.parameters(), lr=0.01)
    perte_fn = nn.CrossEntropyLoss()

    pertes = []
    for iteration in range(1, MAX_ITER + 1):
        modele.train()
        optimiseur.zero_grad()
        logits = modele(lot)
        perte = perte_fn(logits, cibles)
        perte.backward()
        optimiseur.step()
        pertes.append(perte.item())

        predictions = logits.argmax(dim=1)
        if torch.equal(predictions, cibles):
            print(f"\n8/8 correctes atteintes en {iteration} iterations (perte finale = {perte.item():.5f})")
            break
    else:
        print(f"\nPas de 8/8 apres {MAX_ITER} iterations -- voir le journal des tentatives dans RAPPORT.md")

    modele.eval()
    with torch.no_grad():
        logits = modele(lot)
        predictions = logits.argmax(dim=1)
    print("\nPredictions finales vs vraies formes :")
    for i in range(8):
        vrai = idx2label[cibles[i].item()]
        pred = idx2label[predictions[i].item()]
        marque = "OK" if vrai == pred else "FAUX"
        print(f"  {marque:>4}  vrai={vrai:<10} predit={pred}")

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(pertes)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Perte (cross-entropy)")
    ax.set_title("Phase 2 -- courbe de perte sur les 8 relevés (par coeur)")
    fig.tight_layout()
    chemin = FIGURES_DIR / "phase2_perte.png"
    fig.savefig(chemin, dpi=150)
    print(f"\nFigure enregistree : {chemin}")


if __name__ == "__main__":
    main()
