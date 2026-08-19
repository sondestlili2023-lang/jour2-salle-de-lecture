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

## Phase 1 : le chiffre était vrai, la flotte est perdue

### 1. Ce que le chiffre du 4 juillet disait réellement

Le chiffre de la phase 0 dit une seule chose, rigoureusement : ce jour-là,
en moyenne, environ 51 personnes ont rempli le formulaire de témoignage,
contre 9,2 un jour ordinaire. Il ne dit rien sur *pourquoi*. Le dossier a
choisi une explication parmi plusieurs qui restent tout aussi compatibles
avec le même nombre :

- **Exposition, pas indifférence.** Le 4 juillet est un soir où une part
  inhabituellement grande de la population est dehors, dans le noir, en
  train de regarder le ciel — pour les feux d'artifice. Plus de témoins
  potentiels dehors et en train de regarder en l'air, ça fait plus de
  relevés, sans que personne soit devenu moins vigilant. C'est même
  l'inverse de l'hypothèse du dossier : ces gens-là regardaient le ciel
  activement, pas distraitement.
- **Confusion avec un phénomène humain connu.** Les feux d'artifice, les
  lanternes, les drones de spectacle produisent des lumières mobiles,
  colorées, qui se prêtent bien à une description de type "orbe",
  "cercle" ou "lumière qui change de couleur". Sur les relevés du 4
  juillet, 9,9 % (126 sur 1 272) mentionnent explicitement le mot
  *fireworks* dans leur propre texte — un mot qui n'existe nulle part
  dans le vocabulaire de la colonne `shape`, et qu'aucun comptage sur les
  dates n'aurait pu voir. Le pic du 4 juillet peut être, au moins en
  partie, un pic de confusion avec un spectacle pyrotechnique attendu,
  pas un pic de vigilance en berne.
