"""Phase 14 : le cerveau emprunté, et sa facture.

Modele emprunte : distilbert-base-uncased (66,4M parametres), recupere
librement sur Hugging Face, assez petit pour tourner sur une machine
sans accelerateur -- c'est deja la tension de l'acte 4 : DistilBERT est
lui-meme un choix "petit exprès" (une version compressee de BERT), pas
le plus gros cerveau disponible, precisement parce que le plus gros
n'entre pas dans notre budget de calcul.

Trois regimes sur la meme tache (comments filtres -> forme, phase 8) :
  1. sonde gelee   : tout DistilBERT fige, seule une tete lineaire s'entraine.
  2. fine-tuning partiel : tout bouge, mais a des vitesses differentes
     selon la profondeur (taux d'apprentissage discriminant).
  3. adaptateurs LoRA : DistilBERT intact, seules de petites matrices de
     rang faible glissees dans les projections query/value s'entrainent.

Chaque regime tourne dans son PROPRE sous-processus (mesure de memoire
propre, pas polluee par les regimes precedents) et imprime une ligne
JSON de resultats que le processus parent recolte.
"""
import copy
import json
import resource
import subprocess
import sys
import time

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from commun import RACINE
from formes import charger_jeu_formes, construire_classes, decouper
from phase8 import construire_mots_interdits, filtrer_texte

NOM_MODELE = "distilbert-base-uncased"
GRAINE = 42
N_TRAIN_SOUS_ECH = 4000
N_VAL_SOUS_ECH = 800
BATCH = 16
LONGUEUR_MAX = 40
DATA_DIR = RACINE / "data"


def preparer_jeu_filtre():
    jeu, _ = charger_jeu_formes()
    interdits = construire_mots_interdits()
    train, val, test = decouper(jeu)
    for d in (train, val, test):
        d["comments"] = d["comments"].map(lambda t: filtrer_texte(t, interdits))
    label2idx = construire_classes(jeu["shape"])
    return train, val, test, label2idx


class JeuTexte(Dataset):
    def __init__(self, df, label2idx):
        self.textes = df["comments"].tolist()
        self.labels = [label2idx[s] for s in df["shape"]]

    def __len__(self):
        return len(self.textes)

    def __getitem__(self, i):
        return self.textes[i], self.labels[i]


def assembler(lot, tokenizer):
    textes, labels = zip(*lot)
    enc = tokenizer(list(textes), return_tensors="pt", padding=True, truncation=True, max_length=LONGUEUR_MAX)
    return enc, torch.tensor(labels)


class CoucheLoRA(nn.Module):
    """Remplace une couche lineaire GELEE par elle-meme + une correction de
    rang faible (A: d_in x r, B: r x d_out), seule partie entrainee.
    La couche d'origine n'est jamais modifiee (requires_grad=False)."""

    def __init__(self, lineaire_gele, rang=8, alpha=16):
        super().__init__()
        self.lineaire = lineaire_gele
        for p in self.lineaire.parameters():
            p.requires_grad = False
        d_in, d_out = lineaire_gele.in_features, lineaire_gele.out_features
        self.A = nn.Parameter(torch.randn(d_in, rang) * 0.01)
        self.B = nn.Parameter(torch.zeros(rang, d_out))
        self.echelle = alpha / rang

    def forward(self, x):
        return self.lineaire(x) + self.echelle * (x @ self.A @ self.B)


class ClassifieurLLM(nn.Module):
    def __init__(self, encodeur, dim_cachee, n_classes):
        super().__init__()
        self.encodeur = encodeur
        self.tete = nn.Linear(dim_cachee, n_classes)

    def forward(self, enc):
        sortie = self.encodeur(**enc)
        cls = sortie.last_hidden_state[:, 0, :]  # jeton [CLS]
        return self.tete(cls)


