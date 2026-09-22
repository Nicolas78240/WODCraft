# WODCraft for VS Code

Editor support for [WODCraft](https://github.com/Nicolas78240/WODCraft) 1.0 — the plain-text
language that prescribes functional-fitness workouts (`.wod`).

## Features

Always available, no Python needed:

- syntax highlighting for formats (`For time`, `AMRAP`, `EMOM`, `E2MOM`, `Every … x N`, `Tabata`,
  `Death by`, `Max load`, `N rounds`, rep ladders such as `21-15-9`), labels (`Buy-in:`,
  `Cash-out:`, `Odd:`, `Even:`, `Min N:`, `Scaled:`), meta keys, units, dual values (`43/30`),
  percentages, `@`, `->`, `//` comments and `#` / `##` headings;
- snippets for every format, for levels and for a whole session — each one compiles as written;
- comment toggling, bracket matching and indentation-based folding.

With the language server (a Python interpreter that has `wodcraft` and `pygls`):

- **live diagnostics** as you type, with the exact span, the spec code (`E020`, `E031`, …) and a
  link to the relevant section of the specification;
- **completion** of movement names (with their family, Rx load and French aliases), format
  keywords, labels, meta keys and values, units, modifiers and `use` paths;
- **hover** on a movement: canonical name, catalog id, family, accepted quantities and parameters,
  Rx load and every English and French alias;
- **format document** (`Shift+Alt+F`) — the canonical form produced by `wodc fmt`;
- **quick fixes** for the diagnostics that carry a suggestion: replace an unknown movement with the
  closest catalog entry (`E020`), add the missing unit or a `units:` line (`E031`), fix a decimal
  comma (`E003`), repair an unknown meta key (`E012`) or label (`E011`), point a `use` line at an
  existing library workout (`E050`), replace tabs in the indentation (`E002`);
- **outline** of the file: `#` documents, `##` sections and the block tree.

## Requirements

The language server runs in-process in Python; nothing else is spawned and no temporary file is
written. Install it in the interpreter of your choice:

```bash
pip install 'wodcraft[lsp]'      # or: pip install wodcraft pygls
```

Then point the extension at that interpreter:

```jsonc
{
  "wodcraft.pythonPath": "/usr/local/bin/python3"
}
```

Python 3.11 or later is required.

## Settings

| Setting | Scope | Default | Meaning |
|---|---|---|---|
| `wodcraft.pythonPath` | machine | `python3` | Interpreter used to run `python -m wodcraft.lsp`. |
| `wodcraft.server.enabled` | window | `true` | Turn the server off to keep only highlighting and snippets. |
| `wodcraft.server.arguments` | machine | `[]` | Extra arguments for the server. |
| `wodcraft.trace.server` | window | `off` | Log the LSP traffic in the *WODCraft Language Server* output channel. |

## Commands

- **WODCraft: Restart Language Server** — after installing or changing the interpreter.

## Trusted and untrusted workspaces

Syntax highlighting and snippets work everywhere. Because starting the server means running a
Python interpreter, `wodcraft.pythonPath` is a *machine* setting and is restricted in untrusted
workspaces: a folder you have not trusted cannot point the extension at an interpreter of its own.
Virtual (remote, non-filesystem) workspaces are not supported.

If the interpreter cannot import the server, the extension says so once, keeps highlighting and
snippets working, and offers to open the setting or the log.

## Building from source

```bash
cd editor/vscode
npm install
npm run compile          # tsc -p ./  (strict)
npm run package          # vsce package -> wodcraft-1.0.0.vsix
```

## License

Apache-2.0. The WODCraft specification and documentation are CC BY-SA 4.0.
