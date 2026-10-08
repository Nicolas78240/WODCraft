# Changelog

## 1.2.1 — 2026-10-08

### Fixes
- `wodc timer` shows the caps of a session too: a section whose `cap:` covers several blocks gets its
  `cap: the clock stops` line at its place in the session — the section's start plus its cap — in
  clock order with the other sections' caps. It was compiled but not shown. Block caps and the cap of
  a single block still add no line. The MCP `timeline_wod` result shows these lines in `rendered`
  (its `cap_s` stays null for a session), and WODCraftKit has `Timeline.caps(of:)` and
  `Timeline.render(_:caps:)` behind `timerText()`; Python has `timer_caps`. A new conformance case,
  `session_section_caps`, carries such a session.

### Docs
- The MCP server, its syntax guide and its prompt name the spec version they implement (they said 1.0).
- `docs/mcp.md` lists `timeline_wod`'s `cap_s`; `integration-oko.fr.md` gets a dated status box.

## 1.2.0 — 2026-10-08

The CrossFit Total, decided with Nicolas on 8 October 2026. Every 1.0 and 1.1 document still
compiles to exactly the same JSON, with the same stamp; a document that uses a 1.2 construct is
stamped `"1.2"`, and the schema accepts all three.

### The language
- **Attempts**: `Max load, 3 attempts` (French `3 essais`, written back in English by `wodc fmt`).
  The best attempt counts; a `Rest` written last in the block is the rest **between** the attempts
  (three attempts, two rests). Elsewhere than on Max load it is `E014`; fewer than one is `E035`.
- **Totals**: `score: load, total` (French `charge, total`) adds the parts up. Over several timed
  blocks the score is `{"type": "multi", "aggregate": "sum", "unit": "load", "parts": […]}`, every
  part scored by the value (`E036` on a part that cannot be); over a single block it is the value
  with `"aggregate": "sum"` (`score: reps, total` for Lynne). `total` is the only modifier (`E013`).
- **One cap or the other** (SPEC §6.1): `cap:` caps the whole workout — on a single block it is still
  that block's cap; over several blocks it is the workout's new `cap_s` instead of the first block's.
  Combined with block caps it is the new **`E037`**, instead of disappearing without a word.

### The library
- New collection **`benchmarks/`** with `crossfit_total` (`use benchmarks/crossfit_total`): back
  squat, shoulder press, deadlift, three attempts each, 2:00 between attempts, 3:00 between lifts,
  and no cap, like the original (the library keeps only official caps).
- Lynne scores `reps, total`, and its note no longer explains the count.

### Fixes
- Several block caps now add up in `estimate.capped_s`, with the rest between the blocks (three lifts
  capped at 10:00 reported 10:00).
- A `Max load` without sets is estimated as a build-up — its attempts, or five efforts, about 30 s
  each with the rest between them — instead of a few seconds (the Total went from 0:09 to
  17:38–32:46). The timer sizes such a lift on its own.
- `wodc show --lang fr` translates the board's labels: `Charge max · 3 essais`, `Repos`,
  `Score : total des charges (meilleur essai de chaque barre)`, `Durée :`, `Note :`… Format names
  other than Max load stay in English, as on French-speaking whiteboards.
- `wodc timer` shows the cap of the whole workout as the moment the clock stops
  (`   30:00          cap: the clock stops`), in its place in time; block caps change nothing. The
  MCP `timeline_wod` result carries it as `cap_s`, and WODCraftKit has `Timeline.cap(of:)`,
  `Timeline.render(_:cap:)` and `timerText()`.
- `wodc lib` aligns its columns on the longest path.

### Tooling
- Schema `spec/workout.schema.json` moves to `…/schema/1.2/`: `attempts` on a block, `aggregate`
  and `unit` on the score, `cap_s` on the workout; seven new conformance cases.
- `swift/WODCraftKit` implements all of the above (`Block.attempts`, `Score.aggregate`,
  `Score.unit`, `Score.isTotal`, `Workout.capS`, the French board), checked by the same conformance
  suite and by the differential check.
- Editor grammar, completions and the MCP guide know attempts, totals and `E037`.

## 1.1.1 — 2026-10-08

### Catalog
- Five movements validated by the product owner from a real board (oKo, 6 October): `commando_push_up`,
  `box_bar_muscle_up`, `kettlebell_side_bend`, `press_back` and `harlow` (228 movements). `press_back`
  and `harlow` are minimal entries — name and French name only — until their standard is described.

### Packaging
- A `Package.swift` at the root of the repository: an application can depend on
  `https://github.com/Nicolas78240/WODCraft` at an exact tag. `swift/WODCraftKit/Package.swift` stays
  where the tests run.

### Docs
- `docs/amelioration-continue.fr.md`: how a gap found in an application becomes a WODCraft change, and
  how the application picks up the release.

## 1.1.0 — 2026-10-04

Additions for real training sessions (the whiteboard of 29 September: warm-up, skill, team chipper,
core work). Every 1.0 document still compiles to exactly the same JSON, stamped `"wodcraft": "1.0"`;
a document that uses a 1.1 construct is stamped `"1.1"`, and the schema accepts both.

### The language
- **Generic ergometer**: `ergometer` (`ergo`, `cal ergo`, `machine`, `ergomètre`), in calories,
  distance or time; the machine is chosen when the score is logged. Also `yoga push-up` and the
  `scap pull` alias.
- **`hold`**, a standard modifier: `1 Wall walk (hold 10 s)`; the duration adds to every rep in
  estimates.
- **Alternatives**: `10 Ring row | 8 Scapular pull-up`. The item is the first option, the others go
  in `or`; an option without a quantity takes the first one's; levels apply to every option; the board
  says "or" ("ou" in French).
