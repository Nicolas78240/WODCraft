# WODCraft Specification v0.1

## 🎯 Objectif du projet
WODCraft est un **langage spécifique au domaine (DSL)** conçu pour **décrire, partager et automatiser les WODs (Workouts of the Day)**, en particulier pour le CrossFit et les disciplines similaires.

Ce projet vise à :
- Fournir une **syntaxe standardisée** et lisible par les coachs ET les développeurs.
- Permettre la **génération automatique** de formats variés : timeline (timer), HTML, PDF, ICS (calendrier), JSON (API).
- Normaliser les variations RX / Scaled / Intermédiaire, hommes / femmes, et faciliter les adaptations.
- Servir de **socle pour des agents IA** capables d’analyser, générer ou adapter des WODs automatiquement.

---

## 🏗 Structure du langage

### Sections principales
- `WOD "Nom"` : titre du WOD
- `TEAM N` : taille de l’équipe
- `CAP T` : temps limite global
- `SCORE` : règles de scoring
- `TRACKS [RX, SCALED, …]` : niveaux disponibles
- `BUYIN { … }` et `CASHOUT { … }` : parties avant et après le bloc principal
- `REST T` : périodes de repos
- `BLOCK … { … }` : bloc principal (AMRAP, EMOM, FT, RFT, CHIPPER, TABATA, INTERVAL)

### Exemples de blocs
```wod
BLOCK AMRAP 12:00 WORK split:any {
  12 wall_balls @9kg SYNC;
  10 box_jumps @24in;
  200m run;
}
```

### Variantes supportées
- **Duals** : `@43/30kg`, `15/12 cal`, `400/300m`, `21/15` (résolus selon `--gender`).
- **Flags** : `SYNC`, `@shared`, `@each`.
- **Tracks** : RX, INTERMEDIATE, SCALED (choix par `--track`).
- **Catalog JSON** : comble ou surcharge les mouvements (charges, distances, reps, cals).

---

## 🔧 Outillage CLI

Le binaire `wodc` fournit :

- `parse` → transforme un fichier `.wod` en AST JSON.  
- `lint` → vérifie la validité et signale les incohérences (alias, charges douteuses, mouvements inconnus).  
- `run` → génère une timeline exécutable (JSON ou texte).  
- `export` → exporte en `json`, `html` ou `ics` (calendrier).  

### Exemples
```bash
# Lint programmation (langage)
wodc lint examples/language/program_12w.wod

# Compiler une session (langage)
wodc session examples/language/team_realized_session.wod --modules-path modules --format json

# Construire le catalogue
wodc catalog build
```

---

## 📂 Fichiers du projet
- `wodc` → CLI unifiée (parse, lint, validate, session, results, catalog build).
- `box_catalog.json` → catalog de mouvements avec standards RX/Scaled et H/F.
- `examples/language/*.wod` → exemples de programmation/sessions/realized.
- `exports/*.html|ics` → exemples d’exports.

---

## 🚀 Perspectives
- Ajouter macros, imbrications, shorthands (`21-15-9 thrusters + pullups`).
- Versionner la grammaire (`LANG 0.4` dans l’entête).  
- Intégrer un **formatter** (`wodc fmt`) pour uniformiser les fichiers.  
- Générer automatiquement un **timer** utilisable en box.

---

## 🤖 Usage par les agents IA
Un agent IA peut :  
1. Lire un fichier `.wod` et en obtenir l’AST JSON (`parse`).  
2. Vérifier la validité (`lint`).  
3. Adapter un WOD pour un profil (ex: femme, scaled) via `--track` / `--gender`.  
4. Exporter le WOD dans un format exploitable (HTML/ICS/JSON).  
5. Générer de nouveaux WODs en respectant la grammaire.  

Le DSL est conçu pour être **strict mais extensible**, afin de permettre une **interopérabilité maximale** avec des outils d’IA et des systèmes externes.

---

© Projet **WODCraft** — 2025
