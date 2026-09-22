# WODCraft 1.0 — Proposition

> Statut : brouillon pour validation · 2026-09-22
> Objet : refonte complète du langage et du compilateur WODCraft, avec l'objectif d'en faire un standard ouvert.

## 1. L'idée de départ, conservée

WODCraft reste **un vrai langage avec un vrai compilateur** : on écrit un WOD, le compilateur le vérifie
(syntaxe, unités, cohérence format/score, mouvements connus, plausibilité) et produit une représentation
structurée exploitable par des applis, des timers, un calendrier ou une IA.

Ce qui change : la syntaxe. Elle doit être celle qu'on lit au tableau blanc, pas celle d'un programmeur.
**Stricte ne veut pas dire technique** — `21-15-9` est une notation parfaitement précise, il suffit de la définir.

## 2. Principes

1. **Test du tableau blanc** — tout fichier valide peut être affiché tel quel au mur de la box et compris par un athlète.
2. **Strict et vérifié** — rien d'ambigu n'est accepté en silence. Toute erreur est localisée (ligne, colonne), codée et accompagnée d'une suggestion.
3. **Notations métier natives** — `21-15-9`, `3 rounds`, `43/30 kg`, `15/12 cal`, `EMOM 10`, `E2MOM`, `every 3:00 x 5`, `5x5 @ 75%`.
4. **Le JSON compilé est le contrat** — c'est lui que les applis échangent, décrit par un JSON Schema versionné.
5. **Personnalisable à l'athlète** — un même WOD se résout pour une catégorie (H/F), un niveau (Rx/Scaled), des unités (kg/lb) et des 1RM.
6. **Un seul niveau obligatoire : le WOD** — séance et programmation sont des couches au-dessus, optionnelles.

## 3. Le langage par l'exemple

### 3.1 Les benchmarks

```wod
# Fran
For time, cap 10:00
21-15-9
  Thruster 43/30 kg
  Pull-up

Scaled:
  Thruster 30/20 kg
  Pull-up -> Jumping pull-up
```

```wod
# Helen
3 rounds for time
  400 m Run
  21 Kettlebell swing 24/16 kg
  12 Pull-up
```

```wod
# Murph
For time, cap 60:00
vest: 9/6 kg
  1 mi Run
  100 Pull-up
  200 Push-up
  300 Air squat
  1 mi Run
note: Partitionner pull-ups, push-ups et squats librement.
```

```wod
# Cindy
AMRAP 20
  5 Pull-up
  10 Push-up
  15 Air squat
```

### 3.2 Les autres formats courants

```wod
# EMOM alterné
EMOM 12
  Odd: 12/10 cal Row
  Even: 10 Burpee

# Intervalles
Every 4:00 x 4
  400 m Run
  max Burpee
score: reps

# Buy-in / cash-out, en équipe
Teams of 2, for time, cap 20:00
Buy-in:
  1000 m Row (split)
4 rounds
  12 Wall ball 9/6 kg (sync)
  10 Box jump 24/20 in
Cash-out:
  50 Double-under (each)

# Force
Back squat 5x5 @ 75%
Rest 2:00 between sets

Clean: build to heavy 1 in 15:00
```

### 3.3 Une séance complète

```wod
# Mardi 23 septembre
level: rx

## Warm-up
2 rounds
  200 m Run
  10 Air squat
  5 Inchworm

## Strength
Back squat 5x5 @ 75%

## Metcon
use girls/fran

## Cool-down
5:00 Bike, easy
```

`use girls/fran` insère un WOD de la bibliothèque standard (Girls, Heroes, Open).

## 4. Règles du langage (résumé)

| Élément | Règle |
|---|---|
| Titre | `# Titre` = un WOD ; s'il contient des `## Sections`, c'est une séance. |
| Ligne de format | `For time`, `AMRAP n`, `EMOM n`, `EnMOM n`, `Every mm:ss x n`, `Tabata`, `n rounds [for time]`, `21-15-9`, `Max load`, `build to heavy n`, `Death by`. Options après virgule : `cap mm:ss`, `Teams of n`. |
| Ligne de mouvement | `[quantité] Mouvement [paramètre] [(modificateur)]` — ex. `21 Kettlebell swing 24/16 kg (sync)`. |
| Imbrication | Indentation de 2 espaces. Facultative quand il n'y a qu'un bloc (le cas le plus courant). |
| Double H/F | `43/30 kg` = hommes/femmes (convention CrossFit). Une seule valeur = identique pour tous. |
| Quantités | reps `21`, distance `400 m` / `1 mi` / `5 km`, calories `15/12 cal`, durée `30 s` / `2 min` / `1:30`, `max`. |
| Paramètres | charge `kg` `lb` `pood`, `@ 75%` (de la 1RM du mouvement, ou `@ 75% Back squat`), hauteur `in` `cm`, `bw`. |
| Unités | `m` = **toujours** mètres ; minutes = `min` ou `mm:ss`. Un nombre nu après `AMRAP`/`EMOM` = minutes. Charges sans unité acceptées seulement si `units:` est défini (fichier ou config de la box). |
| Méta | `key: value` : `cap`, `score`, `units`, `level`, `vest`, `note`, `stimulus`, `tags`. |
| Niveaux | `Scaled:` / `Foundations:` ne listent que les différences ; `A -> B` remplace un mouvement. |
| Score | Déduit du format (For time → temps, AMRAP → rounds + reps, Every x N avec `max` → somme de reps, Max load → charge) ; surchargeable par `score:`. |
| Commentaires | `// …` ; `note:` pour ce qui doit être affiché. |
| Noms de mouvements | Naturels et insensibles à la casse/pluriel : `Pull-up`, `pull ups`, `Tractions` → `pull_up` via le catalogue (alias FR/EN). |

