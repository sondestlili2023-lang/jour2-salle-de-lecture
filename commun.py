"""Constantes et utilitaires partages entre les scripts phaseN.py.

Meme transmission qu'hier (Jour1, projet1/Jour1-1_reception_des_releves) :
88 875 relevés, 11 colonnes sans en-tete, meme URL de telechargement.
"""
import csv
import urllib.request
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent
DATA_DIR = RACINE / "data"
DATA_DIR.mkdir(exist_ok=True)

URL_TRANSMISSION = (
    "https://raw.githubusercontent.com/planetsig/ufo-reports/master/"
    "csv-data/ufo-complete-geocoded-time-standardized.csv"
)
CSV_BRUT = DATA_DIR / "releves_klaxo3.csv"

# Le manifeste retrouve a part (l'ordre des 11 champs, sans en-tete dans le fichier)
COLONNES = [
    "datetime",
    "city",
    "state",
    "country",
    "shape",
    "duration_seconds",
    "duration_hours_min",
    "comments",
    "date_posted",
    "latitude",
    "longitude",
]


def telecharger_si_absent():
    """Recupere la transmission si elle n'est pas deja sur le disque."""
    if CSV_BRUT.exists():
        return CSV_BRUT
    print(f"Telechargement de la transmission depuis {URL_TRANSMISSION} ...")
    urllib.request.urlretrieve(URL_TRANSMISSION, CSV_BRUT)
    print(f"Transmission enregistree dans {CSV_BRUT}")
    return CSV_BRUT


def charger_releves():
    """Charge la transmission en DataFrame, en ecartant les lignes mal formees.

    Retourne (df, total_lignes, lignes_ecartees) sans jamais deviner un champ
    manquant : une ligne qui n'a pas exactement 11 champs est mise de cote.
    """
    telecharger_si_absent()

    gardees = []
    ecartees = []
    total = 0
    with open(CSV_BRUT, newline="", encoding="utf-8", errors="replace") as f:
        for ligne in csv.reader(f):
            total += 1
            if len(ligne) == len(COLONNES):
                gardees.append(ligne)
            else:
                ecartees.append(ligne)

    df = pd.DataFrame(gardees, columns=COLONNES)
    return df, total, ecartees


def parser_dates(df):
    """Ajoute datetime_obs (colonne `datetime` parsee) et date_posted parsee.

    Le format source ecrit parfois '24:00' pour minuit (1220 lignes) : un
    parsing strict les rejette (NaT) alors que la date est parfaitement
    lisible. On les recupere en remplacant '24:00' par '00:00' du jour
    suivant plutot que de perdre 1220 lignes en silence.
    """
    df = df.copy()
    etait_24h = df["datetime"].str.endswith("24:00")
    dt_normalise = df["datetime"].str.replace(" 24:00", " 00:00", regex=False)
    parsed = pd.to_datetime(dt_normalise, format="%m/%d/%Y %H:%M", errors="coerce")
    df["datetime_obs"] = parsed.where(~etait_24h, parsed + pd.Timedelta(days=1))
    df["date_posted_parsed"] = pd.to_datetime(df["date_posted"], format="%m/%d/%Y", errors="coerce")
    return df
