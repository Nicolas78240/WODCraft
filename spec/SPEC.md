# WODCraft Language Specification — 1.2 (draft)

Status: draft · Editor: WODCraft project · License: CC BY-SA 4.0 (see `LICENSE-docs`)

The key words MUST, MUST NOT, SHOULD and MAY are to be interpreted as in RFC 2119.

## 1. Goals

WODCraft is a plain-text language to **prescribe** functional-fitness workouts (CrossFit-style WODs)
and whole training sessions. A WODCraft file:

1. reads like a gym whiteboard, so athletes can read it with no training;
2. is **strict**: anything ambiguous is rejected with a located, coded diagnostic;
3. compiles to a JSON document (see `workout.schema.json`) that applications exchange.

Out of scope for 1.2: multi-week programming, logged results (the athlete's adaptation, §9.1, is
the only record of what was actually done).

## 2. Lexical structure

- Files are UTF-8 text with the extension `.wod`. Line endings are LF or CRLF.
- `//` starts a comment that runs to the end of the line. Comments are ignored.
- A line containing only whitespace and/or a comment is a **blank line**.
- **Indentation** is made of spaces. A tab in indentation is an error (`E002`).
  Indentation levels are relative: a line is a child of the nearest previous line with a smaller indentation.
- Keywords, units and labels are **case-insensitive** (`FOR TIME`, `For time` and `for time` are equal).
  Canonical form (produced by the formatter) is shown in this document.
- Numbers are written with digits and an optional decimal point: `1.5`. A decimal comma (`1,5`) is an error (`E003`).
- A **dual value** `a/b` gives the value for the *men* and *women* categories, in that order. A single value applies to both.

### 2.1 Durations

| Form | Meaning |
|---|---|
| `m:ss`, `mm:ss`, `h:mm:ss` | clock time, e.g. `1:30`, `12:00`, `1:00:00` |
| `N s`, `N sec` | seconds |
| `N min` | minutes |
| bare `N` | minutes — **only** in a format line (`AMRAP 12`, `EMOM 10`, `cap 20`) |

`m` is **never** minutes: it always means metres.

### 2.2 Units

| Kind | Units |
|---|---|
| load | `kg`, `lb`, `pood` (1 pood = 16 kg) |
| height | `in`, `cm` |
| distance | `m`, `km`, `mi`, `ft` |
| energy | `cal` |
| time | see 2.1 |
| relative | `%` (of a one-rep max), `bw` (bodyweight), `RPE N` |

A unit MAY be attached to its number (`400m`) or separated by a space (`400 m`).
The canonical form separates them, except for `%`.

## 3. Documents

A file contains one or more **documents**.

- `# Title` starts a document. Lines before the first `#` form one untitled document.
- A document whose body contains `## Section` headings is a **session**; otherwise it is a **workout**.
- In a session, lines between the `#` heading and the first `##` MAY only be meta lines (§6).
  Each section body is a workout body.

```wod
# Fran                      // a workout
...

# Tuesday 23 September      // a session
date: 2026-09-23
## Warm-up
...
## Metcon
...
```

## 4. Workout body

A body is a sequence of **statements**, one per line:

| Statement | Example |
|---|---|
| format line | `AMRAP 20`, `3 rounds for time`, `21-15-9` |
| label line | `Buy-in:`, `Odd: 10 Burpee`, `Scaled:` |
| movement line | `21 Kettlebell swing 24/16 kg` |
| rest line | `Rest 2:00` |
| use line | `use girls/fran` |
| meta line | `cap: 10:00`, `note: Go unbroken` |

### 4.1 Block ownership

A format line or a label line opens a **block**. The block owns, by the first rule that applies:

1. its **indented children**, if the next non-blank line is more indented;
2. if it is the **first format line of a workout body** (meta lines excepted): every following line of
   the body, up to the first level label (`Scaled:`…) — the whole workout hangs off its main format;
   a meta line is transparent here: it never owns the indented lines that follow it, they belong to
   the block above it;