def construire_modele(regime):
    from transformers import AutoModel

    torch.manual_seed(GRAINE)
    encodeur = AutoModel.from_pretrained(NOM_MODELE)
    dim = encodeur.config.hidden_size

    if regime == "sonde":
        for p in encodeur.parameters():
            p.requires_grad = False

    elif regime == "lora":
        for p in encodeur.parameters():
            p.requires_grad = False
        for bloc in encodeur.transformer.layer:
            attn = bloc.attention
            attn.q_lin = CoucheLoRA(attn.q_lin)
            attn.v_lin = CoucheLoRA(attn.v_lin)

    modele = ClassifieurLLM(encodeur, dim, n_classes=19)
    return modele


def groupes_parametres(modele, regime, lr_base=2e-5):
    """Un seul groupe pour 'sonde' et 'lora' (le reste est gele de toute
    facon). Pour 'partiel' : un taux d'apprentissage par profondeur --
    l'embedding (le plus pres de l'entree) a le taux le plus bas, la tete
    de classification (le plus pres de la sortie) le plus haut."""
    if regime != "partiel":
        return [{"params": [p for p in modele.parameters() if p.requires_grad], "lr": lr_base * 50}]

    groupes = []
    groupes.append({"params": modele.encodeur.embeddings.parameters(), "lr": lr_base * 0.2})
    n_couches = len(modele.encodeur.transformer.layer)
    for i, bloc in enumerate(modele.encodeur.transformer.layer):
        profondeur = (i + 1) / n_couches  # 0 (pres de l'entree) .. 1 (pres de la sortie)
        groupes.append({"params": bloc.parameters(), "lr": lr_base * (0.2 + 1.8 * profondeur)})
    groupes.append({"params": modele.tete.parameters(), "lr": lr_base * 50})
    return groupes


def compter_entrainables(modele):
    return sum(p.numel() for p in modele.parameters() if p.requires_grad)


def taille_checkpoint(modele):
    # etat des seuls parametres entrainables (ce qu'il faut vraiment sauvegarder)
    etat = {n: p.detach().clone() for n, p in modele.named_parameters() if p.requires_grad}
    chemin = DATA_DIR / "phase14_tmp_ckpt.pt"
    torch.save(etat, chemin)
    taille = chemin.stat().st_size
    chemin.unlink()
    return taille


