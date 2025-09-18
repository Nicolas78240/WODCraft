# CLAUDE.md

Guidance for Claude Code when navigating the WODCraft repository.

## Architecture Overview

- **Python CLI (`src/wodcraft/cli.py`)** – entry point exposed as `wodc`; delegates to the language core for parsing, linting, session compilation, exports, and SDK helpers (`src/wodcraft/sdk.py`).
- **Language core (`wodc_vnext/core.py`)** – authoritative grammar (Lark), AST transformer (`ToAST`), compiler utilities, resolver, and lint infrastructure.
- **MCP server (`mcp/`)** – TypeScript bridge exposing tools such as `draft_wod`, `lint_wod`, `compile_wod`, and documentation resources for Claude Desktop.
- **VS Code extension (`editor/wodcraft-vscode/`)** – syntax highlighting, snippets, schema completion, and CLI integration.

## Day-to-day Commands

```bash
# Lint / parse / run WODCraft files
wodc lint examples/wod/progressive_farmer.wod
wodc parse examples/wod/progressive_farmer.wod
wodc session examples/session/sample_session.wod --modules-path modules --format json

# Python tests
pytest -q

# MCP development
cd mcp
npm install
npm run dev
npm run build

# Build & publish (Python)
python3 -m build
make publish-pypi
```

## DSL Quick Reference

```wod
module wod.sample.training v1 {
  notes: {
    stimulus: "Pull + engine",
    focus: ["Limiter les pauses", "Respiration"]
  }

  wod AMRAP 12:00 {
    20/16 cal Row
    REST 2:00
    15m Farmer_Carry PROGRESS("+15m/round") @22.5kg/15kg
  }

  score AMRAP {
    rounds: Rounds
    reps: Reps
  }
}
```

- Quantités supportées : `10`, `200m`, `20/16 cal`, `MAXREP`…
- Progression : `PROGRESS("+15m/round")`
- Charges duales : `@43kg/30kg`
- Repos internes : `REST 2:00`
- Types de score : `Time`, `Rounds`, `Reps`, `Distance(unit)`, `Load(unit)`, `Calories`, `Tempo`, `Int`, `Float`, `Bool`, `String`
- Pas de commentaires `#` – utiliser `//` ou `notes:`

### Sessions (assemblage de modules)

```wod
module wod.block.a v1 { wod AMRAP 7:00 { 10 Push_up 10 Sit_up 10 Pull_up } }
module wod.block.b v1 { wod EMOM 10:00 { 5 Thruster @43kg/30kg 5 Burpee } }
module wod.block.c v1 {
  wod ForTime cap 10:00 {
    21 Snatch @43kg/30kg
    21 Pull_up
    15 Snatch @43kg/30kg
    15 Pull_up
    9 Snatch @43kg/30kg
    9 Pull_up
  }
}

session "Pull Pyramid" {
  components {
    wod import wod.block.a@v1
    wod import wod.block.b@v1
    wod import wod.block.c@v1
  }
  scoring {
    wod ForTime time+reps
  }
}
```

## Testing & Linting

- `pytest` suite covers parser, transformer, resolver, compiler, lint rules, and SDK contracts.
- `npm run test` in `mcp/` runs Vitest for MCP utilities.
- `npm run lint`/`npm run typecheck` ensure the MCP stays healthy.

## File Organization

```
src/wodcraft/        # CLI, SDK, high-level helpers
wodc_vnext/          # Grammar + language core (to be migrated under src/)
WODCraft_spec.md     # DSL specification
mcp/                 # MCP server implementation
editor/              # VS Code extension
modules/             # Example module library
examples/            # Example workouts & sessions
tests/               # Pytest suite
```

## Notes for Claude

- Always prefer generating modules/sessions that lint with `wodc lint`.
- When drafting via MCP, fetch the structure guide (`wodcraft://guide/structure`) before producing DSL.
- Respect dual loads, REST blocks, score definitions, and include notes when clarifying stimulus or pacing.