3. otherwise, the **following sibling lines** at the same indentation. A format block also takes the
   label lines that follow it (`Buy-in:`, `Odd:`…) and stops at the next format line, level label,
   heading or end of body; a label block stops at the next label as well.

Rules 2 and 3 let the common cases be written without indentation:

```wod
For time, cap 10:00      // block: for_time (cap 600 s)       — rule 2
21-15-9                  //   └ block: reps [21,15,9]          — rule 1
  Thruster 43/30 kg      //       ├ thruster
  Pull-up                //       └ pull_up

EMOM 12                  // block: emom (720 s)                — rule 2
Odd: 12/10 cal Row       //   ├ odd  → row
Even: 10 Burpee          //   └ even → burpee
```

Several timed blocks in sequence MUST be indented under an untimed parent, or written as
separate indented blocks:

```wod
3 rounds
  AMRAP 4
    10 Burpee
    10 Air squat
  Rest 1:00
```

### 4.2 Nesting

| Block | MAY contain |
|---|---|
| `rounds`, `reps` ladder (untimed) | anything |
| `emom` (including `EnMOM`), `every` | movements, rest, slot labels, `for_time`, `amrap`, untimed blocks |
| `for_time`, `amrap`, `tabata`, `death_by`, `max_load` | movements, rest, untimed blocks, `Buy-in:`/`Cash-out:` (`for_time`, `amrap` only) |

Any other combination is an error (`E015`).

## 5. Format lines

`FORMAT [, OPTION]*`. Options: `cap DURATION`, `teams of N`, `for time`, `there and back`,
`N attempts`.

| Format | Syntax | Semantics |
|---|---|---|
| For time | `For time` | complete the work as fast as possible |
| Rounds | `N rounds` · `N rounds for time` | repeat the block N times (timed if `for time`) |
| Rep ladder | `21-15-9` · `21-15-9 for time` | one round per value; each child movement *without* a quantity takes that value |
| Open ladder | `3-6-9 ...` | a ladder with a constant step that keeps going until the cap |
| AMRAP | `AMRAP DURATION` | as many rounds (and reps) as possible |
| EMOM | `EMOM DURATION` | every minute on the minute |
| EnMOM | `E2MOM 20`, `E3MOM 15` | every *n* minutes; DURATION is the total |
| Every | `Every DURATION x N` | N intervals of DURATION |
| Tabata | `Tabata` · `Tabata N` | N intervals (default 8) of 20 s work / 10 s rest, **per movement**, movements in order |
| Death by | `Death by` | minute *k*: perform *k* reps of the (single) child movement, until failure |
| Max load | `Max load` · `Max load, N attempts` · `Max load, cap DURATION` | build to the heaviest load for the prescribed reps; with attempts, the best of N attempts counts |
| Sets | movement line with `NxM` / `N-N-N` (§7.3) | strength sets |

A rep ladder MAY use any number of values (`10-9-8-7-6-5-4-3-2-1`). An **open ladder** ends with `...`
and MUST have a constant step: `3-6-9 ...` means 3, 6, 9, 12… until the cap is reached (`E035` otherwise).
`Teams of N` MUST only appear on the outermost format line of a workout.

**There and back** (1.1; French `aller-retour` is accepted and written back as `there and back`)
applies to `For time`, `AMRAP`, `N rounds` and rep ladders: the list is done in order, then in reverse
order back to the first line, **without repeating the last one**. Lines A, B, C are done
A, B, C, B, A — one round of an AMRAP is that whole path. On any other format it is an error
(`E014`).

```wod
For time, cap 25:00, teams of 2, there and back
  50 cal Row (split)
  40 Pull-up (split)
  10 Wall walk (split)
```

The score (§12) carries `there_and_back: true`: a round is the whole path, and an athlete stopped
by the cap counts the reps done along it (50 + 40 + 10 + 40 + 50 reps and calories for the path
above). Duration estimates count the whole path.

**Attempts** (1.2; French `essais` is accepted and written back as `attempts`) apply to `Max load`
only — on any other format they are an error (`E014`), and N MUST be at least 1 (`E035`).
`Max load, 3 attempts` gives the athlete three attempts at the heaviest load; the best one counts.
A `Rest` written as the last line of the block is the rest **between** the attempts: three attempts
take two rests (§8). A `Rest` between two blocks keeps its usual meaning.