def executer_regime(regime, epochs=3):
    from transformers import AutoTokenizer

    torch.manual_seed(GRAINE)
    train, val, test, label2idx = preparer_jeu_filtre()
    train_s = train.sample(n=N_TRAIN_SOUS_ECH, random_state=GRAINE).reset_index(drop=True)
    val_s = val.sample(n=N_VAL_SOUS_ECH, random_state=GRAINE).reset_index(drop=True)

    tokenizer = AutoTokenizer.from_pretrained(NOM_MODELE)
    modele = construire_modele(regime)

    n_entrainables = compter_entrainables(modele)
    taille_ko = taille_checkpoint(modele) / 1024

    groupes = groupes_parametres(modele, regime)
    optim = torch.optim.Adam(groupes)
    perte_fn = nn.CrossEntropyLoss()

    dl_tr = DataLoader(JeuTexte(train_s, label2idx), batch_size=BATCH, shuffle=True,
                        collate_fn=lambda lot: assembler(lot, tokenizer))
    dl_val = DataLoader(JeuTexte(val_s, label2idx), batch_size=64, shuffle=False,
                         collate_fn=lambda lot: assembler(lot, tokenizer))
    dl_test = DataLoader(JeuTexte(test, label2idx), batch_size=64, shuffle=False,
                          collate_fn=lambda lot: assembler(lot, tokenizer))

    temps_pas = []
    meilleur_acc, meilleur_etat = -1, None
    debut_total = time.time()
    for ep in range(epochs):
        modele.train()
        for enc, y in dl_tr:
            t0 = time.time()
            optim.zero_grad()
            logits = modele(enc)
            perte = perte_fn(logits, y)
            perte.backward()
            optim.step()
            temps_pas.append(time.time() - t0)

        modele.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for enc, y in dl_val:
                preds = modele(enc).argmax(dim=1)
                correct += (preds == y).sum().item()
                total += len(y)
        acc = correct / total
        print(f"[{regime}] epoch {ep+1}/{epochs} val_acc={acc:.4f}", file=sys.stderr)
        if acc > meilleur_acc:
            meilleur_acc = acc
            meilleur_etat = {n: p.detach().clone() for n, p in modele.named_parameters() if p.requires_grad}
    duree_totale = time.time() - debut_total

    for n, p in modele.named_parameters():
        if p.requires_grad and n in meilleur_etat:
            p.data.copy_(meilleur_etat[n])

    modele.eval()
    from sklearn.metrics import f1_score
    tous_preds, tous_y = [], []
    with torch.no_grad():
        for enc, y in dl_test:
            preds = modele(enc).argmax(dim=1)
            tous_preds.append(preds); tous_y.append(y)
    tous_preds = torch.cat(tous_preds); tous_y = torch.cat(tous_y)
    acc_test = (tous_preds == tous_y).float().mean().item()
    f1_test = f1_score(tous_y.numpy(), tous_preds.numpy(), average="macro")

    pic_memoire_ko = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    resultat = {
        "regime": regime,
        "n_entrainables": n_entrainables,
        "taille_checkpoint_ko": round(taille_ko, 1),
        "temps_median_pas_ms": round(1000 * sorted(temps_pas)[len(temps_pas) // 2], 2),
        "duree_totale_s": round(duree_totale, 1),
        "pic_memoire_mo": round(pic_memoire_ko / 1024, 1),
        "acc_test": round(acc_test, 4),
        "macro_f1_test": round(f1_test, 4),
    }
    print("RESULTAT_JSON:" + json.dumps(resultat))
    return resultat


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--regime":
        executer_regime(sys.argv[2])
        return

    print("=== Phase 14 : le cerveau emprunté, et sa facture ===")
    print(f"Modele : {NOM_MODELE} (66,4M parametres)")
    print(f"Sous-echantillon d'entrainement : {N_TRAIN_SOUS_ECH} relevés (budget CPU) ; "
          f"evaluation sur le test COMPLET (10 977 relevés, comme la phase 8).")
    print("Reference (phase 8, ModeleTCN, vocabulaire interdit) : accuracy test 0,3507, macro-F1 0,1327")

    resultats = []
    for regime in ("sonde", "partiel", "lora"):
        print(f"\n--- Lancement du regime '{regime}' (sous-processus dedie) ---")
        proc = subprocess.run(
            [sys.executable, __file__, "--regime", regime],
            capture_output=True, text=True, cwd=str(RACINE),
        )
        for ligne in proc.stderr.splitlines():
            print("  " + ligne)
        ligne_resultat = next(l for l in proc.stdout.splitlines() if l.startswith("RESULTAT_JSON:"))
        r = json.loads(ligne_resultat[len("RESULTAT_JSON:"):])
        resultats.append(r)
        print(f"  -> {r}")

    print("\n=== Tableau recapitulatif ===")
    print(f"{'regime':>10} {'params entr.':>13} {'ckpt (Ko)':>10} {'ms/pas':>8} {'duree(s)':>9} {'pic RAM(Mo)':>12} {'acc test':>9} {'macro-F1':>9}")
    for r in resultats:
        print(f"{r['regime']:>10} {r['n_entrainables']:>13,} {r['taille_checkpoint_ko']:>10.1f} "
              f"{r['temps_median_pas_ms']:>8.1f} {r['duree_totale_s']:>9.1f} {r['pic_memoire_mo']:>12.1f} "
              f"{r['acc_test']:>9.4f} {r['macro_f1_test']:>9.4f}")

    with open(DATA_DIR / "phase14_resultats.json", "w") as f:
        json.dump(resultats, f, indent=2)
    print("\nResultats enregistres : data/phase14_resultats.json (non versionne)")


if __name__ == "__main__":
    main()
