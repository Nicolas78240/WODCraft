## What this changes

## Checklist

- [ ] `pytest`
- [ ] `wodc check src/wodcraft/library/*/*.wod` and `wodc fmt --check src/wodcraft/library/*/*.wod`
- [ ] `python spec/validate_schema.py`
- [ ] `ruff check src tests`
- [ ] Every DSL snippet I wrote (docs, docstrings, snippets, prompts) passes `wodc check`
- [ ] A language change also updates `spec/SPEC.md` and `spec/conformance/`