```wod
# CrossFit Total
score: load, total
cap: 30:00
Max load, 3 attempts
  1 Back squat
  Rest 2:00
Rest 3:00
Max load, 3 attempts
  1 Shoulder press
  Rest 2:00
Rest 3:00
Max load, 3 attempts
  1 Deadlift
  Rest 2:00
```

## 6. Label and meta lines

**Labels** open a block; text after the colon, if any, is a single child movement line.

| Label | Allowed in | Meaning |
|---|---|---|
| `Buy-in:` / `Cash-out:` | workout body | work before / after the main block, inside the clock |
| `Odd:` / `Even:` | EMOM, EnMOM | minutes 1, 3, 5… / 2, 4, 6… |
| `Min N:` | EMOM, EnMOM, Every | the N-th interval of each cycle (cycle length = highest N) |
| `Scaled:` / `Intermediate:` / `Foundations:` | workout body, after the Rx work | level adaptations (§9) |
| `Adapted:` | workout body, after the Rx work | what one athlete actually did (§9.1, 1.1) |

**Meta lines** are `key: value` where the key is one of the following (case-insensitive; label and meta names never overlap):

| Key | Value | Where |
|---|---|---|
| `cap` | duration — the cap of the **whole** workout (§6.1) | workout |
| `score` | `time`, `rounds+reps`, `rounds`, `reps`, `load`, `distance`, `calories`, `none`, then optionally `, total` (§12) | workout |
| `tiebreak` | free text | workout |
| `units` | `kg` or `lb` | workout, session — default unit for loads written without one |
| `vest` | load | workout |
| `stimulus`, `note` | free text | anywhere (repeatable) |
| `tags` | comma-separated words | workout, session |
| `date` | `YYYY-MM-DD` | session |
| `time` | `HH:MM` (local) | session |

An unknown key is an error (`E012`).

The value of `score:` is one of the words above, optionally followed by modifiers after a comma —
the grammar of a format line. The only modifier is `total` (1.2): `score: load, total`. An unknown
modifier is an error (`E013`), and so is `none, total`, which has nothing to add up. The French
`charge` is accepted for `load` and written back as `load` by the formatter.

### 6.1 Time caps (1.2)

A workout has **either** one cap for the whole of it, **or** a cap on each block that needs one —
never both:

- `cap:` caps the whole workout. When the body is a single block, the cap is that block's
  (`cap: 12:00` above `For time` is `For time, cap 12:00`); when the body holds several blocks, it
  belongs to the workout and is compiled as the workout's `cap_s`: it does not attach to the first
  block.
- `cap DURATION` on a format line caps that block only: three lifts written `Max load, cap 8:00`
  are three windows of 8 minutes, and with the rest between them the workout lasts their sum.
- A `cap:` line in a workout where a block also carries a cap is an error (`E037`), reported on the
  `cap:` line. (Before 1.2 the `cap:` line was silently lost.)

A level block (§9) MAY still change the cap with its own `cap:` line.

## 7. Movement lines

```
[QUANTITY] NAME [SETS] [PARAM]* [(MODIFIER[, MODIFIER]*)]
```

### 7.1 Quantity

| Form | Example | Kind |
|---|---|---|
| integer or dual | `21`, `50/40` | reps |
| distance | `400 m`, `1 mi`, `5 km` | distance |
| calories | `15/12 cal` | calories |
| duration | `30 s`, `1:00`, `2 min` | time |
| `max` [unit] | `max Burpee`, `max cal Row` | as many as possible in the interval, or to failure outside one |

The quantity MAY be omitted inside a rep ladder (it takes the ladder value), inside `Max load`,
`Death by` and `Tabata`, and for a movement the catalog measures in nothing at all. Otherwise
omission is an error (`E030`).

### 7.2 Name

