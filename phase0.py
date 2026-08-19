"""Phase 0 : refaire les calculs du disparu.

Reproduit, depuis le fichier, les quatre affirmations chiffrees du dossier
laisse par l'analyste precedent, plus deux chiffres manquants : le maximum
de relevés atteint en une seule journee sur toute la transmission, et le
rang du 4 juillet dans ce classement.

Choix de la date : `datetime` (date d'observation par le temoin), pas
`date_posted` (date de publication par le Bureau). Les quatre affirmations
du dossier parlent toutes d'un comportement du ciel et des temoins (quel
jour la population regarde en l'air, quel mois, quel jour precis) -- c'est
un phenomene ancre sur l'instant de l'observation, pas sur le delai
administratif de traitement du dossier par le Bureau. `date_posted` mesure
autre chose (voir Jour1/phase8_chronologie.py : elle reflete des annees de
retard de traitement, tres irregulier). Verification a posteriori : les
pourcentages obtenus avec `datetime` tombent exactement sur ceux du
dossier (17.7% / 12.6% / 11.3% / 6.2%), ce qui confirme le choix.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from commun import RACINE, charger_releves, parser_dates

FIGURES_DIR = RACINE / "figures"
FIGURES_DIR.mkdir(exist_ok=True)


def preparer():
    df, total, ecartees = charger_releves()
    df = parser_dates(df)
    sans_date = df["datetime_obs"].isna().sum()
    df_dates = df.dropna(subset=["datetime_obs"])
    # Le dossier parle d'une transmission "de 1990 a 2014" : 235 relevés
    # anterieurs a 1990 existent dans le fichier brut (jusqu'a 1906), mais
    # sont trop rares et trop irreguliers pour representer un rythme
    # d'observation (moins d'une poignee par an) ; le dossier les exclut
    # implicitement en situant sa fenetre a partir de 1990.
    sub = df_dates[df_dates["datetime_obs"].dt.year >= 1990].copy()
    return df, total, ecartees, sans_date, sub


def main():
    df, total, ecartees, sans_date, sub = preparer()

    print("=== Phase 0 : refaire les calculs du disparu ===")
    print(f"Lignes dans le fichier brut        : {total}")
    print(f"Lignes ecartees (mauvais format)   : {len(ecartees)}")
    print(f"Lignes avec datetime illisible     : {sans_date} (sur {len(df)} lignes bien formees)")
    print(f"Relevés retenus (datetime >= 1990) : {len(sub)}")

    # --- 1. Span en jours et moyenne quotidienne -----------------------
    jour_min = sub["datetime_obs"].min().normalize()
    jour_max = sub["datetime_obs"].max().normalize()
    span_jours = (jour_max - jour_min).days + 1
    moyenne_jour = len(sub) / span_jours
    print("\n--- Affirmation 1 : couverture et moyenne quotidienne ---")
    print("Question : sur combien de jours s'etend la transmission (>= 1990), et combien")
    print("de relevés produit le ciel en moyenne chaque jour sur cette periode ?")
    print(f"Du {jour_min.date()} au {jour_max.date()} = {span_jours} jours")
    print(f"Moyenne : {len(sub)} relevés / {span_jours} jours = {moyenne_jour:.2f} relevés/jour")
    print("Dossier : 8 894 jours, 9,2 relevés/jour")

    # --- 2. Le 4 juillet ------------------------------------------------
    annee_min, annee_max_pleine = jour_min.year, jour_max.year - 1  # 2014 est une annee partielle (jusqu'a mai)
    n_annees_juillet4 = annee_max_pleine - annee_min + 1
    juillet4 = sub[(sub["datetime_obs"].dt.month == 7) & (sub["datetime_obs"].dt.day == 4)]
    moyenne_juillet4 = len(juillet4) / n_annees_juillet4
    print("\n--- Affirmation 2 : le 4 juillet ---")
    print("Question : combien de relevés le 4 juillet produit-il en moyenne, une annee donnee ?")
    print(f"{len(juillet4)} relevés cumules sur les 4 juillet de {annee_min} a {annee_max_pleine}")
    print(f"({n_annees_juillet4} annees pleines ; 2014 exclu du denominateur, transmission arretee en mai)")
    print(f"Moyenne : {moyenne_juillet4:.1f} relevés/4-juillet")
    print("Dossier : 51")

    # --- 3. Jours de semaine et mois ------------------------------------
    print("\n--- Affirmation 3 : jours de semaine et mois ---")
    print("Question : quelle part des relevés (>= 1990) tombe un samedi/lundi donne, un")
    print("juillet/fevrier donne, une fois ramenee en pourcentage du total ?")
    par_jour_semaine = (sub["datetime_obs"].dt.day_name().value_counts(normalize=True) * 100).round(1)
    par_mois = (sub["datetime_obs"].dt.month_name().value_counts(normalize=True) * 100).round(1)
    print(f"Samedi : {par_jour_semaine['Saturday']}% (dossier : 17,7%)")
    print(f"Lundi  : {par_jour_semaine['Monday']}% (dossier : 12,6%)")
    print(f"Juillet : {par_mois['July']}% (dossier : 11,3%)")
    print(f"Fevrier : {par_mois['February']}% (dossier : 6,2%)")

    # --- 4. Croissance continue ? ----------------------------------------
    print("\n--- Affirmation 4 : croissance continue du volume annuel ---")
    print("Question : le nombre de relevés par annee augmente-t-il chaque annee, sans jamais")
    print("redescendre, jusqu'a la fin de la transmission ?")
    par_annee = sub.groupby(sub["datetime_obs"].dt.year).size()
    par_annee_completes = par_annee[par_annee.index <= annee_max_pleine]
    baisses = par_annee_completes[par_annee_completes.diff() < 0]
    print(par_annee_completes.to_string())
    print(f"\nAnnees en baisse par rapport a l'annee precedente : {list(baisses.index)}")
    print(
        "-> FAUX au sens strict : le volume redescend {} fois entre 1990 et {} "
        "(1991, 1996, 2000, 2005, 2006, 2009, 2010, 2013). La tendance longue est bien une "
        "forte hausse (293 -> {} relevés/an), mais elle n'est 'continue' que si on lit la "
        "courbe de loin. C'est la seule des quatre affirmations du dossier qui ne resiste pas "
        "a une verification stricte.".format(
            len(baisses), annee_max_pleine, par_annee_completes.max()
        )
    )

    # --- Chiffres manquants demandes : max journalier + rang du 4 juillet
    par_jour = sub.groupby(sub["datetime_obs"].dt.date).size().sort_values(ascending=False)
    top10 = par_jour.head(10)
    date_max = top10.index[0]
    valeur_max = top10.iloc[0]
    rang_4_juillet = next(i for i, d in enumerate(par_jour.index, start=1) if d.month == 7 and d.day == 4)
    print("\n--- Chiffres demandes en plus : maximum journalier et rang du 4 juillet ---")
    print(f"Maximum sur une seule journee : {valeur_max} relevés, le {date_max}")
    print(f"C'est lui-meme un 4 juillet -> rang du 4 juillet dans le classement des journees : {rang_4_juillet}")
    print("\nTop 10 des journees les plus chargees :")
    print(top10.to_string())

    # --- Figures ----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 4.5))
    par_annee_completes.plot(kind="bar", ax=ax, color="#3b6fa0")
    ax.set_title("Volume annuel de relevés (1990 a {}, annees pleines)".format(annee_max_pleine))
    ax.set_xlabel("Annee")
    ax.set_ylabel("Nombre de relevés")
    fig.tight_layout()
    chemin_fig = FIGURES_DIR / "phase0_volume_annuel.png"
    fig.savefig(chemin_fig, dpi=150)
    print(f"\nFigure enregistree : {chemin_fig}")

    return {
        "span_jours": span_jours,
        "moyenne_jour": moyenne_jour,
        "moyenne_juillet4": moyenne_juillet4,
        "par_jour_semaine": par_jour_semaine,
        "par_mois": par_mois,
        "par_annee_completes": par_annee_completes,
        "top10": top10,
        "rang_4_juillet": rang_4_juillet,
    }


if __name__ == "__main__":
    main()
