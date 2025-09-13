# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

WODCraft is a Domain-Specific Language (DSL) for describing CrossFit workouts (WODs). The architecture consists of three main components:

### Core Python CLI (`wodc_merged.py`)
- **Grammar**: Lark-based parser defining WOD syntax (lines 8-98)
- **AST Transformer**: Converts parsed tokens into structured JSON
- **Linter**: Validates DSL syntax and semantics (error codes: E010, E020, W001, W002, W050)  
- **Resolution**: Applies track/gender variants and catalog normalization
- **Timeline Generator**: Produces time-ordered workout sequences 
- **Exporters**: Outputs to JSON, HTML, ICS (calendar) formats

### MCP Server (`mcp/`)
TypeScript-based Model Context Protocol server providing:
- `draft_wod`: Generate WODs from constraints
- `lint_wod`: Bridge to Python linter with same error codes
- `compile_wod`: Parse DSL to JSON via Python grammar
- `to_markdown`: Render compiled JSON to Markdown
- Movement catalog resources and schema validation

### VS Code Extension (`editor/wodcraft-vscode/`)
Language support with syntax highlighting, snippets, and WOD DSL grammar rules.

## Development Commands

### WODCraft vNext (Extended Language)
```bash
# Parse and validate vNext files (.wodcraft)
python3 wodc_vnext.py validate examples/example_session.wodcraft
python3 wodc_vnext.py parse modules/warmup/full_body_10m.wodcraft

# Compile sessions with module resolution
python3 wodc_vnext.py session examples/example_session.wodcraft --modules-path modules --format json
python3 wodc_vnext.py session examples/example_session.wodcraft --format ics -o out/session.ics
```

### Python CLI (Legacy)
```bash
# Core workflow
python3 wodc_merged.py parse team_mixer.wod -o out/out.json    # Parse to AST
python3 wodc_merged.py lint team_mixer.wod --catalog box_catalog.json --track RX --gender male  # Validate
python3 wodc_merged.py run team_mixer.wod --format text        # Generate timeline
python3 wodc_merged.py export team_mixer.wod --to html -o out/wod.html  # Export formats

# Makefile shortcuts
make install        # Create .venv and install requirements
make lint          # Lint with catalog/track/gender
make demo          # Full workflow: lint + export all formats
make check-spec    # Strict validation (treat warnings as errors)
make fmt           # Format Python (Black) and WOD files
make test          # Run pytest suite
```

### MCP Server
```bash
cd mcp
npm install
npm run dev         # Development mode
npm run build       # TypeScript compilation
npm run typecheck   # Type checking
npm run lint        # ESLint
npm run format      # Prettier
npm run test        # Vitest
```

### Environment Variables (MCP)
- `WODCRAFT_PYTHON`: Python interpreter (default: python3)
- `WODCRAFT_CLI`: Path to wodc_merged.py
- `WODCRAFT_CATALOG`: Catalog JSON path
- `WODCRAFT_TRACK`: RX/INTERMEDIATE/SCALED
- `WODCRAFT_GENDER`: male/female

## DSL Structure and Validation

### Core Syntax Elements
- **Meta**: `WOD "Title"`, `TEAM N`, `CAP time`, `TRACKS [RX, SCALED]`
- **Segments**: `BUYIN {}`, `CASHOUT {}`, `REST time`, `BLOCK type {}`  
- **Block Types**: AMRAP, EMOM, FT, RFT, CHIPPER, TABATA, INTERVAL
- **Work Modes**: split:any/even, ygig, relay, waterfall, synchro
- **Quantities**: Reps, calories, distances, time holds, dual values (15/12)
- **Modifiers**: `@load`, `SYNC`, `@shared`, `@each`

### Lint Error Codes  
- **E010**: Invalid REST (must be > 0)
- **E020**: EMOM without time slots
- **W001**: Unknown movement (not in catalog)
- **W002**: Suspicious load values
- **W050**: Movement alias detected

### Resolution System
The linter/resolver applies track and gender variants:
- Dual values (`21/15`, `43/30kg`) resolve based on `--gender`
- `box_catalog.json` provides movement normalization and track-specific loads
- Track selection filters available variants (RX/INTERMEDIATE/SCALED)

## Testing Strategy

Tests cover all major components:
- `test_parser.py`: Grammar parsing and AST generation
- `test_lint.py`: Error detection and warning validation  
- `test_resolve.py`: Track/gender/catalog resolution
- `test_timeline.py`: Timeline generation accuracy
- `test_fmt.py`: DSL formatting preservation

Run with: `pytest -q` or `make test`

## File Organization

```
wodc_merged.py          # Main CLI with all functionality
WODCraft_spec.md       # Authoritative DSL specification
box_catalog.json       # Movement catalog for normalization
*.wod files            # Example workouts (team_mixer.wod, etc.)
tests/                 # Pytest test suite
mcp/                   # MCP server implementation  
editor/wodcraft-vscode/ # VS Code extension
out/                   # Generated artifacts (not committed)
```

## Key Implementation Details

- **Grammar Definition**: Lines 8-98 in wodc_merged.py define the complete Lark grammar
- **AST Structure**: JSON output has `meta` and `program` sections with workout segments
- **Dual Resolution**: Gender-based variants resolve at lint/export time, not parse time
- **Timeline Algorithm**: Processes blocks sequentially, handling work modes and team logistics
- **Export Templates**: HTML/ICS templates embedded in the main Python file

## WODCraft vNext Architecture

The vNext implementation extends WODCraft with a full language system:

### Extended Language Features
- **Module System**: Reusable components with namespacing (`warmup.full_body_10m@v1`)
- **Session Orchestration**: Assemble modules with parameter overrides
- **Type System**: Typed variables with unit conversions (Load, Distance, Time)
- **Import Resolution**: Pluggable resolver architecture (FileSystem, InMemory)
- **Parameter Overrides**: Type-safe variable substitution in sessions

### File Organization (vNext)
```
wodc_vnext.py           # Extended language implementation
modules/                # Reusable module library
  warmup/               # Warmup modules
  skill/                # Skill development modules  
  strength/             # Strength training modules
  wod/                  # WOD definitions
sessions/               # Session compositions
examples/               # Example sessions
```

### Module Development
Modules are defined in `.wodcraft` files with:
- Typed variables: `vars { percent_1rm: Load(%1RM) = 60%1RM }`
- Constraints: `[min=30%1RM, max=80%1RM]`
- Annotations: `@tag("oly", "technique")`
- Component definitions: `warmup`, `skill`, `strength`, `wod`

### Session Compilation
Sessions reference modules and can override parameters:
```wodcraft
session "Training Day" {
  components {
    skill import skill.snatch_technique@v1 override {
      percent_1rm = 65%1RM
      tempo = "32X1"
    }
  }
  scoring {
    skill LoadKg best_of_sets  
  }
}
```

When making changes to either grammar, update both `WODCraft_spec.md` (legacy) and grammar definitions in `wodc_vnext.py` for consistency.