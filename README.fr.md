# WODCraft

[English](README.md) | Français

**Écrivez un WOD comme il s'écrit au tableau blanc. Laissez un compilateur le vérifier.**

```wod
# Fran
21-15-9 for time, cap 10:00
  Thruster 95/65 lb
  Pull-up

Scaled:
  Thruster 65/45 lb
  Pull-up -> Jumping pull-up
```

```console
$ wodc show fran.wod --category women --units kg
FRAN
21-15-9 for time · cap 10:00
  Thruster ............................. 30 kg
  Pull-up
Score: time (capped: reps)
Estimate: 2:26–5:04
```

WODCraft est un langage ouvert pour **prescrire** des séances de fitness fonctionnel, accompagné d'un
compilateur qui les transforme en JSON exploitable par n'importe quelle application. Il est strict là
où ça compte — unités, noms de mouvements, cohérence du score, plausibilité — et souple là où les
coachs en ont besoin : vous écrivez `Pull-up`, `pull ups` ou `tractions`, et `95/65 lb` reste
`95/65 lb`.

## Pourquoi

- **Lisible par les athlètes.** Tout fichier valide peut être affiché tel quel au mur de la box.
- **Vérifié par un compilateur.** `10 Box jump 24 kg` est refusé : un box jump attend une hauteur.
  `1 m Run` demande si vous vouliez écrire `1 mi`. Un EMOM avec 25 thrusters par minute vous prévient
  qu'il n'est pas tenable.
- **Un seul format d'échange.** Le JSON compilé est décrit par un
  [JSON Schema](spec/workout.schema.json) versionné : c'est lui que s'échangent les timers, les
  applications et les agents IA.
- **Converti pour vous.** Les charges portent les kilos et les livres, avec les équivalences
  réellement utilisées en box (95 lb ↔ 43 kg, 24 in ↔ 60 cm), et `--units lb` bascule tout l'affichage.

## Installation

```bash
pip install wodcraft          # le langage, la CLI, le catalogue et la bibliothèque
pip install "wodcraft[mcp]"   # + le serveur MCP pour Claude et les autres agents IA
pip install "wodcraft[lsp]"   # + le serveur de langage utilisé par l'extension VS Code
```

Python 3.11+, aucune dépendance à l'exécution.

## Utilisation

```bash
wodc check mardi.wod              # diagnostics, avec ligne, colonne et suggestion
wodc show  mardi.wod --me         # la vue tableau blanc, résolue pour votre profil
wodc build mardi.wod -o out.json  # le document compilé
wodc fmt --write mardi.wod        # forme canonique, comme gofmt
wodc timer fran.wod               # le déroulé du chrono, segment par segment
wodc export ics semaine.wod       # une séance dans votre agenda
wodc catalog thruster             # explorer le catalogue de mouvements
wodc lib girls                    # la bibliothèque de référence
wodc show girls/fran --lang fr    # …et n'importe lequel de ses WODs, par son nom
```

Un profil d'athlète (`athlete.toml`, cherché dans le dossier courant, ses parents, puis
`~/.config/wodcraft/`) transforme les prescriptions en vos charges :

```toml
category = "men"     # men | women
level     = "rx"     # rx | intermediate | scaled | foundations
units     = "kg"     # passez à "lb" quand vous vous entraînez en Amérique du Nord
bodyweight_kg = 78

[1rm]
back_squat = 140
clean = 100
```

```console
$ wodc show force.wod --me
BACK SQUAT
Back squat ........................ 5x5 105 kg
```

## Le langage en une minute

```wod
# Mardi 23 septembre           // une séance : titre '#', sections '##'
date: 2026-09-23

## Warm-up
2 rounds
  200 m Run
  10 Air squat

## Strength
Back squat 5x5 @ 75%          // les pourcentages se résolvent avec votre 1RM

## Metcon
use girls/fran                // la bibliothèque standard

## Extra
EMOM 12
Odd: 12/10 cal Row            // les valeurs doubles sont hommes/femmes
Even: 10 Burpee
```

Formats : `For time`, `N rounds [for time]`, échelles de reps (`21-15-9`, `3-6-9 ...`), `AMRAP`,
`EMOM`, `E2MOM`, `Every 4:00 x 4`, `Tabata`, `Death by`, `Max load`, séries de force (`5x5`,
`5-5-3-3-1`). Labels : `Buy-in:`, `Cash-out:`, `Odd:`, `Even:`, `Min N:`, `Scaled:`, `Intermediate:`,
`Foundations:`. Unités : `kg`, `lb`, `pood`, `in`, `cm`, `m`, `km`, `mi`, `ft`, `cal`, `s`, `min` — et
`m` signifie toujours mètres, jamais minutes.

Les mots-clés restent en anglais, comme au tableau blanc dans les box francophones ; les noms de
mouvements, eux, sont reconnus en français comme en anglais (`Tractions`, `Pompes`, `Fentes`…).

La grammaire complète, la sémantique et tous les diagnostics sont dans **[spec/SPEC.md](spec/SPEC.md)**.

## API Python

```python
from wodcraft.api import compile_source
from wodcraft.emit import board
from wodcraft.profile import Profile
from wodcraft.semantics.resolve import resolve

result = compile_source(open("fran.wod").read())
if not result.ok:
    raise SystemExit(result.report())

workout = resolve(result.document, Profile(category="women", units="kg"))
print(board.render(workout))
print(workout["score"])          # {'type': 'time', 'capped': 'reps'}
print(workout["estimate"])       # {'min_s': 146, 'max_s': 304, ...}
```

## Pour les agents IA

`wodcraft[mcp]` fournit un serveur MCP qui expose le compilateur lui-même — sans sous-processus ni
fichier temporaire : `check_wod`, `compile_wod`, `show_wod`, `format_wod`, `timeline_wod`,
`search_movements`, `library_get`. L'agent rédige un WOD, le compilateur répond par des diagnostics
précis, l'agent corrige. Voir [docs/mcp.md](docs/mcp.md).

## Le standard

WODCraft est fait pour être réimplémenté par d'autres :

| Élément | Où |
|---|---|
| Spécification du langage | [spec/SPEC.md](spec/SPEC.md) (CC BY-SA 4.0) |
| Schéma du document compilé | [spec/workout.schema.json](spec/workout.schema.json) |
| Suite de conformité | [spec/conformance/](spec/conformance/) — `.wod` + `.json` ou `.diag` attendus |
| Catalogue de mouvements | [src/wodcraft/catalog/movements.toml](src/wodcraft/catalog/movements.toml) — 200+ mouvements, alias FR/EN |
| Bibliothèque de référence | [src/wodcraft/library/](src/wodcraft/library/) — Girls, Heroes, Open |
| Implémentation de référence | ce dépôt (Apache-2.0) |

## Contribuer

Ajouter un mouvement, un WOD de référence ou un alias français est la porte d'entrée la plus simple :
modifiez le catalogue ou déposez un `.wod` dans la bibliothèque, puis lancez `pytest`. Les évolutions
du langage passent d'abord par la spécification.

## Licence

Code : Apache-2.0. Spécification et documentation : CC BY-SA 4.0 (voir `LICENSE-docs`).
