# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

WODCraft 1.0 is a language for prescribing functional-fitness workouts, plus its reference
compiler. `spec/SPEC.md` is the source of truth for the language; the code implements it.
If the two disagree, the spec wins — fix the code, or change the spec deliberately.

## Layout

```
spec/            SPEC.md (language), workout.schema.json, conformance/ (NAME.wod + NAME.json|.diag)
src/wodcraft/
  syntax/        lexer.py (lines, tokens), lines.py (one line -> statement), parser.py (documents, block ownership)
  semantics/     compiler.py (resolve + check + emit JSON), estimate.py, resolve.py (athlete), measures.py
  emit/          source.py (canonical .wod = wodc fmt), board.py (whiteboard), markdown.py, ics.py, timeline.py
  catalog/       movements.toml (the catalog IS part of the standard), equivalences.toml, loader
  library/       girls/, heroes/, open/ — reachable from any file with `use girls/fran`
  api.py         compile_source / compile_file -> Result(documents, diagnostics, ok)
  cli.py         the `wodc` command      profile.py  athlete profile      diagnostics.py  codes
  mcp/  lsp/     MCP server (FastMCP) and language server (pygls), optional extras
tests/           pytest suite
```

## Commands

```bash
pip install -e ".[dev]"                       # Python 3.11+, no runtime dependency
pytest                                        # the whole suite, including conformance
wodc check src/wodcraft/library/*/*.wod       # the library must always compile
wodc fmt --check src/wodcraft/library/*/*.wod # and stay canonical
python spec/validate_schema.py                # compiled output vs the JSON schema
ruff check src tests && mypy
```

## The language, in short

```wod
# Fran
21-15-9 for time, cap 10:00
  Thruster 95/65 lb
  Pull-up

Scaled:
  Thruster 65/45 lb
  Pull-up -> Jumping pull-up
```

- `#` a document, `##` sections (a session). Meta lines: `cap:`, `score:`, `units:`, `vest:`,
  `note:`, `stimulus:`, `tags:`, `date:`, `time:`.
- Formats: `For time`, `N rounds [for time]`, `21-15-9`, `3-6-9 ...`, `AMRAP n`, `EMOM n`, `E2MOM n`,
  `Every 4:00 x 4`, `Tabata`, `Death by`, `Max load`, sets `5x5` / `5-5-3-3-1`.
- Movement line: `[quantity] Name [sets] [params] [(modifiers)]` — `21 Kettlebell swing 24/16 kg (sync)`.
- `43/30 kg` is men/women. `m` is always metres; minutes are `min` or `mm:ss`.

## House rules

- **Never write a DSL example you have not compiled.** Every snippet in docs, docstrings, prompts,
  snippets and guides must pass `wodc check`. The previous version of this project drifted exactly
  this way.
- Diagnostics carry a code from SPEC §15, an exact line and column, and a suggestion when possible.
  Add the code to the spec table when you add a check.
- A movement name that is not in `catalog/movements.toml` is an error: add the movement rather than
  loosening the resolver.
- Changing the compiled JSON means changing `spec/workout.schema.json` and the conformance fixtures.
- Keep the core dependency-free; `mcp` and `lsp` are optional extras.
