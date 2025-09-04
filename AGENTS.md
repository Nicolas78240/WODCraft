# Repository Guidelines

## Project Structure & Module Organization
- spec: `WODCraft_spec.md` (authoritative DSL description; follow when editing grammar).
- src: `wodc_merged.py` (CLI + parser, linter, runner, exporters).
- examples: `.wod` workout files (currently in repo root, e.g., `team_mixer.wod`).
- data: `box_catalog.json` (optional movement catalog used for normalization).
- outputs: Generated files (e.g., `out/out.json`, `out/wod.html`) should not be committed.

## Build, Test, and Development Commands
- Run parse: `python3 wodc_merged.py parse team_mixer.wod -o out.json`
  - Parses a `.wod` file and writes normalized AST JSON.
- Lint DSL: `python3 wodc_merged.py lint waterfall_trio.wod --catalog box_catalog.json --track RX --gender male`
  - Reports DSL issues and normalization warnings.
- Simulate/run: `python3 wodc_merged.py run synchro_waterfall_emom_t4.wod --format text`
  - Prints a time‑ordered timeline; use `--format json` for machine output.
- Export: `python3 wodc_merged.py export team_mixer.wod --to html -o wod.html`
  - Exports to `json`, `ics`, or `html`.
 - Make targets: `make help` (see `parse`, `lint`, `run`, `export-*`, `demo`, `check-spec`, `fmt`, `venv`, `install`). `fmt` includes Python (Black) and DSL (`wodc fmt`).

## Coding Style & Naming Conventions
- Python 3, PEP 8, 4‑space indentation; keep lines readable (~100 cols).
- Use type hints (`typing`) and descriptive `snake_case` names; constants `UPPER_SNAKE` (e.g., `GRAMMAR`, `KNOWN_MOVEMENTS`).
- Prefer small functions with clear responsibilities; keep regexes and parsing rules close to their usage.
- File naming: `.wod` for workouts; Python modules lowercase with underscores.

## Testing Guidelines
- Framework: Pytest (recommended). Place tests under `tests/` as `test_*.py`.
- Cover: parsing (`parse`), lint rules (`lint`), and exporters (`export --to json/html/ics`).
- Example: assert that parsing a sample `.wod` yields expected keys (`meta`, `program`) and `lint` exits non‑zero on errors.
- Run: `pytest -q` (add Pytest as a dev dependency in your environment).

## Commit & Pull Request Guidelines
- Commits: Imperative present, concise subject; include scope when helpful (e.g., `parser:`, `lint:`). Example: `lint: flag unknown movements (W001)`.
- PRs: Describe intent, link issues, include CLI examples (input `.wod`, command, expected output snippet). Screenshots for HTML export are helpful.
- Keep PRs focused; include/adjust sample `.wod` files when changing grammar.

## Security & Configuration Tips
- Catalogs: Use trusted JSON for `--catalog` (matches `box_catalog.json` schema assumptions).
- Validation first: Run `lint` before `run`/`export` to catch DSL mistakes.
- Do not commit generated artifacts (`*.html`, `*.ics`, `out.json`).
