"""Jeu de donnees et tache unique de l'acte 2 : comments entre, une forme sort.

Ce module centralise les trois decisions de la phase 3 (documentees et
defendues dans RAPPORT.md) pour que toutes les phases de l'acte 2
(2 a 9) travaillent sur exactement le meme jeu et les memes classes.

Decisions appliquees, dans l'ordre :
1. Les 2 922 relevés sans forme (`shape` vide) sont ecartes : rien a
   superviser sans etiquette.
2. Les deux fourre-tout (`unknown`, `other`) sont ecartes : ce ne sont pas
   des formes, ce sont des aveux d'incertitude du temoin ou du Bureau.
   Entrainer un detecteur de FORME a repondre "unknown" n'a pas de sens
   pour la tache "a partir du texte, retrouver la forme observee".
3. Les doublons de sens sont fusionnes : `round` -> `circle`,
   `changed` -> `changing` (meme forme, autre orthographe/temps).

Necessite technique (pas une des "trois decisions", mais sans elle la
decoupe stratifiee plante) : les classes avec moins de 50 relevés apres
fusion (`delta`=8, `crescent`=2, `pyramid`=1, `flare`=1, `hexagon`=1,
`dome`=1 -- 14 lignes en tout) sont ecartees : impossible de repartir
1 exemple sur train/val/test, impossible d'evaluer un score par classe
dessus.

Resultat : 19 classes, 73 177 relevés retenus sur 88 679 lignes bien
formees.
"""
import html
import re
from collections import Counter

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset

from commun import charger_releves

FUSIONS = {"round": "circle", "changed": "changing"}
FOURRE_TOUT = {"unknown", "other"}
SEUIL_CLASSE_MIN = 50

GRAINE = 42
TOKENISEUR = re.compile(r"[a-zA-Z']+")


def tokeniser(texte):
    return [w.lower() for w in TOKENISEUR.findall(html.unescape(texte))]


def charger_jeu_formes():
    """Retourne le DataFrame filtre (colonnes comments, shape) et le detail des exclusions."""
    df, total, ecartees_format = charger_releves()
    shape = df["shape"].str.strip().replace(FUSIONS)

    n_trous = (shape == "").sum()
    n_fourre_tout = shape.isin(FOURRE_TOUT).sum()

    masque = (shape != "") & (~shape.isin(FOURRE_TOUT))
    comptes = shape[masque].value_counts()
    classes_rares = comptes[comptes < SEUIL_CLASSE_MIN].index
    n_rares = shape[masque].isin(classes_rares).sum()

    masque_final = masque & (~shape.isin(classes_rares))
    jeu = df.loc[masque_final, ["comments"]].copy()
    jeu["shape"] = shape[masque_final]
    jeu["comments"] = jeu["comments"].map(html.unescape)

    detail = {
        "total_brut": total,
        "ecartees_format": len(ecartees_format),
        "n_trous": int(n_trous),
        "n_fourre_tout": int(n_fourre_tout),
        "n_rares": int(n_rares),
        "n_classes": jeu["shape"].nunique(),
        "n_final": len(jeu),
    }
    return jeu, detail


def decouper(jeu, prop_val=0.15, prop_test=0.15):
    """Decoupe stratifiee (memes proportions de classes dans les 3 parties)."""
    train_val, test = train_test_split(
        jeu, test_size=prop_test, stratify=jeu["shape"], random_state=GRAINE
    )
    prop_val_ajustee = prop_val / (1 - prop_test)
    train, val = train_test_split(
        train_val, test_size=prop_val_ajustee, stratify=train_val["shape"], random_state=GRAINE
    )
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


def construire_vocabulaire(textes, freq_min=3):
    """Vocabulaire construit uniquement sur les textes fournis (train), pour eviter la fuite."""
    compteur = Counter()
    for t in textes:
        compteur.update(tokeniser(t))
    mots = [mot for mot, n in compteur.items() if n >= freq_min]
    mots.sort()
    word2idx = {"<pad>": 0, "<unk>": 1}
    for mot in mots:
        word2idx[mot] = len(word2idx)
    return word2idx


def construire_classes(shapes):
    classes = sorted(shapes.unique())
    return {c: i for i, c in enumerate(classes)}


def encoder(texte, word2idx, longueur_max):
    ids = [word2idx.get(w, word2idx["<unk>"]) for w in tokeniser(texte)][:longueur_max]
    if not ids:
        ids = [word2idx["<unk>"]]
    return ids


class JeuFormes(Dataset):
    """Encode chaque relevé en identifiants de mots (pour le modele a embeddings)."""

    def __init__(self, df, word2idx, label2idx, longueur_max=40):
        self.textes = df["comments"].tolist()
        self.labels = [label2idx[s] for s in df["shape"]]
        self.word2idx = word2idx
        self.longueur_max = longueur_max

    def __len__(self):
        return len(self.textes)

    def __getitem__(self, i):
        ids = encoder(self.textes[i], self.word2idx, self.longueur_max)
        return torch.tensor(ids, dtype=torch.long), self.labels[i]


def assembler_lot(lot):
    """collate_fn : pad les sequences du lot a la longueur du plus long du lot."""
    sequences, labels = zip(*lot)
    longueur = max(len(s) for s in sequences)
    batch = torch.zeros(len(sequences), longueur, dtype=torch.long)
    for i, s in enumerate(sequences):
        batch[i, : len(s)] = s
    return batch, torch.tensor(labels, dtype=torch.long)


def vecteurs_comptage(textes, word2idx):
    """Sac-de-mots (comptages), pour le modele lineaire du service statistique."""
    V = len(word2idx)
    mat = torch.zeros(len(textes), V)
    for i, t in enumerate(textes):
        for w in tokeniser(t):
            j = word2idx.get(w, word2idx["<unk>"])
            mat[i, j] += 1
    return mat