The name is the sequence of words up to the first token that starts with a digit, `@`, `(`, or a
dual/unit token. It is resolved against the **movement catalog** (§11) by case-insensitive match on the
canonical name, the English aliases and the French aliases, after removing a trailing plural `s`.
An unresolved name is an error (`E020`) with the closest candidates as suggestions.

### 7.3 Sets (strength)

After the name: `NxM` (N sets of M reps) or a set ladder `5-5-3-3-1-1` (one set per value).

```wod
Back squat 5x5 @ 75%
Deadlift 5-5-3-3-1-1 @ RPE 8
```

### 7.4 Parameters

| Parameter | Example | Meaning |
|---|---|---|
| load | `43/30 kg`, `@ 95/65 lb`, `1.5/1 pood` | external load (the `@` is optional) |
| height | `24/20 in`, `60/50 cm`, `10/9 ft` | box or target height; a movement whose catalog entry accepts both (a wall ball) takes a load **and** a height |
| percent | `@ 75%`, `@ 75% Back squat` | share of a one-rep max (of the movement itself, or of the named lift) |
| RPE | `@ RPE 8` | rate of perceived exertion (1–10) |
| bodyweight | `bw`, `@ 1.5 bw` | multiple of bodyweight |
| distance, calories | `Row 500 m`, `10 Shuttle run 25 m` | the quantity when none was written, otherwise a per-rep measure; the movement must accept that kind |

A number without unit in parameter position is a load in the `units:` default unit; without a
default it is an error (`E031`).

The parameter kind MUST match the catalog entry of the movement: a load on a box jump or a height
on a thruster is an error (`E032`).

### 7.5 Modifiers

In parentheses after the parameters: `sync`, `split`, `each`, `alternating`, `unbroken`, `strict`,
`per side`, `rest DURATION`, `hold` or `hold DURATION` (each rep is held, e.g. `1 Wall walk (hold 10 s)`;
the duration is added to every rep in estimates, and anything but a duration after `hold` is an
error, `E001`), or free text in quotes — `("lateral over the dumbbell")`. A quoted
modifier may contain commas; commas outside quotes separate modifiers.

### 7.6 Alternatives (1.1)

`|` separates the **options** of a movement line: the athlete does one of them.

```wod
For time
  10 Ring row | 8 Scapular pull-up
  12/10 cal Row | 15/12 cal Bike erg
```

Each option is a complete movement line (quantity, parameters, modifiers). An option written
without a quantity takes the quantity of the first one: `10 Ring row | Scap pull` is ten of either.
The compiled item is the first option, with the others in `or` (§13), so a reader that ignores `or`
still sees a valid workout. Level and adaptation blocks (§9) apply to every option. A `|` inside a
level block is an error (`E014`). The whiteboard joins the options with "or" ("ou" in French).

## 8. Rest

`Rest DURATION` is a timed pause item. As the **last item of a repeated block** it is performed
between rounds, not after the last one (5 rounds with a trailing `Rest 3:00` contain four rests).
A `Max load` with attempts (§5) is repeated once per attempt: its trailing rest comes between the
attempts (1.2). In a Sets context (`Back squat 5x5 (rest 2:00)`) use the modifier.

## 9. Levels

A workout written without level labels is **Rx**. A level block lists only the differences:

```wod
21-15-9 for time
  Thruster 43/30 kg
  Pull-up
  Box jump 60/50 cm

Scaled:
  Thruster 30/20 kg              // same movement: replace its parameters
  Pull-up -> Jumping pull-up     // replace the movement (parameters MAY follow)
  Box jump -> Step-up 50/40 cm
```

- A line whose movement also appears in the Rx work replaces the parameters of **every** occurrence.
- `A -> B` replaces every occurrence of A by B, keeping quantities.
- To adapt only some occurrences, write the original parameters **before** the arrow; they select the
  occurrences to change: `Deadlift 225 lb -> Deadlift 155 lb`.
