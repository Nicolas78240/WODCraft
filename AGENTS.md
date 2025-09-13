# Repository Guidelines (for Agents)

These guidelines describe how to work with this repository. They supersede old “legacy/vNext” notes: WODCraft is unified around one language and one CLI.

## Project Structure
- Spec: `WODCraft_spec.md` (authoritative DSL description; align grammar changes with it).
- Source (package): `src/wodcraft/`
  - `cli.py` — unified CLI entrypoint (`wodc`)
  - `sdk.py` — stable developer facade (parse/validate/compile_session/results/run/export_ics)
  - `lang/core.py` — facade re‑exporting the language core
- Language core (current source of truth): `wodc_vnext/core.py`
  - Contains `GRAMMAR_VNEXT`, transformer, SessionCompiler, TeamRealizedAggregator, ProgrammingLinter
  - Until fully merged under `src/`, make grammar/type changes here
- Examples: `examples/` (language, girls/heroes/open)
- Modules: `modules/` (module files resolved by sessions)
- Catalog:
  - Data: `data/movements_catalog.json` (+ seeds in `data/movements_seeds.json`)
  - Builder: `scripts/build_catalog.py`
- Editor: `editor/wodcraft-vscode/` (syntax, completion, CLI integration)
- Tests: `tests/` (pytest)

## Commands (Unified CLI)
- Validate: `wodc validate file.wod`
- Parse: `wodc parse file.wod`
- Session compile: `wodc session file.wod --modules-path modules --format json|ics`
- Results aggregate: `wodc results file.wod --modules-path modules`
- Timeline summary: `wodc run file.wod --modules-path modules --format text|json`
- Catalog build: `wodc catalog build`

Make targets:
- `make install` (venv + editable install)
- `make test` (pytest)
- `make catalog-build`
- `make build-dist` (sdist/wheel)

## Coding Style & Conventions
- Python 3, PEP 8, 4 spaces, ~100 cols. Type hints encouraged.
- Prefer small, focused functions; keep grammar tokens unique (avoid duplicate terminals in Lark).
- .wod is the only DSL extension. Python modules are lowercase with underscores.
- User‑facing wording must avoid “legacy/vNext”. Use “WODCraft” and “session/module/programming”.

## Grammar & Core Changes
- Edit `wodc_vnext/core.py`:
  - Update `GRAMMAR_VNEXT` carefully; avoid duplicate terminal names (e.g., DIST/MAXREP issue).
  - Keep transformer output consistent (AST shape used by tests and CLI).
  - If you touch durations/loads, sync helpers in compiler/aggregator.
- Run `pytest -q` after any grammar change.

## Testing
- Tests live in `tests/` and cover: parser, programming linter, resolver, team realized aggregation.
- Run: `pytest -q`. Aim to keep existing tests passing; add new focused tests when adding features.

## Packaging & Release
- PyPI package name: `wodcraft`; entrypoint `wodc`.
- Metadata in `pyproject.toml`. Bump version on user‑visible changes.
- Build: `make build-dist`; Publish: `twine upload dist/*` (CI preferred).
- Keep README (EN/FR) up to date; include Developer Quickstart and Integration.

## VS Code Extension
- Language id: `wodcraft`; uses the unified `wodc` CLI.
- Update `editor/wodcraft-vscode/` for syntax/completion/hover/codelens; no direct Python invocation in the extension.

## Security & Repo Hygiene
- Do not commit generated artifacts (dist/, out/, *.html, *.ics).
- `.pypirc.local` contains tokens; it must stay ignored by git.
- When building the catalog, commit only curated JSON (not transient scratch files).

## PR & Commit Guidelines
- Commits: Imperative present, concise subject (e.g., `cli: enrich --help`, `grammar: support RFT shorthand`).
- PRs: Describe intent, include CLI examples (command + short output), and note any AST changes.
- Keep diffs focused; update docs and examples alongside code changes.

## Developer API (Python)
- Prefer importing via `from wodcraft import sdk` for a stable surface:
  - `sdk.parse(text) -> dict`
  - `sdk.validate(text) -> (ok, error)`
  - `sdk.compile_session(text, modules_path) -> dict`
  - `sdk.export_ics(compiled) -> str`
  - `sdk.results(text, modules_path) -> dict`
  - `sdk.run(text, modules_path) -> dict`
- Lower‑level APIs are under `wodcraft.lang.core` if needed.
