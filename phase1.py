"""Phase 1 : preuves a l'appui de la page ecrite dans RAPPORT.md.

Phase 1 elle-meme est "sans code" (une page d'analyse qualitative). Ce
script ne fait qu'extraire, de maniere reproductible, les chiffres et les
trois relevés verbatim cites dans cette page -- pour qu'ils restent
verifiables et ne soient pas retapes a la main depuis le fichier source.
"""
from commun import charger_releves, parser_dates


def main():
    df, total, ecartees = charger_releves()
    df = parser_dates(df)
    sub = df.dropna(subset=["datetime_obs"])
    j4 = sub[(sub["datetime_obs"].dt.month == 7) & (sub["datetime_obs"].dt.day == 4)]

    print("=== Phase 1 : preuves a l'appui ===")
    fireworks = j4[j4["comments"].str.contains("firework", case=False, na=False)]
    part = 100 * len(fireworks) / len(j4)
    print(f"Relevés du 4 juillet mentionnant explicitement 'firework(s)' : "
          f"{len(fireworks)}/{len(j4)} = {part:.1f}%")
    print("(les feux d'artifice ne sont meme pas dans le vocabulaire de la colonne shape ;")
    print(" ce chiffre ne peut venir que d'avoir lu le texte.)")

    print("\n--- Les trois relevés cites dans RAPPORT.md ---")
    for idx in (68281, 88431, 20611):
        r = df.loc[idx]
        print(f"\n[{idx}] {r['datetime']} -- {r['city']}, {r['state']}, {r['country']} "
              f"-- shape declare : {r['shape'] or '(vide)'}")
        print(f"    {r['comments']}")


if __name__ == "__main__":
    main()
