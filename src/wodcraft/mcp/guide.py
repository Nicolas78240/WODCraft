"""The short, exact WODCraft syntax guide served as ``wodcraft://guide/syntax``.

Every ```wod fenced block in this module is checked by ``tests/test_server.py``:
it must compile with no error. Never add an example without running the tests.
"""

from __future__ import annotations

import re
import textwrap

from wodcraft import SPEC_VERSION

SYNTAX_GUIDE = f"""# WODCraft {SPEC_VERSION} — syntax guide

Write a workout the way it is written on a gym whiteboard. Everything ambiguous is rejected
with a coded diagnostic, so check your draft with the `check_wod` tool before returning it.

## 1. A file

- UTF-8, extension `.wod`. `//` starts a comment (`#` does **not**: it starts a title).
- `# Title` opens a document. A document that contains `## Section` headings is a *session*;
  otherwise it is a *workout*. A file may hold several documents.
- Indentation is spaces only (2 by convention). Tabs are an error.
- Keywords and units are case-insensitive. `m` is **always** metres, never minutes.

```wod
# Fran
21-15-9 for time, cap 10:00
  Thruster 43/30 kg
  Pull-up
```

## 2. Format lines

| Format | Written | Score inferred |
|---|---|---|
| For time | `For time` | time |
| Rounds | `3 rounds` / `3 rounds for time` | none / time |
| Rep ladder | `21-15-9` / `21-15-9 for time` | none / time |
| AMRAP | `AMRAP 20` or `AMRAP 20:00` | rounds+reps |
| EMOM | `EMOM 12` | reps if a child is `max`, else none |
| EnMOM | `E2MOM 20`, `E3MOM 15` (total duration) | idem |
| Every | `Every 4:00 x 4` | idem |
| Tabata | `Tabata` / `Tabata 8` | reps |
| Death by | `Death by` | rounds+reps |
| Max load | `Max load` / `Max load, 3 attempts` / `Max load, cap 15:00` | load |

Options after a comma: `cap DURATION`, `teams of N`, `for time`, `there and back` (For time,
AMRAP, rounds, ladders: the list in order, then back to the first line without repeating the last),
`N attempts` (Max load only: the best attempt counts; a `Rest` written last in the block comes
between the attempts).

A time cap is either `cap:` for the whole workout or `cap` on each block — never both (`E037`).
Several lifts that add up to one score: `score: load, total` (`score: reps, total` for reps).

```wod
# CrossFit Total
score: load, total
cap: 30:00
Max load, 3 attempts
  1 Back squat
  Rest 2:00
Max load, 3 attempts
  1 Shoulder press
  Rest 2:00
Max load, 3 attempts
  1 Deadlift
  Rest 2:00
```

A bare number is minutes **only** in a format line (`AMRAP 20` = 20 minutes). Everywhere else
write `2 min`, `30 s` or `1:30`.

```wod
# Cindy
AMRAP 20
  5 Pull-up
  10 Push-up
  15 Air squat
```

```wod
# Helen
3 rounds for time
  400 m Run
  21 Kettlebell swing 24/16 kg
  12 Pull-up
```

## 3. Movement lines

```
[QUANTITY] Name [SETS] [PARAMETER]* [(MODIFIER, ...)]
```

- Quantity: reps `21`, distance `400 m` / `1 mi` / `5 km`, calories `15/12 cal`,
  time `30 s` / `2 min` / `1:30`, or `max` (`max Burpee`, `max cal Row`).
  It may be omitted **only** inside a rep ladder, `Max load` or `Death by`.
- Name: resolved against the movement catalog (English and French aliases, case and plural
  insensitive: `Pull-up`, `pull ups`, `Tractions`). Use `search_movements` when unsure —
  a name outside the catalog is an error (E020).
- Sets: `5x5` (5 sets of 5) or a ladder `5-5-3-3-1-1`.
- Parameters: load `43/30 kg` / `95/65 lb` / `1.5/1 pood`, percent `@ 75%` or `@ 75% Back squat`,
  `@ RPE 8`, height `24/20 in` / `60/50 cm`, `bw` / `@ 1.5 bw`.
  The `@` is optional before a load. The kind must match the catalog entry: a load on a box jump
  is an error (E032), and so is a height on a thruster.
- `a/b` is always *men/women*, in that order. A single value applies to both.
- Modifiers, in parentheses: `sync`, `split`, `each`, `alternating`, `unbroken`,
  `rest DURATION`, `per side`, `hold` or `hold DURATION` (`1 Wall walk (hold 10 s)`), or free text in quotes.

```wod
# Modifiers and parameters
For time, cap 12:00
  50 Double-under (unbroken)
  40 Wall ball 9/6 kg ("to a 10 ft target")
  30 Box jump 24/20 in
```

```wod
# Strength
units: kg
Back squat 5x5 @ 75%
Deadlift 5-5-3-3-1-1 @ RPE 8
Power clean 5x3 @ 70% Clean
```

## 4. Rest

`Rest DURATION` is a line of its own inside a block. Several timed blocks in a row must hang
under an untimed parent.

```wod
# Intervals with rest
3 rounds
  AMRAP 4:00
    10 Burpee
    10 Air squat
  Rest 1:00
```

## 5. Labels

| Label | Where |
|---|---|
| `Buy-in:` / `Cash-out:` | inside `For time` / `AMRAP` |
| `Odd:` / `Even:` | inside `EMOM` / `EnMOM` |
| `Min N:` | inside `EMOM` / `EnMOM` / `Every` |
| `Scaled:` / `Intermediate:` / `Foundations:` | after the Rx work |

```wod
# Alternating EMOM
EMOM 12
  Odd: 12/10 cal Row
  Even: 10 Burpee
```

```wod
# Every window
Every 4:00 x 4
  400 m Run
  max Burpee
score: reps
```

```wod
# Buy-in and cash-out, in teams
Teams of 2, for time, cap 20:00
Buy-in:
  1000 m Row (split)
4 rounds
  12 Wall ball 9/6 kg (sync)
  10 Box jump 24/20 in
Cash-out:
  50 Double-under (each)
```

## 6. Meta lines

`key: value`, with key one of `cap`, `score`, `tiebreak`, `units`, `vest`, `stimulus`, `note`,
`tags`, `date` (session), `time` (session). Any other key is an error (E012).

`score` takes `time`, `rounds+reps`, `reps`, `load`, `distance`, `calories` or `none`.

**Placement matters.** A meta line written *between* the format line and its movements breaks the
block (E004). Put `vest:`, `units:` and friends **before** the format line; `note:`, `score:` and
`stimulus:` may also sit at the very end of the body.

```wod
# Murph
tags: heroes, benchmark
vest: 9/6 kg
For time, cap 60:00
  1 mi Run
  100 Pull-up
  200 Push-up
  300 Air squat
  1 mi Run
note: Partition the pull-ups, push-ups and air squats as needed.
```

## 7. Levels

A workout written without level labels is Rx. A level block lists **only the differences**, and
every movement it names must already appear in the Rx work (E040).

- same movement, new parameters: `Thruster 30/20 kg`
- swap the movement: `Pull-up -> Jumping pull-up`
- change quantities, only after the arrow: `Chest-to-bar pull-up -> 2x Ring row` (twice the reps),
  `Wall walk -> 3 Inchworm` (three reps); a quantity anywhere else in a level is E014
- `Adapted:` records what one athlete actually did, with the same lines plus bare counts
  (`5 Wall walk`); it is applied after the chosen level
- an alternative in the Rx work: `10 Ring row | Scap pull` (either one; an option without a
  quantity takes the first one's)

```wod
# Levels
AMRAP 15:00
  9 Chest-to-bar pull-up
  12 Dumbbell snatch 22.5/15 kg

Intermediate:
  Chest-to-bar pull-up -> Pull-up

Scaled:
  Chest-to-bar pull-up -> Ring row
  Dumbbell snatch 15/10 kg
```

## 8. Sessions and the library

`## Section` headings turn a document into a session. `use PATH` pulls a workout from the standard
library (`girls/`, `heroes/`, `open/` — browse it with `library_list`).

```wod
# Tuesday 23 September
date: 2026-09-23
time: 18:30

## Warm-up
2 rounds
  200 m Run
  10 Air squat

## Strength
Back squat 5x5 @ 75%

## Metcon
use girls/fran

## Cool-down
5:00 Bike
```

## 9. Mistakes to avoid

| Wrong | Right | Why |
|---|---|---|
| `# 10 minutes of work` | `// 10 minutes of work` | `#` opens a title |
| `AMRAP 12m` | `AMRAP 12` | `m` is metres |
| `Thruster 43/30` with no `units:` | `Thruster 43/30 kg` | E031 |
| `Box jump 24 kg` | `Box jump 24 in` | E032, box jumps take a height |
| `Tabata 8` then a bare `Air squat` | `max Air squat` | only a ladder, `Max load` and `Death by` may drop the quantity |
| `Scaled:` naming a movement absent from Rx | name one of the Rx movements | E040 |
| `1,5 pood` | `1.5 pood` | E003, no decimal comma |
| a meta line inside a block | move it before the format line | E004 |

```wod
# Tabata
Tabata 8
  max Air squat
```

## 10. Workflow

1. Draft the workout.
2. Call `check_wod`; fix every diagnostic (each one carries a line, a column and a suggestion).
3. Call `show_wod` to read the whiteboard, `timeline_wod` for the clock.
4. Return the `.wod` source, not the JSON.
"""


def wod_examples(text: str) -> list[str]:
    """Every ```wod fenced block of a Markdown or Python text, in order, dedented.

    Blocks indented inside a docstring are dedented so that they can be compiled as-is.
    """
    blocks = re.findall(r"^[ \t]*```wod[ \t]*\n(.*?)^[ \t]*```", text, re.DOTALL | re.MULTILINE)
    return [textwrap.dedent(block).strip("\n") + "\n" for block in blocks]
