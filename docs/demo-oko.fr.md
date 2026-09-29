# Ce que ça donne, concrètement

Une démonstration de bout en bout, pour décider sur pièces plutôt que sur une note d'architecture.
**Toutes les sorties ci-dessous ont été produites en exécutant le compilateur**, avec le profil
d'athlète de l'exemple (`examples/athlete.toml` : homme, kilos, 1RM back squat 140 kg).

---

## 1. Vous collez le WOD tel qu'il est au tableau

Ce que vous tapez, avec les fautes de frappe d'un jeudi soir :

```text
21-15-9 for time, cap 10:00
  Trusters 95/65 lb
  Pull ups
```

L'app répond **immédiatement et hors ligne**, sous le champ de saisie :

```
2:3  erreur E020  Mouvement inconnu « Trusters ».
                  vouliez-vous dire « Thruster », « Kettlebell thruster » ou « Dumbbell thruster » ?
```

Une seule erreur : `Pull ups` est déjà reconnu (comme `pull-up`, `pull up`, `tractions`). Vous
corrigez le mot, et c'est bon :

```
✓ valide
```

## 2. L'app a tout compris toute seule

Vous n'avez rien choisi dans un menu : le compilateur a rempli les champs à votre place.

| Champ de l'app | Valeur trouvée |
|---|---|
| Format | `for_time` |
| Schéma de reps | 21-15-9 |
| Time cap | 600 s |
| Mouvements | `thruster` (43/30 kg), `pull_up` |
| Type de score | **temps**, et **reps** si vous prenez le cap |
| Durée estimée | 3:22 – 6:14 |

C'est le champ « type de score » qui compte : l'app sait qu'à la fin elle doit vous demander un
chrono, pas un nombre de tours.

## 3. Ce que vous voyez à l'écran

Vos charges, votre unité, en français :

```
21-15-9 for time · cap 10:00
  Thruster ............................. 43 kg
  Traction
Score: time (capped: reps)
Estimate: 3:22–6:14
[men · rx · kg]
```

La même prescription affichée à une athlète femme donnerait `30 kg`, et en Amérique du Nord
`95 lb` — sans que le WOD saisi change d'un caractère.

## 4. Une partie de force, avec votre 1RM

Vous tapez une ligne :

```wod
Back squat 5x5 @ 75% (rest 2:30)
```

L'app affiche :

```
Squat arrière ......... 5x5 105 kg (rest 2:30)
Score: load
Estimate: 8:24–15:36
[men · rx · kg]
```

**105 kg**, parce que votre 1RM de back squat est à 140. Le type de score est `load` : à la fin, elle
vous demandera une charge, pas un chrono. C'est exactement votre `part = "strength"`.

## 5. La ligne écrite dans `wods`

Rien de neuf pour vos écrans existants : les colonnes actuelles restent remplies, dérivées du texte.

```json
{
  "part": "metcon",
  "format": "for_time",
  "time_cap_s": 600,
  "movements": [
    { "movement_id": "thruster", "name": "Thruster", "reps": [21, 15, 9],
      "load_kg": { "men": 43, "women": 30 } },
    { "movement_id": "pull_up", "name": "Pull-up", "reps": [21, 15, 9] }
  ],
  "score": { "value": 312, "unit": "s" },
  "rx": true
}
```

et pour la partie de force :

```json
{
  "part": "strength",
  "format": "strength",
  "movements": [
    { "movement_id": "back_squat", "name": "Back squat", "sets": [5, 5, 5, 5, 5], "percent": 75 }
  ],
  "score": { "value": 105, "unit": "kg" },
  "rx": true
}
```

Le texte d'origine est conservé tel quel dans `source_dsl`, avec le document complet dans `compiled`.
Notez `movement_id` : c'est lui qui règle la fragmentation des records entre « Back squat »,
« back squat » et « Squat arrière ».

## 6. Le timer, le jour où vous en voudrez un

Le même WOD donne déjà la liste des segments à jouer :

```
    0:00   10:00  21-15-9 for time · cap 10:00: Thruster 95/65 lb + Pull-up
           10:00  total
```

Un EMOM donnerait un segment par minute, un Tabata huit segments de 30 s par mouvement. Rien à
inventer côté app.

## 7. Pourquoi vous pouvez faire confiance à ces sorties

Le compilateur Swift qui tournera dans l'app et l'implémentation Python de référence produisent le
**même document, au caractère près** — vérifié ici sur ce WOD, sur les 68 cas de conformité du
standard, sur les 40 benchmarks, et sur plusieurs centaines de sources générées automatiquement.
C'est ce qui garantit que ce que vous voyez sur cette page est bien ce que l'app affichera.
