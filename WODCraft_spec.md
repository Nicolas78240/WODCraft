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
- **Charges / calories duales** : `@95lb/65lb`, `20/16 cal` — les valeurs H/F sont normalisées dans l'AST.
- **Progressions** : `PROGRESS("+15m/round")` documente l’augmentation automatique par tour ou intervalle.
- **Notes structurées** : `notes: "Stimulus grip"` au niveau du module, ou `notes: ["Stimulus: grip", "Focus: pacing"]` dans un bloc `wod { ... }` pour consigner les consignes et stimuli.
- **Repos** : `REST 2:00` (ou `REST 2min`) intercalé dans un bloc WOD pour marquer une pause prescrite.
- **Flags** : `SYNC`, `@shared`, `@each`.
- **Tracks** : RX, INTERMEDIATE, SCALED (choix par `--track`).
- **Catalog JSON** : comble ou surcharge les mouvements (charges, distances, reps, cals).

#### Exemple de WOD avec notes

```wod
module wod.progressive.farmer v1 {
  notes: {
    stimulus: "Grip + moteur"
    coaching: ["Garder la posture", "Respiration nasale"]
  }

  wod AMRAP 20:00 {
    notes: ["Stimulus: maintenir un effort constant", "Limiter les pauses sur le carry"]
    20/16 cal Row
    REST 2:00
    15m Farmer_Carry PROGRESS("+15m/round") @22.5kg/15kg
    notes: "Coaching: relâcher la poigne entre les tours"
  }
}
```

### Types disponibles pour `score`

- `Time`
- `Rounds`
- `Reps`
- `Distance(unit)` (ex. `Distance(m)`)
- `Load(unit)` (ex. `Load(kg)`)
- `Calories`
- `Tempo`
- `Int`, `Float`, `Bool`, `String`

### Mots-clés et conventions pratiques

- Pas de commentaires `#` : utilisez `//` ou `notes:` pour documenter les consignes.
- Le time cap s'exprime via `wod ForTime cap 10:00 { ... }` ou dans `notes` si le format n'est pas strictement FT.
- Les repos intégrés se font via `REST 2:00` au sein du bloc `wod`.
- Pour séparer des parties (A/B/C) dans un même jour, enchaînez plusieurs blocs `wod` dans le même module.

### Sessions avancées (multi-blocs + repos)

```wod
module wod.day.sample v1 {
  notes: "Stimulus pull + engine"

  wod AMRAP 7:00 {
    10 Push_up
    10 Sit_up
    10 Pull_up
    REST 2:00
  }

  wod EMOM 10:00 {
    5 Thruster @43kg/30kg
    5 Burpee
    REST 2:00
  }

  wod ForTime cap 10:00 {
    21 Snatch @43kg/30kg
    21 Pull_up
    15 Snatch @43kg/30kg
    15 Pull_up
    9 Snatch @43kg/30kg
    9 Pull_up
  }

  score ForTime {
    time: Time
    reps: Reps
  }
}
```

### Orchestration via `session`

```wod
module wod.block.a v1 { wod AMRAP 7:00 { 10 Push_up 10 Sit_up 10 Pull_up } }
module wod.block.b v1 { wod EMOM 10:00 { 5 Thruster @43kg/30kg 5 Burpee } }
module wod.block.c v1 {
  wod ForTime cap 10:00 {
    21 Snatch @43kg/30kg
    21 Pull_up
    15 Snatch @43kg/30kg
    15 Pull_up
    9 Snatch @43kg/30kg
    9 Pull_up
  }
}

session "Pull Pyramid" {
  components {
    warmup import warmup.base@v1
    wod import wod.block.a@v1
    wod import wod.block.b@v1
    wod import wod.block.c@v1
  }
  scoring {
    wod ForTime time+reps
  }
  meta {
    track = "RX"
  }
}
```

> En session, les temps de repos sont généralement portés par les modules importés (`REST` ou `notes`).

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

## 🔧 Workflow : Lint vs Compile

### 🔍 **Lint** (`wodc lint`)
**Objectif :** Analyse statique et validation sémantique sans exécution

#### Ce que fait le linter :
1. **Validation syntaxique** avec messages d'erreur enrichis :
   - Position ligne/colonne exacte
   - Contexte source affiché
   - Suggestions de correction intelligentes

2. **Validation sémantique CrossFit** :
   - **Sécurité** : charges inappropriées (ex: `50 Deadlift @200kg`)
   - **Faisabilité** : EMOM impossibles (trop de mouvements/temps)
   - **Cohérence** : REST négatifs, progressions invalides
   - **Structure** : équilibre des domaines modaux (cardio/strength/gymnastics)

#### Exemple d'output :
```bash
$ wodc lint problematic_wod.wod
WARNING: Heavy deadlifts (150kg) - verify safety progression
WARNING: EMOM might be too packed - 5 movements in 60s slots
ERROR: REST duration must be positive
INFO: No cardio movements - WOD focuses on strength/gymnastics
✓ 3 warnings, 1 error found
```

### ⚙️ **Compile/Session** (`wodc session`)
**Objectif :** Résolution complète et génération d'artefacts exécutables

#### Ce que fait la compilation :
1. **Résolution de modules** avec cache intelligent :
   - Import/override de composants versionnés
   - Résolution de dépendances
   - Cache LRU pour performances (80%+ gain)

2. **Génération d'artefacts** :
   - JSON exécutable structuré
   - Timeline pour coachs
   - Calendriers ICS
   - Agrégation résultats d'équipe

#### Workflow type :
```bash
# Développement : validation continue
wodc lint my_session.wod        # Feedback rapide

# Production : génération finale
wodc session my_session.wod --format json  # Artefacts
wodc run my_session.wod         # Timeline coaching
```

## 🤖 Usage par les agents IA
Un agent IA peut :
1. **Analyser** un fichier `.wod` avec `lint` pour validation sémantique
2. **Parser** vers AST JSON structuré (`parse`)
3. **Compiler** des sessions complètes avec résolution de modules (`session`)
4. **Adapter** WODs pour profils spécifiques via `--track` / `--gender`
5. **Exporter** vers formats multiples (HTML/ICS/JSON)
6. **Générer** de nouveaux WODs respectant la grammaire et la sémantique CrossFit

Le DSL est conçu pour être **strict mais extensible**, avec une architecture monolithique optimisée pour les agents IA permettant une **interopérabilité maximale**.

---

© Projet **WODCraft** — 2025
