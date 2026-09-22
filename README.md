# WODCraft

English | [Français](README.fr.md)

**Write a workout the way it goes on the whiteboard. Let a compiler check it.**

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
$ wodc show girls/fran --category women --units kg
FRAN
21-15-9 for time · cap 10:00
  Thruster ............................. 30 kg
  Pull-up
Score: time (capped: reps)
Estimate: 3:22–6:14
Stimulus: Short and intense; unbroken or near-unbroken sets.
[women · rx · kg]
```

WODCraft is an open language for **prescribing** functional-fitness workouts, plus a compiler that
turns them into JSON any app can consume. It is strict where it matters — units, movement names,
score coherence, plausibility — and relaxed where coaches need it: you write `Pull-up`, `pull ups`
or `tractions`, and `95/65 lb` stays `95/65 lb`.

## Why

- **Readable by athletes.** Every valid file can go straight on the wall.
- **Checked by a compiler.** `10 Box jump 24 kg` is refused: a box jump takes a height. `1 m Run`
  asks whether you meant `1 mi`. An EMOM with 25 thrusters a minute warns you it is not doable.
- **One interchange format.** The compiled JSON is described by a versioned
  [JSON Schema](spec/workout.schema.json); it is what timers, apps and AI agents exchange.
- **Yours to convert.** Loads carry both kg and lb, using the equivalences boxes actually use
  (95 lb ↔ 43 kg, 24 in ↔ 60 cm), and `--units lb` switches the whole view.

## Install

```bash
pip install wodcraft          # the language, the CLI, the catalog and the library
pip install "wodcraft[mcp]"   # + the MCP server for Claude and other AI agents
pip install "wodcraft[lsp]"   # + the language server used by the VS Code extension
```

Python 3.11+, no runtime dependency.

## Use

```bash
wodc check tuesday.wod              # diagnostics, with line, column and a suggestion
wodc show  tuesday.wod --me         # the whiteboard view, resolved for your profile
wodc build tuesday.wod -o out.json  # the compiled document
wodc fmt --write tuesday.wod        # canonical form, like gofmt
wodc timer fran.wod                 # what the clock does, segment by segment
wodc export ics week.wod            # a session in your calendar
wodc catalog thruster               # explore the movement catalog
wodc lib girls                      # the benchmark library
wodc show girls/fran --lang fr      # …and any of its workouts, by name
```

An athlete profile (`athlete.toml`, found in the current directory, a parent, or `~/.config/wodcraft/`)
turns prescriptions into your loads — there is one in [`examples/`](examples/):

```toml
category = "men"     # men | women
level     = "rx"     # rx | intermediate | scaled | foundations
units     = "kg"     # switch to "lb" when you train in North America
bodyweight_kg = 78

[1rm]
back_squat = 140
clean = 100
```

```console
$ wodc show examples/strength.wod --profile examples/athlete.toml
BACK SQUAT
Back squat ............ 5x5 105 kg (rest 2:30)
Estimate: 8:24–15:36
Note: Add 2.5 kg next week if every set moves well.
[men · rx · kg]
```

## The language in one minute

```wod
# Tuesday 23 September        // a session: '#' title, '## sections'
date: 2026-09-23

## Warm-up
2 rounds
  200 m Run
  10 Air squat

## Strength
Back squat 5x5 @ 75%          // percentages resolve against your 1RM

## Metcon
use girls/fran                // the standard library

## Extra
EMOM 12
Odd: 12/10 cal Row            // dual values are men/women
Even: 10 Burpee
```

Formats: `For time`, `N rounds [for time]`, rep ladders (`21-15-9`, `3-6-9 ...`), `AMRAP`, `EMOM`,
`E2MOM`, `Every 4:00 x 4`, `Tabata`, `Death by`, `Max load`, strength sets (`5x5`, `5-5-3-3-1`).
Labels: `Buy-in:`, `Cash-out:`, `Odd:`, `Even:`, `Min N:`, `Scaled:`, `Intermediate:`, `Foundations:`.
Units: `kg`, `lb`, `pood`, `in`, `cm`, `m`, `km`, `mi`, `ft`, `cal`, `s`, `min` — and `m` always
means metres, never minutes.

The full grammar, the semantics and every diagnostic are in **[spec/SPEC.md](spec/SPEC.md)**.

## Python API

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
print(workout["estimate"])       # {'min_s': 202, 'max_s': 374, ...}
```

## In your editor

The VS Code extension in [`editor/vscode/`](editor/vscode/) highlights `.wod` files on its own, and
turns on live diagnostics, movement completion, hover, formatting and quick fixes as soon as a Python
interpreter with `wodcraft[lsp]` is available. The language server is `python -m wodcraft.lsp`, so any
LSP-capable editor can use it.

## In an application

```bash
wodc bundle            # catalog.json, library.json and the schema: 115 kB an app can embed
```

- **Apple platforms** — [`swift/WODCraftKit`](swift/WODCraftKit) is a SwiftPM package with no third
  party dependency: the compiled model, the compiler, the catalog, the 40 benchmarks, the whiteboard
  and a timeline that drives a timer. It compiles **offline** and is validated by the same conformance
  suite as the reference implementation.
- **Anything else** — `pip install "wodcraft[service]"` runs a small HTTP service
  (`/compile`, `/check`, `/format`, `/show`, `/catalog`, `/library`). See [docs/service.md](docs/service.md).

## For AI agents

`wodcraft[mcp]` ships an MCP server that exposes the compiler itself — no shelling out, no temporary
files: `check_wod`, `compile_wod`, `show_wod`, `format_wod`, `timeline_wod`, `search_movements`,
`library_get`. An agent drafts a workout, the compiler answers with precise diagnostics, the agent
fixes it. See [docs/mcp.md](docs/mcp.md).

## The standard

WODCraft is meant to be implementable by anyone:

| Piece | Where |
|---|---|
| Language specification | [spec/SPEC.md](spec/SPEC.md) (CC BY-SA 4.0) |
| Compiled-document schema | [spec/workout.schema.json](spec/workout.schema.json) |
| Conformance suite | [spec/conformance/](spec/conformance/) — `.wod` + expected `.json` or `.diag` |
| Movement catalog | [src/wodcraft/catalog/movements.toml](src/wodcraft/catalog/movements.toml) — 200+ movements, FR/EN aliases |
| Benchmark library | [src/wodcraft/library/](src/wodcraft/library/) — Girls, Heroes, Open |
| Reference implementation | this repository (Apache-2.0) |
| Second implementation | [`swift/WODCraftKit`](swift/WODCraftKit) — Swift, validated by the same conformance suite |

## Contributing

Adding a movement, a benchmark workout or a French alias is the easiest way in: edit the catalog or
drop a `.wod` in the library, then run `pytest`. Language changes go through the specification first.

## License

Code: Apache-2.0. Specification and documentation: CC BY-SA 4.0 (see `LICENSE-docs`).
