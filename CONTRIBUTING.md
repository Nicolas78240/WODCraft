# Contributing to WODCraft

## Getting set up

```bash
pip install -e ".[dev]"
pytest
```

Python 3.11+. The core package has no runtime dependency, and it should stay that way.

## The easy contributions

**A movement.** Add an entry to `src/wodcraft/catalog/movements.toml`: identifier in `snake_case`,
canonical English name, English and French aliases, family (`M`/`G`/`W`), the quantities it accepts,
the parameter it expects (`load`, `height` or `none`), and an average pace. No alias may collide with
another movement.

**A benchmark workout.** Drop a `.wod` in `src/wodcraft/library/`, run `wodc check` and
`wodc fmt --write` on it, and say in the pull request where the workout comes from. Accuracy matters
more than volume: a wrong benchmark is worse than a missing one.

**A French alias.** `fr = [...]` in the catalog — this is how a French athlete writes `Tractions`
and still gets `pull_up`.

## Changing the language

The specification comes first. In order:

1. `spec/SPEC.md` — including the diagnostic table in §15 when you add a check.
2. `spec/conformance/` — a case with the expected JSON, or the expected diagnostic codes and lines.
3. The implementation.
4. The library, the README and the editor support.

A behaviour that is not in the specification is a bug in one of the two.

## Before you open a pull request

```bash
pytest
wodc check src/wodcraft/library/*/*.wod
wodc fmt --check src/wodcraft/library/*/*.wod
python spec/validate_schema.py
ruff check src tests
```

Every DSL snippet you write — in docs, docstrings, editor snippets or MCP guides — must pass
`wodc check`. Drift between documentation and implementation is how the previous version of this
project died.

## Licensing

Code is Apache-2.0; the specification and documentation are CC BY-SA 4.0. By contributing you agree
to publish your work under those licences.
