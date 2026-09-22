# WODCraft Language Specification — 1.0 (draft)

Status: draft · Editor: WODCraft project · License: CC BY-SA 4.0 (see `LICENSE-docs`)

The key words MUST, MUST NOT, SHOULD and MAY are to be interpreted as in RFC 2119.

## 1. Goals

WODCraft is a plain-text language to **prescribe** functional-fitness workouts (CrossFit-style WODs)
and whole training sessions. A WODCraft file:

1. reads like a gym whiteboard, so athletes can read it with no training;
2. is **strict**: anything ambiguous is rejected with a located, coded diagnostic;
3. compiles to a JSON document (see `workout.schema.json`) that applications exchange.

Out of scope for 1.0: multi-week programming, logged results.

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
3. otherwise, the **following sibling lines** at the same indentation, up to the next format line,
   label line, level label, heading, or end of body.

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

`FORMAT [, OPTION]*`. Options: `cap DURATION`, `teams of N`, `for time`.

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
| Tabata | `Tabata` · `Tabata N` | N rounds (default 8) of 20 s work / 10 s rest; children rotate |
| Death by | `Death by` | minute *k*: perform *k* reps of the (single) child movement, until failure |
| Max load | `Max load` · `Max load, cap DURATION` | build to the heaviest load for the prescribed reps |
| Sets | movement line with `NxM` / `N-N-N` (§7.3) | strength sets |

A rep ladder MAY use any number of values (`10-9-8-7-6-5-4-3-2-1`). An **open ladder** ends with `...`
and MUST have a constant step: `3-6-9 ...` means 3, 6, 9, 12… until the cap is reached (`E035` otherwise).
`Teams of N` MUST only appear on the outermost format line of a workout.

## 6. Label and meta lines

**Labels** open a block; text after the colon, if any, is a single child movement line.

| Label | Allowed in | Meaning |
|---|---|---|
| `Buy-in:` / `Cash-out:` | workout body | work before / after the main block, inside the clock |
| `Odd:` / `Even:` | EMOM, EnMOM | minutes 1, 3, 5… / 2, 4, 6… |
| `Min N:` | EMOM, EnMOM, Every | the N-th interval of each cycle (cycle length = highest N) |
| `Scaled:` / `Intermediate:` / `Foundations:` | workout body, after the Rx work | level adaptations (§9) |

**Meta lines** are `key: value` where the key is one of the following (case-insensitive; label and meta names never overlap):

| Key | Value | Where |
|---|---|---|
| `cap` | duration | workout |
| `score` | `time`, `rounds+reps`, `rounds`, `reps`, `load`, `distance`, `calories`, `none` | workout |
| `tiebreak` | free text | workout |
| `units` | `kg` or `lb` | workout, session — default unit for loads written without one |
| `vest` | load | workout |
| `stimulus`, `note` | free text | anywhere (repeatable) |
| `tags` | comma-separated words | workout, session |
| `date` | `YYYY-MM-DD` | session |
| `time` | `HH:MM` (local) | session |

An unknown key is an error (`E012`).

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
| distance, calories | `Row 500 m` | read as the quantity, when the movement accepts it and no quantity was written |

A number without unit in parameter position is a load in the `units:` default unit; without a
default it is an error (`E031`).

The parameter kind MUST match the catalog entry of the movement: a load on a box jump or a height
on a thruster is an error (`E032`).

### 7.5 Modifiers

In parentheses after the parameters: `sync`, `split`, `each`, `alternating`, `unbroken`, `strict`,
`per side`, `rest DURATION`, or free text in quotes — `("lateral over the dumbbell")`. A quoted
modifier may contain commas; commas outside quotes separate modifiers.

## 8. Rest

`Rest DURATION` is a timed pause item. As the **last item of a repeated block** it is performed
between rounds, not after the last one (5 rounds with a trailing `Rest 3:00` contain four rests). In a Sets context (`Back squat 5x5 (rest 2:00)`) use the modifier.

## 9. Levels

A workout written without level labels is **Rx**. A level block lists only the differences:

```wod
Scaled:
  Thruster 30/20 kg              // same movement: replace its parameters
  Pull-up -> Jumping pull-up     // replace the movement (parameters MAY follow)
  Box jump -> Step-up 20/16 in
```

