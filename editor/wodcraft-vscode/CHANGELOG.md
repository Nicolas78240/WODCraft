# WODCraft Language Support — Changelog
# WODCraft Language Support — Changelog

## 1.2.0
- Autocomplete improvements: add setting `wodcraft.preferredAsLabel` (default true) to show Preferred movement name as label while inserting snake_case id.
- Catalog integration: richer `preferred`, `aliases`, `category` metadata in suggestions.

## 1.1.0
- Uniformize file extension to `.wod` across repository; grammar recognizes `.wod`.
- Add vNext keywords highlighting: `module`, `vars`, `session`, `programming`, `team`, `realized`, `achievements`, etc.
- Enable comment syntax: `//` and `/* ... */`.
- Add vNext snippets: module, session, programming, team, realized.
- README updated for legacy + vNext usage.

## 0.1.0
- Initial release: legacy WODCraft syntax, basic snippets.
## 1.3.0
- vNext context-aware completions refined: units after `@`, tempo patterns, common durations, and module import scan with triggers.
- Minor stability tweaks in completion provider.

## 1.4.0
- vNext lint integration: auto-selects programming lint / validate / session compile and surfaces diagnostics (Pxxx/V001/C001).
- Override var introspection: parse imported module to suggest exact vars with type/default/constraints.
- Settings: `wodcraft.vnextCliPath`, `wodcraft.modulesPath`, `wodcraft.preferredAsLabel` with preferred label + snake_case insert.
