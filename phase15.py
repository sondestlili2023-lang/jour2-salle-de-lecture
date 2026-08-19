"""Phase 15 : le Conseil pose des questions, vous citez vos sources.

Systeme de question-reponse avec citations sur le fichier complet des
88 679 relevés bien formes (comments non filtres -- l'interdiction de
vocabulaire de la phase 8 etait specifique a la tache de classification,
pas a la lecture generale des temoignages).

Recherche : TF-IDF + similarite cosinus (deterministe, pas de reseau de
neurones ici -- la difficulte de la phase est de CHOISIR quoi lire parmi
88 679 candidats, pas de generer du texte). Comparee a une methode naive
(nombre de mots de la question presents tel quels dans le relevé).

Generation : un second cerveau emprunte, google/flan-t5-small (77M
parametres, encodeur-decodeur). DistilBERT (phase 14) est un encodeur
seul, incapable de produire du texte ; la tache exige de la generation,
donc un autre modele emprunte -- toujours "recupere librement", jamais
entraine par nous -- pas le meme instrument que la phase 14 parce que ce
n'est pas le meme travail.
"""
import json
import re

import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer

from commun import RACINE, charger_releves

DATA_DIR = RACINE / "data"

# Liste figee AVANT toute mesure -- ne pas modifier apres avoir vu les resultats.
# Le Conseil pose ses questions en francais ; le corpus (NUFORC) est en
# anglais. Premier essai tout-en-francais : le petit generateur emprunte
# (77M parametres) melangeait consignes et contenu, produisait des reponses
# vides ou incoherentes -- documente plus bas. Correction : une traduction
# anglaise fixe, ecrite ici en meme temps que l'originale (pas apres avoir
# vu si ca marchait mieux), sert de requete reelle au systeme -- le
# francais reste la version "officielle" posee au Conseil.
QUESTIONS_FIXES = [
    ("Est-ce que les apparitions au-dessus des zones habitées ont une forme particulière ?",
     "Do sightings over populated areas have a particular shape?"),
    ("Que décrivent les témoins qui parlent de bruit ?",
     "What do witnesses who mention noise describe?"),
    ("Que racontent les témoins qui mentionnent des enfants présents ?",
     "What do witnesses who mention children present describe?"),
    ("Que disent les témoins à propos des feux d'artifice ?",
     "What do witnesses say about fireworks?"),
    ("Les objets triangulaires sont-ils décrits comme silencieux ?",
     "Are triangular objects described as silent?"),
    ("Que rapportent les témoins qui disent avoir eu peur ?",
     "What do witnesses who say they were scared report?"),
    ("Les témoins parlent-ils de messages reçus par télépathie ?",
     "Do witnesses mention messages received by telepathy?"),
    ("Les témoins mentionnent-ils leur équipe sportive préférée ?",
     "Do witnesses mention their favorite sports team?"),  # controle hors-sujet
]

BUDGET_CARACTERES = 500  # caracteres de contexte, fixe, jamais depasse -- voir RAPPORT.md
SEUIL_AUCUNE_REPONSE = 0.08  # score TF-IDF max en dessous duquel on renonce plutot qu'inventer


def charger_corpus():
    df, total, ecartees = charger_releves()
    df = df.reset_index(drop=True)
    return df


def construire_index(df):
    vectoriseur = TfidfVectorizer(stop_words="english", max_features=30000)
    matrice = vectoriseur.fit_transform(df["comments"])
    return vectoriseur, matrice


def rechercher_tfidf(question, vectoriseur, matrice, k=25):
    vq = vectoriseur.transform([question])
    scores = (matrice @ vq.T).toarray().ravel()
    ordre = np.argsort(scores)[::-1][:k]
    return ordre, scores[ordre]


MOTS_VIDES_EN = {
    "the", "a", "an", "of", "do", "does", "is", "are", "what", "who", "their", "about",
    "over", "on", "to", "and", "or", "in", "by", "say", "mention", "witnesses", "describe",
}


def rechercher_naif(question, df, k=25):
    """Nombre de mots de la question (hors mots vides anglais) presents tel
    quels (sous-chaine, insensible a la casse) dans le relevé -- pas de
    ponderation, pas de normalisation, juste un compte."""
    mots_q = [m for m in re.findall(r"[a-zA-Z]+", question.lower()) if m not in MOTS_VIDES_EN]
    textes = df["comments"].str.lower()

    def compte(t):
        return sum(1 for m in mots_q if m in t)

    scores = textes.map(compte).to_numpy()
    ordre = np.argsort(scores)[::-1][:k]
    return ordre, scores[ordre]