- A line whose movement also appears in the Rx work replaces the parameters of **every** occurrence.
- `A -> B` replaces every occurrence of A by B, keeping quantities.
- To adapt only some occurrences, write the original parameters **before** the arrow; they select the
  occurrences to change: `Deadlift 225 lb -> Deadlift 155 lb`.
- A level block MAY also carry the meta lines `vest`, `cap` and `note`; `vest: none` removes the vest.
- A level block never changes quantities (`E014`): a workout with half the reps is a different workout.
- A movement that does not appear in the Rx work is an error (`E040`).

## 10. Use

`use PATH` inserts a workout from a library, e.g. `use girls/fran`. When a workout body (or a
session section) contains nothing but a `use` line, it **adopts** the referenced workout entirely —
its blocks, score, levels and notes — and keeps its own title. Elsewhere the referenced blocks are
inserted where the line stands, and must be allowed there (§4.2). PATH is resolved against, in
order: the directory of the current file, directories given to the compiler, the standard library.
An unresolved path is an error (`E050`) with suggestions. Cycles are an error (`E051`).
The standard library ships `girls/`, `heroes/` and `open/`.

## 11. Movement catalog

The catalog (`catalog/movements.toml`) is part of the standard. Each entry has an identifier
(`snake_case`), a canonical English name, English and French aliases, a family (`M` monostructural,
`G` gymnastics, `W` weightlifting), the quantities it accepts (reps, distance, calories, time), the
parameter kind it expects (load, height, none), and an average pace used for duration estimates.
Implementations MUST accept every catalog entry and MUST NOT accept names outside the catalog.
The first French alias is also the French display name (`wodc show --lang fr`).

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
| untimed `rounds` / ladder | `none`, or the declared `score:` (`reps`, `load`…) |
| several timed blocks in one workout | `multi`: one score per part |

An explicit score that cannot be measured by the main block is an error (`E036`), e.g. `score: rounds+reps`
on a `for_time` without cap. A workout whose body holds several timed blocks (a metcon then a heavy
single) scores `multi`, with one entry per part — that is also how a workout carries two scores.

## 13. Compiled output

Compiling a document produces a JSON object described by `spec/workout.schema.json`. In summary:

- `wodcraft`: spec version (`"1.0"`); `kind`: `"workout"` or `"session"`; `title`.
- Workout: `blocks` (tree of blocks and items), `score`, `levels`, `meta`, `team`.
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

## 14. Athlete resolution

A compiled workout MAY be resolved for an athlete profile: `category` (`men` | `women`), `level`
(`rx` | `scaled` | `intermediate` | `foundations`), `units` (`kg` | `lb`) and one-rep maxes.
Resolution applies the level block, selects the category value of every dual, converts to the
preferred units and turns percentages into loads rounded to the nearest 2.5 kg / 5 lb.
A level missing from the workout falls back to the closest easier-to-harder existing level, then Rx.

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
| E040 | error | level block references a movement absent from the Rx work |
| E041 | error | duplicate level block |
| E050 | error | `use` path not found |
| E051 | error | `use` cycle |
| W100 | warning | implausible distance (e.g. `1 m Run`: did you mean `1 mi`?) |
| W101 | warning | women value greater than men value (reversed dual?) |
| W102 | warning | EMOM / interval work estimated above 90 % of the interval |
| W103 | warning | estimated duration far beyond the cap (more than 1.5×) |
| W104 | warning | load far above the catalog reference (typo?) |
| W105 | warning | implausible quantity (more than 1000 reps) |
| I200 | info | estimated duration |

Duration estimates are **indicative**: they come from the average paces of the catalog and a load
factor, and they are excluded from conformance (§16).

## 16. Conformance

`spec/conformance/` contains pairs of files: `NAME.wod` with either `NAME.json` (expected compiled
output) or `NAME.diag` (expected diagnostic codes and lines, one `CODE LINE` per line).
An implementation conforms to WODCraft 1.0 when it produces, for every case, the same JSON (key order
and `estimate` excluded) or the same set of error codes and lines.
