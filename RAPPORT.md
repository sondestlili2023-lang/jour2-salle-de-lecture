# RAPPORT.md -- Bureau d'Analyse Terrestre, salle de lecture

## Phase 0 : refaire les calculs du disparu

### Choix de la date

La transmission porte deux dates : `datetime` (l'instant ou le temoin a
regarde le ciel) et `date_posted` (l'instant ou le Bureau a publie le
dossier). J'utilise **`datetime`**.

Les quatre affirmations du dossier decrivent toutes un comportement du
ciel et des temoins -- quel jour la population regarde en l'air, quel
mois, quel jour precis produit un pic. C'est un phenomene ancre sur
l'instant de l'observation, pas sur le delai administratif que met le
Bureau a traiter un dossier (delai tres irregulier : voir le repo d'hier,
`Jour1-1_reception_des_releves/phase8_chronologie.py`, ou un relevé de
1950 est publie en 2004). Verification a posteriori : les quatre
pourcentages obtenus avec `datetime` tombent exactement sur ceux du
dossier, ce qui confirme que c'est la bonne colonne.

Detail de parsing : 1 220 lignes ecrivent l'heure `24:00` (minuit) au
lieu de `00:00` le lendemain. Un parsing strict les rejette silencieusement
(`NaT`). Je les recupere en reportant `24:00` sur `00:00` du jour suivant
plutot que de perdre 1 220 relevés sans le dire. Sans cette correction, la
moyenne quotidienne tombe a 9,05/jour au lieu de 9,2 -- c'est cette
correction qui fait matcher le chiffre du dossier.

Fenetre retenue : relevés dont `datetime` >= 1990-01-01. 235 relevés
anterieurs existent dans le fichier (jusqu'a 1906) mais sont trop rares et
trop irreguliers pour representer un rythme d'observation ; le dossier les
exclut implicitement en situant sa fenetre a partir de 1990.

### Les quatre affirmations reproduites

| # | Question a laquelle le chiffre repond | Calcul | Dossier | Obtenu |
|---|---|---|---|---|
| 1 | Sur combien de jours s'etend la transmission depuis 1990, et combien de relevés le ciel produit-il en moyenne par jour sur cette fenetre ? | `(dernier jour - 1990-01-01) + 1` ; `n_relevés / n_jours` | 8 894 jours, 9,2/jour | **8 894 jours, 9,16/jour** |
| 2 | Combien de relevés un 4 juillet produit-il en moyenne, une annee donnee ? | somme des relevés sur tous les 4 juillet 1990-2013 (2014 exclu, transmission arretee en mai), divisee par 24 annees | 51 | **50,8** |
| 3a | Quelle part des relevés tombe un samedi (resp. un lundi) ? | `value_counts(normalize=True)` sur le jour de semaine | 17,7 % / 12,6 % | **17,7 % / 12,6 %** |
| 3b | Quelle part des relevés tombe en juillet (resp. en fevrier) ? | idem sur le mois | 11,3 % / 6,2 % | **11,3 % / 6,2 %** |
| 4 | Le volume annuel augmente-t-il chaque annee sans jamais redescendre, jusqu'a la fin de la transmission ? | diff() annee sur annee, 1990-2013 (annees pleines) | "croit continument" | **FAUX au sens strict : 8 baisses** (1991, 1996, 2000, 2005, 2006, 2009, 2010, 2013) |

Les trois premieres affirmations sont exactes au dixieme pres. La
quatrieme est la seule qui ne resiste pas a une verification stricte : le
volume annuel redescend 8 fois entre 1990 et 2013. La tendance longue est
bien une forte hausse (293 relevés en 1990, 7 924 en 2012), mais elle
n'est "continue" que si on lit la courbe de loin -- l'analyste a
probablement regarde la forme generale sans verifier annee par annee.

### Chiffres demandes en plus

- **Maximum sur une seule journee : 206 relevés, le 4 juillet 2010.**
- **Rang du 4 juillet dans ce classement : 1er.** Le jour le plus charge
  de toute la transmission (24 ans, 8 894 jours) est lui-meme un 4
  juillet. Trois autres 4-juillet figurent aussi dans le top 5 (2012 :
  191, rang 3 ; 2013 : 180, rang 4 ; 2011 : 155, rang 5).

### Top 10 des journees les plus chargees

| Rang | Date | Relevés |
|---|---|---|
| 1 | 2010-07-04 | 206 |
| 2 | 1999-11-16 | 195 |
| 3 | 2012-07-04 | 191 |
| 4 | 2013-07-04 | 180 |
| 5 | 2011-07-04 | 155 |
| 6 | 2009-09-19 | 129 |
| 7 | 2014-01-01 | 99 |
| 8 | 2013-12-31 | 96 |
| 9 | 2004-10-31 | 94 |
| 10 | 2009-07-04 | 88 |

Le soir de novembre "195 personnes" et les pics d'Halloween / Nouvel An
mentionnes en phase 1 sont deja visibles ici (1999-11-16, 2004-10-31,
2013-12-31, 2014-01-01) : le 4 juillet n'est pas le seul jour ou le ciel
attire l'attention, seulement le plus frequent des jours qui le font.

### Courbe du volume annuel

![Volume annuel de relevés](figures/phase0_volume_annuel.png)

### Reproductibilite

`python3 phase0.py` (apres `pip install -r requirements.txt`) telecharge
la transmission si absente et affiche tous les chiffres ci-dessus, sur
une machine neuve, en quelques secondes.
