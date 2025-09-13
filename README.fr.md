# WODCraft

WODCraft est un DSL (Domain‑Specific Language) pour décrire, valider et exporter des WODs (Workouts of the Day). Il fournit un outil CLI unifié pour parser, linter, compiler des sessions et exporter (JSON/ICS), avec prise en charge des niveaux et genres via un catalogue de mouvements.

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

## Utilisation CLI (unifiée)
- Valider: `wodc validate examples/language/team_realized_session.wod`
- Parser: `wodc parse examples/language/team_realized_session.wod`
- Compiler une session → JSON/ICS: `wodc session examples/language/team_realized_session.wod --modules-path modules --format json`
- Agréger le réalisé d’équipe: `wodc results examples/language/team_realized_session.wod --modules-path modules`
- Construire le catalogue: `wodc catalog build`

Raccourcis Makefile: `make help` (venv, install, test, catalog-build, vnext-validate, vnext-session, vnext-results, build-dist).

## Intégration Développeur
- Installer: `pip install wodcraft`
- Importer le SDK: `from wodcraft import sdk`
- Usage courant:

```python
from pathlib import Path
from wodcraft import sdk

text = Path("examples/language/team_realized_session.wod").read_text()

# Valider
ok, err = sdk.validate(text)
if not ok:
    raise ValueError(err)

# Parser en AST (dict)
ast = sdk.parse(text)

# Compiler la première session (résolution des modules depuis ./modules)
compiled = sdk.compile_session(text, modules_path="modules")

# Exporter ICS (nécessite exports.ics dans la session)
ics_str = sdk.export_ics(compiled)

# Agréger le réalisé d’équipe si présent
agg = sdk.results(text, modules_path="modules")

# Produire un résumé timeline
timeline = sdk.run(text, modules_path="modules")
```

La façade `sdk` offre une surface stable (sans legacy/vNext). Pour les usages avancés, les APIs de bas niveau sont sous `wodcraft.lang.core`.

## Tests
- Lancer: `make test` ou `pytest -q`
- Couverture incluse: parse, lint (E/W), résolution (catalog/gender), timeline, formatter.

## Spécification et architecture
- Spécification DSL: voir `WODCraft_spec.md`.
- CLI unifiée: `src/wodcraft/cli.py` (entrypoint `wodc`).
- Cœur langage: `src/wodcraft/lang/core.py` (façade sur vNext).
- vNext core: `wodc_vnext/core.py` (modules/sessions/types), en cours de migration sous `src/`.
- Exemples sous `examples/` et modules sous `modules/`. Catalogue de mouvements: `data/movements_catalog.json`.

## Exemples (Langage / Programmation)
- `examples/language/programming_plan.wod`: bloc “Coach Programming” minimal
- `examples/language/team_realized_session.wod`: session avec `team` + `realized` pour l’agrégation

## Roadmap
- Formatter avancé (indentation/blocs), macros et shorthands (`21-15-9`).
- Versionner la grammaire et `wodc fmt` canonique.
- Timer exécutable pour usage en box.

## Contribuer
- Lisez `AGENTS.md` (conventions, structure, commandes).
- Ouvrez des PRs focalisées avec exemples CLI et artefacts d’export.

## 📜 License

- **Code (DSL, outils, générateurs)** : [Apache 2.0](./LICENSE)  
- **Contenus (docs, liste de mouvements, exemples, images/vidéos)** : [CC-BY-SA 4.0](./LICENSE-docs)  

En résumé :  
Vous pouvez utiliser librement WODCraft dans vos projets, y compris commerciaux, tant que vous citez la source.  
Les contenus (mouvements, docs, etc.) doivent rester ouverts et sous la même licence CC-BY-SA.

---

© 2025 Nicolas Caussin - caussin@aumana-consulting.com