- **Level quantities**, after the arrow only: `Chest-to-bar pull-up -> 2x Ring row` (factor),
  `Wall walk -> 3 Inchworm` (new quantity). Any other quantity in a level block is still `E014`.
- **There and back**: `For time, teams of 2, cap 25:00, there and back` (`aller-retour` accepted) —
  the list in order, then back without repeating the last line. The block and its score carry
  `there_and_back`; estimates count the whole path.
- **`Adapted:`**: what one athlete actually did, with the same lines as a level plus bare counts
  (`5 Wall walk`). Compiled in `adapted`; resolution applies it after the chosen level and sets
  `resolved.adapted`.

### The library
- **Christine** joins the Girls (22), and the Heroes grow from 10 to 51: Adam Brown, Arnie, Blake,
  Brenton, Bull, Bulger, Capoot, Coe, Daniel, Danny, Erin, Forrest, Garrett, Griff, Hall, Hansen,
  Helton, Jack, Jason, Johnson, Joshie, Luce, Lumberjack 20, Marco, McGhee, Mr. Joshua, Nutts, PK,
  Paul, RJ, Roy, Ryan, Servais, Severin, Stephen, The Seven, Thompson, Tommy V, Tyler, War Frank,
  Whitten. Prescriptions follow the CrossFit definitions; where the original gives men's loads only,
  the women's load is the commonly used one and a `note:` says so.
- New catalog movements: `l_pull_up`, `ring_push_up`, `ring_handstand_push_up`,
  `dumbbell_squat_clean`, `dumbbell_split_clean`, `kettlebell_overhead_squat`,
  `plate_overhead_lunge`, `plate_carry`, `stiff_legged_deadlift` (the `stiff leg deadlift` alias moves
  from `romanian_deadlift` to it).

### Fixes
- `wodc fmt` no longer turns `AMRAP 5:00` + `1-2-3 ...` into a bare ladder (it dropped the clock).
- The board shows the ladder of an AMRAP: `AMRAP 5:00 · 1-2-3 …`.

### Tooling
- Schema `spec/workout.schema.json` moves to `…/schema/1.1/`: `or`, `factor`, `quantity` on level
  operations, `there_and_back`, `adapted`, `resolved.adapted`; every expected conformance document is
  now validated against it.
- `swift/WODCraftKit` implements all of the above (`Movement.or` / `options`, `Movement.factor`,
  `LevelOperation.factor` / `quantity`, `Block.thereAndBack`, `Score.thereAndBack`,
  `Workout.adapted`, `Resolved.adapted`), with the same conformance suite.
- New example: `examples/session-2026-09-29.wod`.

## 1.0.0 — not released on its own (first published as 1.1.0)

Complete rewrite. WODCraft is now a specified language with a reference compiler, and the old
`module … { wod ForTime { … } }` syntax is gone (the previous implementation is archived under the
`v0.3-legacy` tag).

### The language
- New whiteboard-first syntax: `21-15-9 for time, cap 10:00`, `AMRAP 12`, `EMOM 10`, `E2MOM 20`,
  `Every 4:00 x 4`, `Tabata`, `Death by`, `Max load`, `5x5 @ 75%`, `Buy-in:` / `Cash-out:`,
  `Odd:` / `Even:` / `Min N:`, levels `Scaled:` / `Intermediate:` / `Foundations:`, sessions with
  `#` and `##`, and `use girls/fran` for the standard library.
- Dual men/women values (`95/65 lb`), `m` always means metres, and `mi`, `ft`, `pood`, `cal`, `%`,
  `bw` and `RPE` are part of the language.
- Specification: `spec/SPEC.md`, with a JSON Schema for the compiled document and a conformance suite.

### The compiler
- Diagnostics with a code, an exact line and column, and a suggestion — including movement typos,
  wrong parameter kinds (a load on a box jump), incoherent scores, implausible distances, reversed
  men/women loads, overloaded EMOM intervals and caps shorter than the estimate.
- Movement catalog of 200+ entries with French and English aliases; kg ↔ lb and cm ↔ in conversions
  use the equivalences boxes actually use.
- Athlete resolution: category, level, preferred units, one-rep maxes and bodyweight.
- Duration estimates for workouts and sessions.

### Tooling
- `wodc check | build | show | fmt | timer | export | catalog | lib`, with a canonical formatter,
  an athlete profile (`--me`), French movement names (`--lang fr`) and library names
  (`wodc show girls/fran`).
- Python API (`wodcraft.api`, `wodcraft.library`, `wodcraft.resources`), MCP server with 8 tools
  (`wodcraft[mcp]`) and a language server with diagnostics, completion, hover, formatting and quick
  fixes (`wodcraft[lsp]`), plus a VS Code extension.
- Standard library of 40 benchmark workouts (Girls, Heroes, Open); the specification and the JSON
  schema ship inside the package.
- `wodc bundle` writes the JSON an application embeds (catalog, library, schema: 115 kB).
- `swift/WODCraftKit`: the language in Swift for iOS, watchOS and macOS — compiled model, compiler,
  catalog, library, whiteboard and timeline, offline, validated by the conformance suite.
- `wodcraft[service]`: a small HTTP compile service, with a Dockerfile that builds.
- 1 572 tests, 68 conformance cases, 98 % coverage; CI on Python 3.11–3.13; no runtime dependency.
- The two implementations are compared against each other on thousands of generated sources
  (`make swift-diff`), not only on the conformance fixtures.

## 0.3.2 and earlier

See the `v0.3-legacy` tag.
