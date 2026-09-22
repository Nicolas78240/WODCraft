# Changelog

## 1.0.0 — unreleased

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
- `wodc check | build | show | fmt | timer | export | catalog | lib`, with a canonical formatter.
- Python API (`wodcraft.api`), MCP server (`wodcraft[mcp]`) and language server (`wodcraft[lsp]`).
- Standard library of 40 benchmark workouts (Girls, Heroes, Open).
- CI on Python 3.11–3.13; the package ships with no runtime dependency.

## 0.3.2 and earlier

See the `v0.3-legacy` tag.
