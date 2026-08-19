"""Phase 9 : rendre des comptes sur trois decisions.

Reprend le modele de la phase 8 (vocabulaire des formes interdit) et
explique trois de ses predictions sur le jeu de test, mot par mot, par
occlusion : on retire un mot a la fois (remplace par <unk>), on regarde
de combien la confiance dans la classe predite chute. Un mot dont le
retrait fait CHUTER la confiance est un mot que le modele a utilise comme
preuve ; un mot dont le retrait fait MONTER la confiance est un mot qui
brouillait sa decision.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn.functional as F

from commun import RACINE
from formes import charger_jeu_formes, decouper, encoder, tokeniser
from modele import ModeleTCN
from phase8 import construire_mots_interdits, filtrer_texte

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)
LONGUEUR_MAX = 40

# (indice dans le test filtre, etiquette de la fiche)
EXEMPLES = [
    (3820, "reussi"),
    (3329, "rate"),
    (9583, "hesitation"),
]


def charger_modele_et_jeu():
    ckpt = torch.load(RACINE / "data" / "phase8_modele.pt", weights_only=False)
    word2idx, label2idx = ckpt["word2idx"], ckpt["label2idx"]
    idx2label = {i: c for c, i in label2idx.items()}
    modele = ModeleTCN(taille_vocab=len(word2idx), n_classes=len(label2idx), residuel=True, norme_par_exemple=True)
    modele.load_state_dict(ckpt["state_dict"])
    modele.eval()

    jeu, _ = charger_jeu_formes()
    _, _, test = decouper(jeu)
    interdits = construire_mots_interdits()
    test = test.reset_index(drop=True).copy()
    test["comments_filtre"] = test["comments"].map(lambda t: filtrer_texte(t, interdits))
    return modele, word2idx, label2idx, idx2label, test


def occlusion(modele, word2idx, idx2label, texte_filtre):
    mots = tokeniser(texte_filtre)[:LONGUEUR_MAX]
    ids = encoder(texte_filtre, word2idx, LONGUEUR_MAX)
    id_unk = word2idx["<unk>"]

    with torch.no_grad():
        probs_pleines = F.softmax(modele(torch.tensor([ids])), dim=1)[0]
    top2 = torch.topk(probs_pleines, 2)
    classe_predite = top2.indices[0].item()
    classe_seconde = top2.indices[1].item()
    conf_pleine = probs_pleines[classe_predite].item()

    lots = []
    for i in range(len(ids)):
        version = ids.copy()
        version[i] = id_unk
        lots.append(version)
    with torch.no_grad():
        probs_occlus = F.softmax(modele(torch.tensor(lots)), dim=1)
    importances = (conf_pleine - probs_occlus[:, classe_predite]).tolist()

    return {
        "mots": mots,
        "importances": importances,
        "predit": idx2label[classe_predite],
        "confiance": conf_pleine,
        "second": idx2label[classe_seconde],
        "confiance_seconde": top2.values[1].item(),
    }


def tracer(res, vrai, chemin, titre):
    mots, imp = res["mots"], res["importances"]
    ordre = list(range(len(mots)))[::-1]  # premier mot en haut
    couleurs = ["#2a9d5c" if imp[i] >= 0 else "#c0392b" for i in ordre]
    fig, ax = plt.subplots(figsize=(7, 0.4 * len(mots) + 1.2))
    ax.barh([mots[i] for i in ordre], [imp[i] for i in ordre], color=couleurs)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Importance (chute de confiance si ce mot est retire -- vert = a l'appui, rouge = brouille)")
    ax.set_title(titre)
    fig.tight_layout()
    fig.savefig(chemin, dpi=150)


def main():
    modele, word2idx, label2idx, idx2label, test = charger_modele_et_jeu()

    print("=== Phase 9 : rendre des comptes sur trois decisions ===")
    for idx, tag in EXEMPLES:
        r = test.loc[idx]
        res = occlusion(modele, word2idx, idx2label, r["comments_filtre"])
        print(f"\n[{tag}] idx={idx}  vrai={r['shape']}  texte filtre : {r['comments_filtre']}")
        print(f"  predit={res['predit']} (conf={res['confiance']:.3f})  second={res['second']} (conf={res['confiance_seconde']:.3f})")
        print("  importance par mot :")
        for m, v in zip(res["mots"], res["importances"]):
            print(f"    {m:>12} : {v:+.4f}")
        titre = f"Phase 9 -- {tag} (vrai={r['shape']}, predit={res['predit']})"
        chemin = FIGURES_DIR / f"phase9_{tag}.png"
        tracer(res, r["shape"], chemin, titre)
        print(f"  Figure enregistree : {chemin}")


if __name__ == "__main__":
    main()
