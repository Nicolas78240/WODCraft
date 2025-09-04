# WODCraft

English | [Français](README.fr.md)

WODCraft is a Domain‑Specific Language (DSL) to describe, validate, and export Workouts of the Day (WODs). It ships a single CLI to parse, lint, simulate (timeline), and export (JSON/HTML/ICS) workouts, with support for tracks (RX/Intermediate/Scaled) and gender (male/female).

## Why
- Standardize how WODs are written, readable by coaches and tools.
- Automate useful formats: timer timeline, calendar, web, API.
- Normalize variants (tracks, dual reps/cals/loads) via a JSON catalog.
- Provide a solid base for AI agents to analyze/generate WODs.

## DSL at a Glance
```wod
WOD "Team Mixer"
TEAM 2
TRACKS [RX, INTERMEDIATE, SCALED]
CAP 20:00

BUYIN {
  400m run;
}

BLOCK AMRAP 12:00 WORK split:any {
  12 wall_balls @9kg SYNC;
  10 box_jumps @24in;
  200m run;
}

CASHOUT {
  50 double_unders @each;
}
```
The full grammar and rules are in WODCraft_spec.md (source of truth).

## Features
- Parser → structured JSON AST.
- Linter → errors/warnings (e.g., E010 REST>0, E020 EMOM without slots, W001 unknown movement, W002 suspicious load, W050 alias).
- Resolution → applies `--track`/`--gender` and an optional JSON `--catalog`.
- Timeline → `run` produces an event sequence (text or JSON).
- Export → `export` to `json`, `html`, `ics`.
- Formatting → `fmt` (minimal safe normalization of `.wod` files).

## Quick Setup
- Python 3 recommended. Isolated env:
  - `make install` (creates `.venv` and installs `requirements.txt`)
  - or `pip install -r requirements.txt`

## CLI Usage
- Parse: `python3 wodc_merged.py parse team_mixer.wod -o out/out.json`
- Lint: `python3 wodc_merged.py lint team_mixer.wod --catalog box_catalog.json --track RX --gender female`
- Timeline (text): `python3 wodc_merged.py run team_mixer.wod --format text`
- Export HTML: `python3 wodc_merged.py export team_mixer.wod --to html -o out/wod.html`
- Format: `python3 wodc_merged.py fmt team_mixer.wod -i`

Makefile shortcuts: `make help` (parse, lint, run, export-*, demo, check-spec, fmt, venv, install).

## Tests
- Run: `make test` or `pytest -q`
- Coverage includes: parser, lint (E/W), resolution (catalog/gender), timeline, formatter.

## Spec and Architecture
- DSL spec: see `WODCraft_spec.md`.
- Implementation: `wodc_merged.py` (Lark grammar + transformer, linter, timeline, exports, fmt).
- Examples: `.wod` files at repo root (team_mixer, waterfall_trio, …). Catalog: `box_catalog.json`.

## Roadmap
- Advanced formatter (indentation/blocks), macros and shorthands (`21-15-9`).
- Versioned grammar and canonical `wodc fmt`.
- Executable timer for gym use.

## Contributing
- Read `AGENTS.md` (conventions, structure, commands).
- Open focused PRs with CLI examples and export artifacts.

© WODCraft — 2025
