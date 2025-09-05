# WODCraft MCP Server

Model Context Protocol (MCP) server for designing, linting, and compiling WODs using the canonical WODCraft DSL and Python parser.

## Features
- draft_wod: generate a valid WODCraft DSL, compiled JSON, and Markdown (from constraints).
- lint_wod: real linter bridge to the Python CLI (same codes: E010, E020, W001, W002, W050...).
- compile_wod: parse DSL to structured JSON via the Python grammar.
- to_markdown: render compiled JSON to Markdown.
- generate_variants: suggest RX/INTERMEDIATE/SCALED adjustments.
- Resources: movement catalog, examples, compiled schema, and the DSL spec.

## Install
```bash
cd mcp
npm install
npm run dev   # start MCP server (stdio) for development
# or
npm run build && npm start
```

The server will attempt to locate the Python CLI (`wodc_merged.py`) in the repo root. You can override via env:
- WODCRAFT_PYTHON: python interpreter (default: python3)
- WODCRAFT_CLI: path to `wodc_merged.py`
- WODCRAFT_CATALOG: optional catalog JSON (e.g., ../box_catalog.json)
- WODCRAFT_TRACK: RX | INTERMEDIATE | SCALED (default RX)
- WODCRAFT_GENDER: male | female (default male)

## Claude Desktop wiring
Edit config:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

Recommended (global install):
```json
{
  "mcpServers": {
    "wodcraft": { "command": "wodcraft-mcp" }
  }
}
```

Local development:
```json
{
  "mcpServers": {
    "wodcraft": {
      "command": "node",
      "args": ["/absolute/path/to/this/repo/mcp/dist/server.js"]
    }
  }
}
```

Restart Claude Desktop. You’ll see WODCraft tools.

## Tools
- draft_wod: `mode`, `duration`, optional `teamSize`, `level`, `equipment`, `focus`, `name`.
- lint_wod: `{ dsl }` → issues with `level|code|path|message`.
- compile_wod: `{ dsl }` → canonical AST JSON.
- to_markdown: `{ compiled }` → Markdown.
- generate_variants: `{ compiled }` → adds `scales` suggestions.

## Resources
- wodcraft://movements → data/movements.json
- wodcraft://examples/basic → examples/example_basic.wod
- wodcraft://schema/compiled?v=0.1 → schemas/compiled_wod.schema.json
- wodcraft://spec → WODCraft_spec.md
