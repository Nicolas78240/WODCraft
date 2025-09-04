# WODCraft

WODCraft est un DSL (Domain‑Specific Language) pour décrire, valider et exporter des WODs (Workouts of the Day). Il fournit un outil CLI unique pour parser, linter, simuler (timeline) et exporter (JSON/HTML/ICS) des entraînements, avec prise en charge des niveaux (RX/Scaled/Intermediate) et des genres (H/F).

## Pourquoi
- Standardiser l’écriture des WODs, lisible par les coachs et les outils.
- Automatiser la génération de formats utiles (timer, calendrier, web, API).
- Normaliser les variantes (tracks, dual reps/cals/charges) via un catalogue JSON.
- Servir de base à des agents IA pour analyser/générer des WODs.

## Aperçu du DSL
```wod
WOD "Team Mixer"
TEAM 2
TRACKS [RX, INTERMEDIATE, SCALED]
CAP 20:00

BUYIN {
  400m run;
}

BLOCK AMRAP 12:00 WORK split:any {
  12 wall_balls @9kg SYNC;
  10 box_jumps @24in;
  200m run;
}

CASHOUT {
  50 double_unders @each;
}
```
La grammaire complète et les règles sont décrites dans WODCraft_spec.md (source de vérité).

## Fonctionnalités
- Parser → AST JSON structuré.
- Linter → erreurs/avertissements (ex: E010 REST>0, E020 EMOM sans slot, W001 mouvement inconnu, W002 charge suspecte, W050 alias).
- Résolution → applique `--track`/`--gender` et un `--catalog` JSON.
- Timeline → `run` produit une séquence d’événements (texte ou JSON).
- Export → `export` vers `json`, `html`, `ics`.
- Formatage → `fmt` (normalisation minimale sûre des `.wod`).

## Installation rapide
- Python 3 recommandé. Environnement isolé:
  - `make install` (crée `.venv` et installe `requirements.txt`)
  - ou `pip install -r requirements.txt`

## Utilisation CLI
- Parser: `python3 wodc_merged.py parse team_mixer.wod -o out/out.json`
- Lint: `python3 wodc_merged.py lint team_mixer.wod --catalog box_catalog.json --track RX --gender female`
- Timeline (texte): `python3 wodc_merged.py run team_mixer.wod --format text`
- Export HTML: `python3 wodc_merged.py export team_mixer.wod --to html -o out/wod.html`
- Formatage: `python3 wodc_merged.py fmt team_mixer.wod -i`

Raccourcis Makefile: `make help` (parse, lint, run, export-*, demo, check-spec, fmt, venv, install).

## Tests
- Lancer: `make test` ou `pytest -q`
- Couverture incluse: parse, lint (E/W), résolution (catalog/gender), timeline, formatter.

## Spécification et architecture
- Spécification DSL: voir `WODCraft_spec.md`.
- Implémentation: `wodc_merged.py` (grammaire Lark + transformer, linter, timeline, exports, fmt).
- Exemples: fichiers `.wod` à la racine (team_mixer, waterfall_trio, …). Catalogue: `box_catalog.json`.

## Roadmap
- Formatter avancé (indentation/blocs), macros et shorthands (`21-15-9`).
- Versionner la grammaire et `wodc fmt` canonique.
- Timer exécutable pour usage en box.

## Contribuer
- Lisez `AGENTS.md` (conventions, structure, commandes).
- Ouvrez des PRs focalisées avec exemples CLI et artefacts d’export.

© WODCraft — 2025