- A level block MAY also carry the meta lines `vest`, `cap` and `note`; `vest: none` removes the vest.
- A level block changes quantities only with an explicit form, right after the arrow (1.1):
  `Chest-to-bar pull-up -> 2x Ring row` multiplies the quantities of every occurrence (a movement that
  takes its reps from a ladder does twice the ladder value), and `Wall walk -> 5 Inchworm` sets them.
  The factor MUST be greater than zero (`E035`); the new quantity MUST be one the movement accepts
  (`E033`). A quantity written anywhere else in a level block — before the arrow, or on a line
  without one — is an error (`E014`): a level adapts the movement, it does not silently rewrite the
  workout.
- A movement that does not appear in the Rx work is an error (`E040`).

### 9.1 Adapted (1.1)

`Adapted:` records how **one athlete** actually did the workout — the moves they replaced, the counts
they did. It is written like a level block, after the Rx work and the levels, and accepts the same
lines (`A -> B`, `A -> 2x B`, `A -> 10 B`, parameters, `vest`, `cap`, `note`), plus a quantity on a
line without an arrow: `5 Wall walk` means five wall walks were done instead of the prescription.

```wod
For time
  20 Bar muscle-up
  30 Chest-to-bar pull-up
  10 Wall walk

Scaled:
  Bar muscle-up -> Jumping pull-up

Adapted:
  Bar muscle-up -> 2x Chest-to-bar pull-up
  Jumping pull-up -> Ring row
  5 Wall walk
  note: shoulder pain, no kipping
```

- An `Adapted:` line may name a movement of the Rx work or one that a level puts in (`Jumping pull-up`
  above); anything else is an error (`E040`). A second `Adapted:` block is an error (`E041`).
