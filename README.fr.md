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

### 🔍 **Analyse & Validation**
- **Parser** → AST JSON structuré avec messages d'erreur enrichis
- **Linter** → validation sémantique spécifique CrossFit :
  - ✅ Erreurs de syntaxe avec ligne/colonne + suggestions
  - ⚠️ Avertissements sécurité (charges lourdes, deadlifts haute répétition)
  - 📊 Analyse structure WOD (équilibre mouvements, domaines temporels)
  - 🏃 Sémantique mouvements (faisabilité EMOM, validation REST)
- **Cache intelligent** → 80%+ compilation plus rapide

### ⚙️ **Compilation & Résolution**
- **Système de modules** → import/override avec versioning
- **Compilation sessions** → résolution composants vers JSON exécutable
- **Résolution tracks/genres** → applique variantes du catalogue mouvements
- **Agrégation équipe** → scoring AMRAP/ForTime/MaxLoad

### 📤 **Export & Timeline**
- **Génération timeline** → résumés WOD pour coachs
- **Formats export** → JSON, calendrier ICS, HTML
- **Agrégation résultats** → analytics performance équipe

## Installation rapide
- Python 3 recommandé. Environnement isolé:
  - `make install` (crée `.venv` et installe `requirements.txt`)
  - ou `pip install -r requirements.txt`

## Utilisation CLI (unifiée)

### 🔍 **Analyse & Validation** (Développement)
```bash
# Lint: analyse statique avec validation spécifique CrossFit
wodc lint examples/wod/progressive_farmer.wod
# ✓ Vérifie syntaxe, structure, sémantique mouvements
# ✓ Signale avertissements charges dangereuses, timing impossible
# ✓ Suggère améliorations pour coaching

# Parse: conversion vers AST structuré (debug)
wodc parse examples/language/team_realized_session.wod
```

### ⚙️ **Compilation & Export** (Production)
```bash
# Session: résolution imports & compilation vers JSON exécutable
wodc session examples/language/team_realized_session.wod --modules-path modules --format json

# Results: agrégation données performance équipe
wodc results examples/language/team_realized_session.wod --modules-path modules

# Run: génération résumé timeline pour coachs
wodc run examples/language/team_realized_session.wod --modules-path modules
```

### 🛠️ **Utilitaires**
```bash
# Construction catalogue mouvements
wodc catalog build

# Validation syntaxe de base (vérification rapide)
wodc validate examples/language/team_realized_session.wod
```

### **Quand utiliser quoi ?**

| **Commande** | **Objectif** | **Cas d'usage** |
|--------------|-------------|-----------------|
| `wodc lint` | Analyse statique | **Développement**: détecter erreurs, valider logique CrossFit |
| `wodc session` | Compilation JSON/ICS | **Production**: générer formats finaux pour apps |
| `wodc run` | Génération timeline | **Coaching**: aperçu rapide WOD |
| `wodc results` | Agrégation équipe | **Analyse**: calculer performance équipe |

### **Exemple: Workflow Lint vs Compile**

```bash
# 1. Pendant développement : lint pour feedback immédiat
$ wodc lint my_wod.wod
WARNING: Deadlifts lourds (150kg) - vérifier progression sécurité
INFO: WOD mouvement unique - considérer options pacing
✓ Syntaxe WODCraft valide

# 2. Pour production : compilation vers formats exécutables
$ wodc session my_session.wod --format json
{
  "session": {
    "title": "Focus Force",
    "components": { ... },
    "timeline": [ ... ]
  }
}

# 3. Pour coaching : timeline rapide
$ wodc run my_session.wod
Session: Focus Force
- Warmup: Mouvement Dynamique — 300s
- Strength: Back Squat (5x5) — 1200s
- WOD: AMRAP 12:00 (Push-ups, Air Squats) — 720s
Total: 2220s (37 minutes)
```

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

La façade `sdk` offre une surface stable. Pour les usages avancés, les APIs de bas niveau sont sous `wodcraft.lang.core`.

## Tests
- Lancer: `make test` ou `pytest -q`
- Couverture incluse: parse, lint (E/W), résolution (catalog/gender), timeline, formatter.

## Spécification et architecture
- Spécification DSL: voir `WODCraft_spec.md`.
- CLI unifiée: `src/wodcraft/cli.py` (entrypoint `wodc`).
- Façade du cœur langage: `src/wodcraft/lang/core.py`.
- Grammaire/transformer de référence: `wodc_vnext/core.py` (en cours de migration sous `src/`).
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
