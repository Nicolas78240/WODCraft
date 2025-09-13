# WODCraft Language Support (VS Code)

Provides syntax highlighting and snippets for `.wod` files.

## Install (local, without publishing)

Option A — Extension Development Mode
- Open VS Code.
- Run: `Developer: Reload Window` (optional) to ensure a fresh session.
- Run: `Developer: Open Extensions Folder` to copy the folder, or use the command below.
- From the repository root:
  - VS Code: `code --extensionDevelopmentPath=./editor/wodcraft-vscode .`
  - Windsurf: open the folder and use “Run Extension” with the path `editor/wodcraft-vscode`.

Option B — Install from folder
- In VS Code, open the Command Palette → `Developer: Install Extension from Location...` and pick `editor/wodcraft-vscode`.

After installation
- `.wod` files are recognized as language `WODCraft`.
- Syntax highlighting is enabled for legacy and language constructs (module/session/programming/team/realized/achievements).
- Comments supported: `// line`, `/* block */`.
- Snippets:
  - Legacy: `amrap`, `emom`, `ft`, `rft`, `buyin`, `cashout`, `rest`.
  - Language blocks: `module`, `session`, `programming`, `team`, `realized`.

Autocomplete from catalog
- Set `wodcraft.catalogPath` (e.g. `box_catalog.json`) in settings.
- Movement IDs from the catalog appear in completion suggestions.

## Files
- `package.json` — extension manifest and contributions.
- `syntaxes/wod.tmLanguage.json` — TextMate grammar.
- `language-configuration.json` — brackets and indentation.
- `snippets/wod.json` — autocomplete snippets.

## Notes
- The DSL currently has no comment syntax in the grammar.
- You can still use the formatter `wodc fmt` to normalize spacing/blank lines.
