# AGENTS.md

Instructions for autonomous agents contributing to WODCraft. Read `CLAUDE.md` first — it describes
the layout, the commands and the house rules. This file adds what matters when an agent works alone.

## Before you change anything

1. `pip install -e ".[dev,mcp,lsp]"` then `pytest` — the suite must be green before you start.
2. Read `spec/SPEC.md`. The language is specified, not improvised: a behaviour that is not in the
   spec is not a feature, it is a bug in one of the two.

## Definition of done

- `pytest` green, including `tests/test_conformance.py`.
- `wodc check src/wodcraft/library/*/*.wod examples/*.wod` and `wodc fmt --check …` both clean.
- `python spec/validate_schema.py` clean.
- `ruff check src tests` clean.
- Every DSL snippet you wrote — documentation, docstring, MCP guide, editor snippet — verified with
  `wodc check`.

## Language changes

Order matters: specification (`spec/SPEC.md`, including the diagnostic table §15) → conformance
fixtures (`spec/conformance/`) → implementation → library and documentation. A new diagnostic needs
a conformance case with its code and line.

## What not to do

- Do not add a runtime dependency to the core package.
- Do not relax the movement resolver to make a file compile; add the movement to the catalog.
- Do not commit generated artifacts, `node_modules`, or build output.
- Do not publish to PyPI, push tags, or deploy anything without being asked.
