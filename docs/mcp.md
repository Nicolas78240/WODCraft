# The WODCraft MCP server

The WODCraft 1.0 compiler, exposed over the [Model Context Protocol](https://modelcontextprotocol.io).
An assistant drafts a workout, `check_wod` tells it exactly what is wrong (code, line, column,
suggestion), it fixes the draft, and only hands back source that compiles.

Everything runs through the Python API in-process: no temporary files, no subprocesses.

## Install

```bash
pip install "wodcraft[mcp]"     # WODCraft + the MCP Python SDK (>= 2.2)
python -m wodcraft.mcp.server --help
```

From a checkout: `pip install -e ".[mcp]"`.

> The MCP SDK 2.x renamed `FastMCP` to `MCPServer`; the server uses that API. With `mcp<2` the
> import fails with an explicit message.

## Run

```bash
python -m wodcraft.mcp.server                       # stdio (default)
python -m wodcraft.mcp.server --http --port 8000    # streamable HTTP (the SDK transport)
```

| Option | Default | Meaning |
|---|---|---|
| `--http` | — | serve over streamable HTTP instead of stdio |
| `--host` | `127.0.0.1` | listen address |
| `--port` | `8000` | port |
| `--path` | `/mcp` | endpoint path |
| `--json-response` | — | answer with plain JSON instead of SSE |
| `--stateless` | — | keep no session between HTTP requests |

## Configure

**Claude Code**

```bash
claude mcp add wodcraft -- python -m wodcraft.mcp.server
```

**Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "wodcraft": {
      "command": "python",
      "args": ["-m", "wodcraft.mcp.server"]
    }
  }
}
```

With a virtualenv, give the full path to its interpreter. The specification ships inside the
package, so `wodcraft://spec` works from a plain `pip install`; `WODCRAFT_SPEC_DIR` overrides the
directory if you want to serve a working copy instead.

## Tools

| Tool | Input | Output |
|---|---|---|
| `check_wod` | `source` | `ok`, `errors`, `warnings`, `diagnostics[]` (code, severity, line, column, message, suggestion), `summary` |
| `compile_wod` | `source` | `document` and `documents[]`: the compiled JSON (SPEC §13) |
| `show_wod` | `source`, `category?`, `level?`, `units?` | `board`: the whiteboard view, resolved for that athlete |
| `format_wod` | `source` | `formatted`: the canonical form, and `changed` |
| `timeline_wod` | `source` | `segments[]` (`at_s`, `duration_s`, `label`, `kind`, `open_ended`), `total_s`, `rendered` |
| `search_movements` | `query?`, `family?`, `limit?` | `movements[]`: id, name, French and English aliases, family, quantities, parameter, Rx |
| `library_list` | `query?` | `workouts[]`: `use` path, title, tags |
| `library_get` | `path` | `source`, `title`, `tags`, `use_line` |

Every tool declares a JSON `outputSchema`. `check_wod`, `compile_wod`, `show_wod`, `format_wod` and
`timeline_wod` never raise on invalid source: they answer `ok: false` with the diagnostics.

## Resources

| URI | Content |
|---|---|
| `wodcraft://guide/syntax` | a short, exact syntax guide — **read this before writing** |
| `wodcraft://spec` | the full specification (`SPEC.md`) |
| `wodcraft://catalog` | the movement catalog, as JSON |
| `wodcraft://library` | the index of the standard library |
| `wodcraft://library/{path}` | one library workout, e.g. `wodcraft://library/girls/fran` |

Every DSL example in the guide, in the prompt and in this page is checked by the test suite: an
example that does not compile fails the build.

## Prompt

`design_wod(goal, duration?, equipment?, level?)` — asks for a workout built for a goal, a duration,
the available equipment and a level, and imposes the 1.0 syntax plus the draft → `check_wod` → fix loop.

## Example

`check_wod` on this draft:

```
# Engine builder
AMRAP 15
  200m Row
  15 Trusters 43/30
  10 Box jump 24/20 kg
```

answers:

```json
{
  "ok": false,
  "errors": 2,
  "diagnostics": [
    { "code": "E020", "severity": "error", "line": 4, "col": 6,
      "message": "Unknown movement 'Trusters'.",
      "suggestion": "did you mean 'Thruster' or 'Kettlebell thruster' or 'Dumbbell thruster'?" },
    { "code": "E032", "severity": "error", "line": 5, "col": 15,
      "message": "Box jump takes a height (in, cm), not a load." }
  ]
}
```

Fixing the two lines (`15 Thruster 43/30 kg`, `10 Box jump 24/20 in`) makes `check_wod` return
`ok: true`, and `show_wod` then renders the workout for any athlete.
