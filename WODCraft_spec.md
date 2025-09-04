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

Le binaire `wodc_merged.py` fournit :

- `parse` → transforme un fichier `.wod` en AST JSON.  
- `lint` → vérifie la validité et signale les incohérences (alias, charges douteuses, mouvements inconnus).  
- `run` → génère une timeline exécutable (JSON ou texte).  
- `export` → exporte en `json`, `html` ou `ics` (calendrier).  

### Exemples
```bash
# Lint avec catalog et track/gender
python wodc_merged.py lint examples/team_mixer.wod   --catalog box_catalog.json --track RX --gender female

# Run en timeline JSON
python wodc_merged.py run examples/team_mixer.wod   --catalog box_catalog.json --track RX --gender female --format json

# Export HTML
python wodc_merged.py export examples/team_mixer.wod   --to html -o team_mixer.html   --catalog box_catalog.json --track RX --gender female
```

---

## 📂 Fichiers du projet
- `wodc_merged.py` → CLI principale (parse, lint, run, export).
- `box_catalog.json` → catalog de mouvements avec standards RX/Scaled et H/F.
- `examples/*.wod` → exemples de WODs (team_mixer, waterfall_trio, synchro_emom…).  
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