- The compiled workout exposes the operations in `adapted` (the same shape as a level's operations),
  not in `levels`: `Adapted` is not a level an athlete can ask for.
- Resolution (§14) applies it **after** the chosen level: each movement is first adapted by the level,
  then by the first `Adapted:` line that matches the movement as the level left it. The resolved
  workout says so with `resolved.adapted: true`.

## 10. Use

`use PATH` inserts a workout from a library, e.g. `use girls/fran`. When a workout body (or a
session section) contains nothing but a `use` line, it **adopts** the referenced workout entirely —
its blocks, score, levels and notes — and keeps its own title. Elsewhere the referenced blocks are
inserted where the line stands, and must be allowed there (§4.2). PATH is resolved against, in
order: the directory of the current file, directories given to the compiler, the standard library.
An unresolved path is an error (`E050`) with suggestions. Cycles are an error (`E051`).
The standard library ships `girls/`, `heroes/`, `open/` and, since 1.2, `benchmarks/` (strength
benchmarks such as `benchmarks/crossfit_total`).

## 11. Movement catalog

The catalog (`catalog/movements.toml`) is part of the standard. Each entry has an identifier
(`snake_case`), a canonical English name, English and French aliases, a family (`M` monostructural,
`G` gymnastics, `W` weightlifting), the quantities it accepts (reps, distance, calories, time), the
parameter kind it expects (load, height, none), and an average pace used for duration estimates.
Implementations MUST accept every catalog entry and MUST NOT accept names outside the catalog.
The first French alias is also the French display name (`wodc show --lang fr`).

The catalog has a generic **ergometer** (`ergometer`, alias `ergo`, `cal ergo`, `machine`, French
`ergomètre`), measured in calories, distance or time: the board leaves the choice of the machine
(rower, bike, ski) to the athlete, and the machine actually used is recorded with the score.

## 12. Score

The score of a workout is taken from the `score:` meta line, or inferred from its main block:

| Main block | Inferred score |
|---|---|
| `for_time`, `N rounds for time`, ladder `for time` | `time` (with a cap: `time`, capped athletes score `reps`) |
| `amrap` | `rounds+reps` |
| `emom`, `enmom`, `every` | `reps` if any child is `max`, else `none` |
| `tabata` | `reps` |
| `death_by` | `rounds+reps` |
| `max_load`, sets | `load` |
| a bare movement line carrying sets (`Back squat 5x5 @ 75%`) | `load` |
| untimed `rounds` / ladder | `none`, or the declared `score:` (`reps`, `load`…) |
| several timed blocks in one workout | `multi`: one score per part |

An explicit score that cannot be measured by the main block is an error (`E036`), e.g. `score: rounds+reps`
on a `for_time` without cap. A workout whose body holds several timed blocks (a metcon then a heavy
single) scores `multi`, with one entry per part — that is also how a workout carries two scores.

**Total** (1.2). `score: VALUE, total` says that the parts **add up** to one score:

- over several timed blocks, the score is `multi` with `"aggregate": "sum"` and `"unit": VALUE`, and
  every part is scored by VALUE. A part that cannot be measured by VALUE is an error (`E036`), on
  that part. The CrossFit Total (three `Max load` blocks) is `score: load, total`;
- over a single block, the score is VALUE with `"aggregate": "sum"`: every effort of the block adds
  up — Lynne, five rounds of max-rep sets, is `score: reps, total`.

A reader that ignores `aggregate` still sees every part. Without `, total`, nothing changes: a
declared score on several timed blocks is still the score of the first one.

In a `Max load` with attempts, the best attempt is the load of the part.

## 13. Compiled output

Compiling a document produces a JSON object described by `spec/workout.schema.json`. In summary:

- `wodcraft`: the version of the compiled format — the oldest one that holds the document. It is
  `"1.0"` for a document that uses nothing newer, so that a 1.0 document compiles to exactly the same
  JSON under 1.1 and 1.2; `"1.1"` when it uses a construct added in 1.1: an alternative (`or`), a level
  quantity (`factor`, `quantity`), a block done there and back (`there_and_back`) or an `Adapted:`
  block (`adapted`); `"1.2"` when it uses a construct added in 1.2: attempts (`attempts`), a total
  (`aggregate`) or a cap on the whole workout (`cap_s`). A session takes the newest version of its
  sections. `kind`: `"workout"` or `"session"`; `title`.
- Workout: `blocks` (the body: blocks, and the movement or rest lines written at the top level, such
  as a bare strength line), `cap_s` (1.2, §6.1), `score`, `levels`, `meta`, `team`.
- Session: `sections`, each `{ "title", "workout" }`, plus `date`, `time`, `meta`.
- Every item has a `source` span `{ "line", "col" }` (1-based).
- The canonical written form of a workout is the **compact** one: `21-15-9 for time, cap 10:00` rather
  than `For time` followed by `21-15-9`. Both compile to the same JSON; the formatter produces the former.
- Movements are catalog identifiers (`"pull_up"`). Loads, heights and distances are normalized:
  loads in kg **and** lb, heights in cm **and** in, distances in m, durations in seconds.
  Dual values become `{ "men": …, "women": … }`.
- Conversions between metric and imperial use the **equivalence table** (`catalog/equivalences.toml`,
  e.g. 95 lb ↔ 43 kg, 24 in ↔ 60 cm) before falling back to arithmetic conversion rounded to
  0.5 kg / 1 lb / 1 cm / 1 in.

### 13.1 A worked example

`21-15-9 for time, cap 10:00` with `Thruster 95/65 lb` and `Pull-up` compiles to:

```json
{
  "wodcraft": "1.0", "kind": "workout", "title": "Fran",
  "blocks": [{
    "type": "for_time", "cap_s": 600, "reps": [21, 15, 9],
    "items": [
      { "type": "movement", "movement": "thruster", "name": "Thruster",
        "load": { "kg": { "men": 43, "women": 30 }, "lb": { "men": 95, "women": 65 },
                  "unit": "lb", "written": { "men": 95, "women": 65 } },
        "source": { "line": 4, "col": 3 } },
      { "type": "movement", "movement": "pull_up", "name": "Pull-up", "source": { "line": 5, "col": 3 } }
    ],
    "source": { "line": 3, "col": 1 }
  }],
  "score": { "type": "time", "capped": "reps" }
}
```

Note the canonical merge (§13): the `for_time` block carries the ladder directly, `unit` and
`written` keep what the author typed, and `kg`/`lb` carry the normalized values. A workout with
several timed blocks scores `{"type": "multi", "parts": [{"type": "…", "block": 0}, …]}`, and with
`score: load, total` `{"type": "multi", "aggregate": "sum", "unit": "load", "parts": [{"type": "load",
"block": 0}, …]}` (1.2).

## 14. Athlete resolution

A compiled workout MAY be resolved for an athlete profile: `category` (`men` | `women`), `level`
(`rx` | `scaled` | `intermediate` | `foundations`), `units` (`kg` | `lb`) and one-rep maxes.
Resolution applies the level block, then the `Adapted:` block when there is one (§9.1), selects the
category value of every dual, converts to the preferred units and turns percentages into loads
rounded to the nearest 2.5 kg / 5 lb. A level factor (`A -> 2x B`) multiplies the quantity; on a
movement that takes its reps from a ladder it stays on the item as `factor`.

When the asked level is missing from the workout, resolution walks the levels from the asked one
**towards the easiest** (`rx` → `intermediate` → `scaled` → `foundations`), then back up towards Rx:
an athlete who asks for `scaled` in a workout that only offers `foundations` gets the foundations
work, and one who asks for `foundations` in a workout that only offers `scaled` gets the scaled work.
Rx is always the last resort, because every workout has it.

## 15. Diagnostics

Every diagnostic has a code, a severity, a message, a source span and, when possible, a suggestion.
Errors make compilation fail; warnings and infos do not.

| Code | Severity | Condition |
|---|---|---|
| E001 | error | syntax error (unexpected token) |
| E002 | error | tab in indentation |
| E003 | error | decimal comma |
| E004 | error | inconsistent indentation |
| E010 | error | unrecognised line |
| E011 | error | unknown label |
| E012 | error | unknown meta key |
| E013 | error | invalid meta value |
| E014 | error | statement not allowed here (e.g. `Odd:` outside an EMOM, `Teams of` not outermost, non-meta line in a session preamble, level block before the Rx work) |
| E015 | error | forbidden nesting (§4.2) |
| E016 | error | empty block |
| E020 | error | unknown movement |
| E030 | error | missing quantity |
| E031 | error | load without unit and no `units:` default |
| E032 | error | parameter kind not accepted by the movement |
| E033 | error | quantity kind not accepted by the movement |
| E034 | error | format without its required duration or count |
| E035 | error | value out of range (zero rounds, RPE > 10, percent > 200, …) |
| E036 | error | score incompatible with the format |
| E037 | error | a workout cap (`cap:`) combined with block caps (1.2, §6.1) |
| E040 | error | level block references a movement absent from the Rx work |
| E041 | error | duplicate level block |
| E050 | error | `use` path not found |
| E051 | error | `use` cycle |
| W100 | warning | implausible distance (e.g. `1 m Run`: did you mean `1 mi`?) |
| W101 | warning | women value greater than men value (reversed dual?) |
| W102 | warning | EMOM / interval work estimated above 90 % of the interval |
| W103 | warning | estimated duration wildly beyond the cap (more than 2.5×), which usually means a typo |
| W104 | warning | load far above the catalog reference (typo?) |
| W105 | warning | implausible quantity (more than 1000 reps) |

Duration estimates are not diagnostics: they are part of the compiled document (`estimate`, §13).
They are **indicative** — they come from the average paces of the catalog and a load factor — and
they are excluded from conformance (§16). Since 1.2, a `Max load` whose lifts carry no sets is
estimated as a build-up — its attempts (five efforts when none are written), each about 30 s, with
the rest between them (2:00 unless a `Rest` is written) — and the cap the estimate reports
(`capped_s`) is the workout's own, or, when several blocks carry a cap, their sum with the rests
between them.

## 16. Conformance

`spec/conformance/` contains pairs of files: `NAME.wod` with either `NAME.json` (expected compiled
output) or `NAME.diag` (expected diagnostics).

A `.diag` file holds one `CODE LINE` per line, in source order, and lists **every** diagnostic the
case produces — warnings included, and the cascading ones too (a rejected line that leaves its block
empty also reports `E016`).

An implementation conforms to WODCraft 1.2 when, for every case, it produces the same JSON (key
order and the `estimate` object excluded) or exactly that list of diagnostics.
