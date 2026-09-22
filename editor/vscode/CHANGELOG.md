# Changelog

All notable changes to the WODCraft VS Code extension are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the extension
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-09-22

First release, tracking WODCraft language specification 1.0.

### Added

- TextMate grammar for `.wod`: formats (`For time`, `AMRAP`, `EMOM`, `E2MOM`, `Every … x N`,
  `Tabata`, `Death by`, `Max load`, `N rounds`, rep ladders and open ladders), labels
  (`Buy-in:`, `Cash-out:`, `Odd:`, `Even:`, `Min N:`, `Scaled:`, `Intermediate:`, `Foundations:`),
  meta keys, units (`kg`, `lb`, `pood`, `in`, `cm`, `m`, `km`, `mi`, `ft`, `cal`, `s`, `min`),
  dual values, percentages, `@`, `->`, `//` comments and `#` / `##` headings.
- Language configuration: `//` comments, `()` pairs, off-side folding, indentation rules.
- 17 snippets, each of which compiles with `wodc check`.
- A language client that starts `python -m wodcraft.lsp` and provides diagnostics, completion,
  hover, formatting, quick fixes and the document outline.
- Settings `wodcraft.pythonPath` (machine), `wodcraft.server.enabled`,
  `wodcraft.server.arguments` and `wodcraft.trace.server`.
- Command **WODCraft: Restart Language Server**.
- Limited support for untrusted workspaces, with `wodcraft.pythonPath` restricted.