def selectionner_dans_budget(df, ordre, scores, budget):
    """Prend les relevés dans l'ordre de score decroissant jusqu'a saturer
    le budget de caracteres -- jamais depasse."""
    choisis, caracteres = [], 0
    for i, s in zip(ordre, scores):
        if s <= 0:
            break
        texte = df.loc[i, "comments"]
        if caracteres + len(texte) > budget:
            if not choisis:
                choisis.append(i)  # au moins un, tronque plus bas si besoin
            break
        choisis.append(i)
        caracteres += len(texte)
    return choisis


def construire_prompt(question_en, df, indices):
    lignes = [f"[{n+1}] {df.loc[i,'comments']}" for n, i in enumerate(indices)]
    contexte = "\n".join(lignes)
    return (
        f"Testimonies:\n{contexte}\n\n"
        f"Question: {question_en}\n"
        "Summarize in one or two sentences what the testimonies above say, citing testimony numbers in brackets."
    )


def repondre(question_en, df, indices, tokenizer, modele):
    if not indices:
        return "Nous n'avons pas ce relevé (aucun candidat suffisamment proche de la question)."
    prompt = construire_prompt(question_en, df, indices)
    ids = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        sortie = modele.generate(
            **ids, max_new_tokens=100, min_new_tokens=25, num_beams=8, no_repeat_ngram_size=3
        )
    return tokenizer.decode(sortie[0], skip_special_tokens=True)


def main():
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    print("=== Phase 15 : le Conseil pose des questions, vous citez vos sources ===")
    df = charger_corpus()
    print(f"Corpus : {len(df)} relevés bien formes (fichier complet, comments non filtres)")
    print(f"Budget de texte : {BUDGET_CARACTERES} caracteres par reponse (fixe)")
    print(f"Questions figees ({len(QUESTIONS_FIXES)}) :")
    for q_fr, q_en in QUESTIONS_FIXES:
        print(f"  - FR: {q_fr}")
        print(f"    EN (requete reelle) : {q_en}")

    vectoriseur, matrice = construire_index(df)

    print("\n--- Verification de determinisme (une question, deux recherches) ---")
    o1, _ = rechercher_tfidf(QUESTIONS_FIXES[0][1], vectoriseur, matrice)
    o2, _ = rechercher_tfidf(QUESTIONS_FIXES[0][1], vectoriseur, matrice)
    print(f"Memes relevés retournes les deux fois : {list(o1) == list(o2)}")

    print("\nChargement du modele de generation (google/flan-t5-small, 77M parametres)...")
    tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-small")
    modele = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-small")

    resultats = []
    for q_fr, q_en in QUESTIONS_FIXES:
        print(f"\n=== Question : {q_fr} ({q_en}) ===")
        entree_q = {"question_fr": q_fr, "question_en": q_en}

        for methode, fn_recherche in [("mien_tfidf", rechercher_tfidf), ("naif_motcle", rechercher_naif)]:
            if methode == "mien_tfidf":
                ordre, scores = fn_recherche(q_en, vectoriseur, matrice)
            else:
                ordre, scores = fn_recherche(q_en, df)

            score_max = float(scores[0]) if len(scores) else 0.0
            if methode == "mien_tfidf" and score_max < SEUIL_AUCUNE_REPONSE:
                indices = []
            else:
                indices = selectionner_dans_budget(df, ordre, scores, BUDGET_CARACTERES)

            reponse = repondre(q_en, df, indices, tokenizer, modele)
            citations = [
                {"datetime": df.loc[i, "datetime"], "city": df.loc[i, "city"],
                 "shape": df.loc[i, "shape"], "comments": df.loc[i, "comments"]}
                for i in indices
            ]

            print(f"\n[{methode}] score max={score_max:.3f}  n_citations={len(indices)}")
            print(f"  Reponse : {reponse}")
            for c in citations[:3]:
                print(f"    cite : {c['datetime']} -- {c['city']} -- {c['shape']} -- {c['comments']}")
            if len(citations) > 3:
                print(f"    ... et {len(citations)-3} autre(s) citation(s)")

            entree_q[methode] = {"score_max": score_max, "reponse": reponse, "citations": citations}

        resultats.append(entree_q)

    with open(DATA_DIR / "phase15_resultats.json", "w") as f:
        json.dump(resultats, f, indent=2, ensure_ascii=False)
    print("\nResultats enregistres : data/phase15_resultats.json (non versionne -- relire pour noter le sourcage)")


if __name__ == "__main__":
    main()