- **Contagion locale.** Un rassemblement public (une plage, un quai, un
  parking bondé un soir de feu d'artifice) fait qu'un seul événement
  ambigu dans le ciel peut être signalé par plusieurs témoins présents
  au même endroit au même moment, gonflant le compte sans multiplier les
  événements réels.

Aucune de ces trois lectures ne soutient "la population ne prêtera pas
attention" — le chiffre du dossier dit plutôt le contraire : ce soir-là,
plus de gens que jamais regardent le ciel, activement, en groupe, et sont
déjà en train de chercher des explications à ce qu'ils y voient.

### 2. Trois relevés, tels quels

```
[7/4/1995 22:00 -- tacoma (waterfront area), wa, us -- shape: circle]
MANY PEOPLE ON DOCK WAITING FOR FIREWORKS DISPLAY SEE A RED CIRCLE
HOVERING AND THEN MOVE SLOWLY WEST.
```
Un comptage voit "+1 relevé, un 4 juillet". Le texte dit qu'il s'agit
d'une foule déjà réunie, déjà tournée vers le ciel pour une raison précise
et documentée (le feu d'artifice) — l'exact opposé d'un public inattentif.

```
[9/9/1972 21:00 -- ??, ca -- shape: rectangle]
It was well over 20 years ago, but I will never forget how unusual it
seemed to me. I still don't know just WHAT it was, maybe you can
```
La phrase s'arrête net sur "maybe you can" : la troncature à 135
caractères du service de transmission a coupé le témoignage en plein
milieu. Un comptage ne remarque jamais qu'il travaille sur des phrases
tronquées ; il traite ce relevé exactement comme un relevé complet.

```
[12/17/1996 02:30 -- redmond, wa, us -- shape: (vide)]
Woman awakened by high-pitch buzzing.  Goes outside and sees large, very
bright, circular disc w/ flat top hovering nearby. Frightened.
```
La colonne `shape` est vide pour ce relevé — un comptage sur cette
colonne perd purement et simplement ce témoignage. Le texte, lui, décrit
sans ambiguïté un disque circulaire à sommet plat. L'information existe,
mais seulement pour qui lit le texte.

### 3. La commande passée au Conseil

Un comptage peut dire *quand* les témoins écrivent. Il ne peut jamais
dire *ce qu'ils ont vu* quand la colonne structurée qui devrait le dire
est vide, fausse, ou absente. C'est la question qu'un système qui lit les
témoignages peut trancher et qu'un comptage ne tranchera jamais :

**Tâche : reconnaissance de forme à partir du témoignage.**
**Entrée :** le texte libre de la colonne `comments` d'un relevé (tronqué
à 135 caractères, tel que transmis).
**Sortie :** une forme unique, choisie parmi le vocabulaire de la colonne
`shape` (circle, light, triangle, sphere, ...).

Le fichier porte déjà, pour la quasi-totalité des relevés, la vraie forme
observée dans la colonne `shape` elle-même : elle sert de vérité terrain
pour vérifier les réponses du système, exactement comme au relevé
[12/17/1996 02:30] ci-dessus où le texte contient la réponse que la
colonne structurée a perdue.

## Acte 2 : le détecteur de formes

### État du terrain sur la colonne `shape` (vérifié depuis le fichier)

2 922 relevés sans forme, 29 valeurs distinctes, dont 18 formes réelles
dépassent 300 relevés (les deux fourre-tout `unknown` et `other` en
dépassent aussi, mais n'en sont pas). Deux doublons de sens : `round`/
`circle` et `changed`/`changing`.

### Les trois décisions (phase 3), appliquées dès la phase 2

Prises une fois pour toutes dans `formes.py`, partagé par toutes les
phases de l'acte pour que "une tâche unique" reste vraie dans le code, pas
seulement dans l'énoncé :

1. **Les 2 922 relevés sans forme sont écartés.** Rien à superviser sans
   étiquette ; les garder forcerait à inventer une 20e classe "je ne sais
   pas", ce qui n'est pas une forme observée.
2. **Les deux fourre-tout (`unknown`, `other`, 12 566 relevés à eux deux)
   sont écartés.** Ce ne sont pas des formes : ce sont des aveux
   d'incertitude du témoin ou du Bureau. Un détecteur de forme entraîné à
   répondre "unknown" apprendrait à reconnaître l'incertitude, pas une
   forme.
3. **Les doublons de sens sont fusionnés** : `round` → `circle` (2
   relevés), `changed` → `changing` (1 relevé). Même forme, autre mot.

Nécessité technique, distincte des trois décisions ci-dessus mais
appliquée dans le même module et déclarée ici : les classes retombées
sous 50 relevés après fusion (`delta`=8, `crescent`=2, `pyramid`=1,
`flare`=1, `hexagon`=1, `dome`=1 — 14 relevés en tout) sont également
écartées, sinon la découpe stratifiée train/val/test est impossible à
faire tenir sur 1 ou 2 exemples et aucun score par classe n'aurait de
sens dessus.

**Résultat : 19 classes retenues, 73 177 relevés sur 88 679 lignes bien
formées.** Découpe stratifiée 70 % / 15 % / 15 % (51 223 / 10 977 / 10 977
relevés), même graine aléatoire partout (`GRAINE = 42` dans `formes.py`).

### Phase 2 : test d'acceptation du Bureau

8 relevés réels, choisis pour couvrir 8 formes différentes (`cylinder`,
`fireball`, `formation`, `light`, `rectangle`, `cross`, `sphere`, `egg`),
soumis au montage exact de la phase 3 (`ModeleConv` : embedding → conv1d
→ batchnorm → ReLU → max-pool global → linéaire, voir `modele.py`).

**Ça a marché du premier essai**, sans qu'il ait fallu changer quoi que
ce soit : 8/8 corrects en seulement 3 itérations (Adam, lr=0,01).

| vrai | prédit |
|---|---|
| cylinder | cylinder |
| fireball | fireball |
| formation | formation |
| light | light |
| rectangle | rectangle |
| cross | cross |
| sphere | sphere |
| egg | egg |

![Perte sur les 8 relevés](figures/phase2_perte.png)

Convergence si rapide parce que le vocabulaire est minuscule (construit
sur ces 8 phrases seules, pas sur les 7 281 mots du vrai vocabulaire
d'entraînement) : presque chaque mot n'apparaît que dans une seule des 8
phrases, ce qui rend la mémorisation quasi triviale par recherche de mot
unique.

**Ce que ce test prouve :** la plomberie fonctionne — l'embedding, la
convolution, la retropropagation et l'optimiseur peuvent effectivement
faire baisser la perte à zéro erreur sur cette architecture.
**Ce qu'il ne prouve absolument pas :** que le modèle généralisera sur
73 177 relevés avec un vocabulaire de 7 281 mots partagés entre 19
classes, où la mémorisation par mot unique ne marche plus.

### Phase 3 : battre le service statistique

Même découpe, mêmes classes que la phase 2 : 19 classes, 73 177 relevés
(train 51 223 / val 10 977 / test 10 977, 70 %/15 %/15 % stratifiés),
vocabulaire de 7 281 mots (construit sur le train seul, fréquence ≥ 3,
pour ne pas fuiter d'information du val/test).

Montages (`modele.py`), 10 époques, Adam/AdamW, meilleure époque sur
validation retenue (arrêt anticipé) :

- **Linéaire** (service statistique) : sac-de-mots (comptages) → une
  couche linéaire.
- **ModeleConv** (le nôtre) : embedding (dim 100) → conv1d (noyau 3) →
  batchnorm → ReLU → concaténation max-pool/moyenne-pool → dropout (0,4)
  → linéaire. Le dropout et la concaténation moyenne+max ont été
  nécessaires : une première version (max-pool seul, sans dropout)
  surapprenait dès la 2e époque et finissait *derrière* le linéaire
  (0,529 contre 0,541) — corrigé en ajoutant du dropout et un signal de
  moyenne en plus du maximum.

| Modèle | Accuracy (test) |
|---|---|
| Toujours "light" (référence) | 0,244 |
| Linéaire (service statistique) | 0,542 |
| **ModeleConv (le nôtre)** | **0,550** |

Le nôtre passe devant, mais l'écart est modeste (+0,8 point). Explication
raisonnable : les textes sont très courts (12 mots en médiane, tronqués à
135 caractères) et beaucoup de témoins citent le nom de la forme dans leur
texte (voir phase 9) — un simple comptage de mots capte déjà l'essentiel
du signal sur des phrases aussi télégraphiques ; l'ordre local des mots,
que seule la convolution voit, n'ajoute qu'un supplément.

![Linéaire -- apprentissage vs validation](figures/phase3_lineaire.png)
![ModeleConv -- apprentissage vs validation](figures/phase3_conv.png)

Du texte brut au premier nombre qui entre dans le réseau (exemple pris
dans le jeu de test) :

```
Texte brut   : ((HOAX))  JUST FOR THE RECORD THESE TIANGLE CRAFTS HAVE BEEN AROUND FOR SOME TIME
Tokenisé     : ['hoax', 'just', 'for', 'the', 'record', 'these', 'tiangle', 'crafts', ...]
Identifiants : [3016, 3414, 2555, 6384, 5159, 6396, 1, 1481, ...]
```
`tiangle` (faute de frappe pour "triangle") n'est pas dans le vocabulaire
d'entraînement → identifiant 1 (`<unk>`). Le premier mot du vocabulaire,
`hoax`, devient un vecteur de 100 nombres (`embed.weight[3016]`) : c'est
le premier nombre qui entre réellement dans le réseau, tout le reste
(convolution, pooling, linéaire) ne fait que le transformer.

### Phase 4 : le carnet de pannes

Même montage que la phase 3 (`ModeleConv`), même découpe, cassé
volontairement trois fois, une fois à chaque fois à partir d'un modèle
neuf (même graine). Référence saine pour comparaison : perte train
2,04 → 1,55, perte val 1,69 → 1,57 sur 5 époques.

**Fiche 1 — évaluation faite sans `modele.eval()`**
- *Geste* : après l'entraînement de l'époque, évaluer directement sans
  remettre le modèle en mode évaluation. Dropout (0,4) reste actif et la
  batchnorm continue à se caler sur les statistiques du lot en cours
  (ici des lots de 4, pour que l'effet ne se noie pas dans la moyenne
  d'un unique bloc de 10 977 exemples).
- *Signature* : la perte de validation "correcte" (`model.eval()`)
  descend de 1,69 à 1,58 ; la même donnée, évaluée en mode train, reste
  systématiquement 10 à 15 % plus haute à chaque époque (1,89 → 1,69).
  Rien n'a changé dans les données entre les deux courbes — seul le mode
  du modèle diffère.
  ![Panne 1](figures/phase4_panne1.png)
- *Test en moins d'une minute* : repasser deux fois de suite exactement
  la même entrée dans le modèle sans le retoucher. En mode `eval()`, les
  deux sorties sont rigoureusement identiques (déterministe). En mode
  `train()`, elles diffèrent (`torch.allclose` renvoie `False`) : la
  seule explication possible pour deux sorties différentes sur une
  entrée identique est un mécanisme stochastique encore actif — dropout,
  donc `model.eval()` n'a pas été appelé.

**Fiche 2 — dictionnaire de décodage incohérent avec l'entraînement**
- *Geste* : entraîner et calculer la perte normalement (indices
  cohérents de bout en bout), mais décoder les indices prédits en noms
  de forme avec un dictionnaire reconstruit dans un autre ordre (classes
  triées par fréquence décroissante au lieu de l'ordre alphabétique
  utilisé à l'entraînement) — le classique du label-encoder régénéré
  entre deux versions du code sans être resynchronisé.
- *Signature* : la perte d'entraînement baisse proprement (2,04 → 1,55)
  et l'accuracy calculée sur les indices bruts monte normalement
  (0,51 → 0,54). L'accuracy calculée en décodant les noms avec le
  mauvais dictionnaire reste plate autour de 0,02 — sous la référence
  "au hasard" (1/19 ≈ 0,053), puisqu'une permutation fixe n'a presque
  aucun point fixe.
  ![Panne 2](figures/phase4_panne2.png)
- *Test en moins d'une minute* : comparer, sur le même lot, l'accuracy
  indice-contre-indice à l'accuracy nom-contre-nom. Si la première est
  correcte et haute pendant que la seconde reste proche de zéro tout au
  long de l'entraînement (au lieu de démarrer bas puis de progresser
  comme dans la panne 1), c'est un problème de décodage, pas
  d'apprentissage : le modèle prédit juste, on le lit mal.

**Fiche 3 — `optim.step()` jamais appelé**
- *Geste* : calculer `perte.backward()` à chaque lot mais oublier
  `optim.step()`. Les gradients sont bien calculés, mais aucune valeur
  du modèle ne bouge jamais.
- *Signature* : la perte reste figée autour de 4,0 sur les 5 époques
  (4,001 / 4,000 / 4,007 / 3,998 / 3,992), sans tendance, seulement le
  bruit de dropout/batchnorm d'un lot à l'autre — comparée à la
  référence saine qui descend franchement de 2,04 à 1,55.
  ![Panne 3](figures/phase4_panne3.png)
- *Test en moins d'une minute* : comparer un tenseur de poids (ici la
  couche de sortie) avant et après l'entraînement avec
  `torch.equal(...)`. `True` = aucune mise à jour n'a jamais eu lieu,
  donc soit `optim.step()` n'est jamais appelé, soit le taux
  d'apprentissage est nul — dans les deux cas, pas la même famille de
  panne que 1 ou 2, où les poids bougent bel et bien.

**Ce que le carnet permet de trancher rapidement, face à une courbe
inconnue :** perte d'entraînement qui descend + perte d'évaluation qui
descend un peu moins vite mais dans le même sens → suspecter la panne 1
(mode du modèle) ; perte d'entraînement qui descend mais qu'aucune
métrique côté "vrai monde" (noms, pas indices) ne suit → panne 2
(décodage) ; perte qui ne bouge absolument pas d'un bout à l'autre →
panne 3 (aucune mise à jour des poids).
