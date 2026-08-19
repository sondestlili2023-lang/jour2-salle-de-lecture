# Bureau d'Analyse Terrestre -- salle de lecture

Suite du dossier Klaxo-3 : la transmission (88 875 relevés) n'est plus
regardee comme des comptages, mais lue comme des temoignages.

## Utilisation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 phase0.py
```

Chaque phase telecharge la transmission si necessaire (voir `commun.py`,
meme source qu'hier) et tourne seule. Le fichier de donnees et les
environnements virtuels ne sont pas versionnes.

Les chiffres et decisions sont dans [RAPPORT.md](RAPPORT.md).