## 5. Le compilateur

### 5.1 Pipeline

```
texte .wod ─► Lexer ─► Parser ─► Résolution ─► Typage ─► Vérifs métier ─► Estimation ─► Émetteurs
               lignes   arbre     use/, noms    unités     format/score    durée,          JSON, tableau,
               + spans  + spans   → catalogue   vs mvt     niveaux, H/F    charge          Markdown, ICS,
                                                                                            timer, fmt
```

- Parser **écrit à la main**, orienté lignes, avec reprise sur erreur (il signale *toutes* les erreurs d'un coup, pas seulement la première). Plus simple à porter en TypeScript qu'une grammaire Lark, et bien meilleurs messages.
- Chaque nœud garde sa position source : les diagnostics pointent la bonne ligne et colonne (éditeur, IA).
- Le **catalogue de mouvements** fait partie du standard : identifiant, noms et alias FR/EN, famille (M/G/W), type de paramètre attendu (charge, hauteur, distance, calories, aucun), charges Rx de référence, cadence moyenne pour les estimations.

### 5.2 Ce que le compilateur vérifie

| Code | Niveau | Exemple | Message |
|---|---|---|---|
| E001 | erreur | `AMRAP` seul | Un AMRAP doit avoir une durée : `AMRAP 12`. |
| E010 | erreur | `21 Thruster 43/30 kg` puis `21 Trusters` | Mouvement inconnu « Trusters ». Vouliez-vous dire « Thruster » ? |
| E020 | erreur | `10 Box jump 24 kg` | « Box jump » attend une hauteur (in, cm), pas une charge. |
| E021 | erreur | `Thruster 43/30` sans `units:` | Unité de charge manquante. Précisez `kg`/`lb` ou définissez `units:`. |
| E030 | erreur | `For time` + `score: rounds` | Le score « rounds » n'a pas de sens pour un For time. |
| E040 | erreur | `Scaled:` modifie `Row` absent du Rx | « Row » n'apparaît pas dans la version Rx. |
| E050 | erreur | `use girls/fram` | WOD « girls/fram » introuvable. Vouliez-vous dire « girls/fran » ? |
| W100 | alerte | `1 m Run` | 1 mètre de course : vouliez-vous dire `1 mi` (mile) ? |
| W110 | alerte | `Thruster 30/43 kg` | Charge femme supérieure à la charge homme : valeurs inversées ? |
| W120 | alerte | EMOM avec 25 thrusters par minute | Travail estimé ~70 s par minute : l'EMOM n'est pas tenable. |
| W130 | alerte | Chipper long, `cap 5:00` | Durée estimée 18–25 min, bien au-delà du cap. |
| I200 | info | — | Durée estimée : 6–9 min · Famille : couplet G/W · Stimulus : court et intense. |

`wodc check` sort ces diagnostics en texte lisible ou en JSON (pour l'éditeur, le MCP et l'IA).

### 5.3 La vue athlète

Un profil (`athlete.toml`) permet de résoudre un WOD pour soi :

```toml
category = "men"      # men | women
level    = "rx"       # rx | scaled | foundations
units    = "kg"       # kg | lb  → mettre "lb" au Québec
[1rm]
back_squat = 140
clean      = 100
```

```
$ wodc show fran.wod --me
FRAN — For time · cap 10:00
21-15-9
  Thruster ........ 43 kg
  Pull-up
Estimé : 6–9 min

$ wodc show seance.wod --me --units lb
Back squat 5x5 @ 75% → 105 kg → 230 lb
```

Les conversions kg ↔ lb utilisent **les équivalences officielles** plutôt que le calcul brut : 95 lb ↔ 43 kg, 65 lb ↔ 30 kg, 135 lb ↔ 61 kg, 24 in ↔ 60 cm, 1,5 pood ↔ 24 kg. Un WOD québécois en `95/65 lb` s'affiche donc `43/30 kg`, comme sur n'importe quel tableau européen. Pour les charges libres (% de 1RM), l'arrondi se fait aux disques disponibles (2,5 kg ou 5 lb).

## 6. Le format de sortie : le vrai standard

Fran compilé (extrait) :

```json
{
  "wodcraft": "1.0",
  "kind": "workout",
  "title": "Fran",
  "format": { "type": "for_time", "cap_s": 600 },
  "blocks": [{
    "scheme": { "type": "rep_ladder", "reps": [21, 15, 9] },
    "items": [
      { "movement": "thruster",
        "load": { "men": { "kg": 43, "lb": 95 }, "women": { "kg": 30, "lb": 65 } },
        "source": { "line": 4, "col": 3 } },
      { "movement": "pull_up", "source": { "line": 5, "col": 3 } }
    ]
  }],
  "levels": {
    "scaled": [
      { "movement": "thruster", "load": { "men": { "kg": 30 }, "women": { "kg": 20 } } },
      { "replace": "pull_up", "with": "jumping_pull_up" }
    ]
  },
  "score": { "type": "time", "capped": "reps" },
  "estimate": { "duration_s": [360, 540] }
}
```

Le standard publié se compose de :

1. **La spécification** (`spec/`) : grammaire formelle (EBNF), sémantique, tableau des diagnostics. Licence CC-BY 4.0.
2. **Le JSON Schema** du format compilé, versionné.
3. **Le catalogue de mouvements**, ouvert, alias FR/EN.
4. **La suite de conformité** : pour chaque `.wod`, le JSON attendu ou les diagnostics attendus. Toute implémentation (Python, TypeScript, Swift…) se valide contre elle.
5. **La bibliothèque de référence** : Girls, Heroes, Open, utilisable via `use`.

Hors du périmètre 1.0 : la programmation sur plusieurs semaines (extension 1.1) et les résultats réalisés (à exporter vers un format existant comme WODIS plutôt que d'en réinventer un).

## 7. Outils

| Outil | Rôle |
|---|---|
| `wodc check` | Vérifie, affiche les diagnostics (texte ou JSON). |
| `wodc build` | Compile en JSON. |
| `wodc show [--me] [--units lb] [--level scaled]` | Affiche la version tableau blanc, résolue pour un athlète. |
| `wodc fmt` | Met en forme canonique (comme `gofmt`) : fin des débats de style. |
| `wodc timer` | Déroulé chronométré (EMOM, Tabata, intervalles). |
| `wodc export ics` | Séance(s) dans un calendrier. |
| Serveur MCP (Python) | `check`, `build`, `show`, `from_text` : Claude transforme une photo ou un texte de tableau blanc en WODCraft, le compilateur le vérifie, Claude corrige jusqu'à ce que ce soit valide. |
| Extension VS Code | Coloration, diagnostics en direct, complétion des mouvements, via un serveur de langage (LSP) en Python qui réutilise le compilateur. |

## 8. Architecture du dépôt

```
spec/                 spécification, JSON Schema, suite de conformité
catalog/              movements.yaml (source unique), equivalences.yaml
library/              girls/, heroes/, open/
src/wodcraft/
  syntax/             lexer, parser, arbre avec positions
  semantics/          résolution, typage, vérifs, estimation
  emit/               json, whiteboard, markdown, ics, timer
  diagnostics.py      codes, messages FR/EN
  cli.py  sdk.py
  mcp/                serveur MCP (FastMCP)
  lsp/                serveur de langage (pygls)
editor/vscode/        client léger de l'extension
tests/                unitaires + exécution de la suite de conformité
```

Un seul langage (Python), un seul catalogue, une seule source de vérité. Plus de TypeScript côté serveur, plus de `node_modules`.

## 9. Ce qu'on garde de l'existant

- La bibliothèque de WODs (Girls, Heroes, Open), réécrite dans la nouvelle syntaxe.
- Les 125 mouvements du catalogue, comme point de départ.
- Le nom, le paquet PyPI `wodcraft`, la commande `wodc`.
- L'idée de séance composée de modules réutilisables (`use`).

L'ancien code est archivé sous le tag `v0.3-legacy`. Le paquet n'a quasiment pas d'utilisateurs (6 téléchargements le mois dernier) : la rupture est sans coût.

## 10. Feuille de route

| Jalon | Contenu | Effort |
|---|---|---|
| M0 | Nettoyage du dépôt, tag `v0.3-legacy`, CI | ½ j |
| M1 | Spec v1 + corpus de 30 WODs + JSON Schema — **validation par vous** | 2–3 j |
| M2 | Compilateur : parser, typage, vérifs, JSON, `fmt`, CLI, suite de conformité | 4–5 j |
| M3 | Catalogue FR/EN, équivalences kg/lb, profil athlète, `show --me`, estimations | 2 j |
| M4 | Serveur MCP Python + `from_text` | 2 j |
| M5 | LSP + extension VS Code | 2 j |
| M6 | Site de la spec, README, publication 1.0 | 1–2 j |

Total : environ 14–17 jours de travail. Chaque jalon est livrable seul ; M1 est le seul où votre avis est indispensable.

## 11. Points ouverts

1. Faut-il accepter aussi l'ordre « poids d'abord » (`43/30 kg Thruster`) ? Proposition : non, une seule forme, `fmt` corrige.
2. Mots-clés en français (`Pour le temps`, `3 tours`) ? Proposition : mots-clés en anglais (c'est l'usage dans les box françaises), noms de mouvements FR et EN acceptés.
3. Catégories au-delà de H/F (masters, adaptive) : prévoir le champ dès 1.0, le remplir plus tard.
