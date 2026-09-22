"""Tests for the WODCraft language server: the handlers are called directly."""

from __future__ import annotations

from pathlib import Path

import pytest

lsp = pytest.importorskip("lsprotocol.types", reason="the language server needs pygls")
pytest.importorskip("pygls", reason="the language server needs pygls")

from pygls.workspace import Workspace  # noqa: E402

from wodcraft.api import LIBRARY_DIR  # noqa: E402
from wodcraft.lsp import analysis  # noqa: E402
from wodcraft.lsp import server as S  # noqa: E402
from wodcraft.lsp import vocabulary as vocab  # noqa: E402
from wodcraft.lsp.positions import from_utf16, to_utf16  # noqa: E402

URI = "file:///workspace/test.wod"

FRAN = """# Fran
tags: girls, benchmark
21-15-9 for time, cap 10:00
  Thruster 43/30 kg
  Pull-up

Scaled:
  Thruster 30/20 kg
  Pull-up -> Jumping pull-up
"""


# --------------------------------------------------------------------------- fixtures


@pytest.fixture()
def server():
    instance = S.create_server()
    instance.protocol._workspace = Workspace(
        None, lsp.TextDocumentSyncKind.Full, [], lsp.PositionEncodingKind.Utf16
    )
    return instance


def open_document(server, text: str, uri: str = URI, version: int = 1):
    server.workspace.put_text_document(
        lsp.TextDocumentItem(uri=uri, language_id="wodcraft", version=version, text=text)
    )
    S.did_open(server, lsp.DidOpenTextDocumentParams(text_document=lsp.TextDocumentItem(uri=uri, language_id="wodcraft", version=version, text=text)))
    return uri


def ident(uri: str = URI) -> lsp.TextDocumentIdentifier:
    return lsp.TextDocumentIdentifier(uri=uri)


# --------------------------------------------------------------------------- diagnostics


def test_valid_document_has_no_diagnostics(server):
    open_document(server, FRAN)
    assert S.diagnostics_for(server.analyse(URI)) == []


def test_unknown_movement_is_reported_at_the_exact_span(server):
    text = "# T\n21-15-9 for time\n  Thrustr 43/30 kg\n  Pull-up\n"
    open_document(server, text)
    (diagnostic,) = S.diagnostics_for(server.analyse(URI))
    assert diagnostic.code == "E020"
    assert diagnostic.severity == lsp.DiagnosticSeverity.Error
    assert diagnostic.source == "wodcraft"
    assert diagnostic.code_description.href.endswith("SPEC.md#15-diagnostics")
    # line 3 (0-based 2), columns 2..9 cover exactly "Thrustr"
    assert (diagnostic.range.start.line, diagnostic.range.start.character) == (2, 2)
    assert (diagnostic.range.end.line, diagnostic.range.end.character) == (2, 9)
    assert text.split("\n")[2][2:9] == "Thrustr"


def test_warning_and_info_keep_their_severity(server):
    open_document(server, "# T\nFor time\n  1 m Run\n")
    severities = {d.code: d.severity for d in S.diagnostics_for(server.analyse(URI))}
    assert severities.get("W100") == lsp.DiagnosticSeverity.Warning


def test_diagnostics_are_refreshed_on_change(server):
    open_document(server, "# T\nFor time\n  21 Thrustr 43/30 kg\n")
    assert "E020" in [d.code for d in S.diagnostics_for(server.analyse(URI))]
    fixed = "# T\nFor time\n  21 Thruster 43/30 kg\n"
    server.workspace.put_text_document(
        lsp.TextDocumentItem(uri=URI, language_id="wodcraft", version=2, text=fixed)
    )
    S.did_change(
        server,
        lsp.DidChangeTextDocumentParams(
            text_document=lsp.VersionedTextDocumentIdentifier(uri=URI, version=2),
            content_changes=[lsp.TextDocumentContentChangeWholeDocument(text=fixed)],
        ),
    )
    assert S.diagnostics_for(server.analyse(URI)) == []


def test_diagnostics_of_a_used_file_are_not_reported_here(server, tmp_path):
    used = tmp_path / "broken.wod"
    used.write_text("# Broken\nFor time\n  21 Nosuchmove\n", encoding="utf-8")
    main = tmp_path / "main.wod"
    text = "# Main\nuse broken\n"
    main.write_text(text, encoding="utf-8")
    uri = main.as_uri()
    open_document(server, text, uri)
    result = server.analyse(uri)
    assert any(d.span.file for d in result.diagnostics)  # the used file did report something
    assert [d.code for d in S.diagnostics_for(result)] == []


def test_did_close_clears_the_cache(server):
    open_document(server, FRAN)
    S.did_close(server, lsp.DidCloseTextDocumentParams(text_document=ident()))
    assert server.cache._items == {}


# --------------------------------------------------------------------------- completion


def _labels(items) -> list[str]:
    return [item.label for item in items]


def test_completion_on_an_empty_line_offers_formats_labels_meta_and_movements(server):
    open_document(server, "# T\n\n")
    items = S.completion(server, lsp.CompletionParams(text_document=ident(), position=lsp.Position(1, 0))).items
    labels = _labels(items)
    assert "For time" in labels and "AMRAP" in labels
    assert "Buy-in:" in labels and "Scaled:" in labels
    assert "cap:" in labels and "score:" in labels
    assert "Thruster" in labels


def test_completion_after_a_quantity_offers_movements_with_details(server):
    open_document(server, "# T\nFor time\n  21 \n")
    items = S.completion(server, lsp.CompletionParams(text_document=ident(), position=lsp.Position(2, 5))).items
    thruster = next(item for item in items if item.label == "Thruster")
    assert thruster.kind == lsp.CompletionItemKind.Value
    assert "weightlifting" in thruster.detail
    assert "Rx 43/30 kg" in thruster.detail
    assert "fr:" in thruster.detail
    assert "propulsion" in thruster.filter_text or "thruster" in thruster.filter_text.lower()
    assert not any(item.label == "AMRAP" for item in items)


def test_completion_after_a_load_offers_units(server):
    open_document(server, "# T\nFor time\n  21 Thruster 43/30 \n")
    items = S.completion(server, lsp.CompletionParams(text_document=ident(), position=lsp.Position(2, 20))).items
    labels = _labels(items)
    assert {"kg", "lb", "pood"} <= set(labels)
    assert all(item.kind == lsp.CompletionItemKind.Unit for item in items)


def test_completion_of_meta_values(server):
    open_document(server, "# T\nscore: \nFor time\n  21 Thruster 43/30 kg\n")
    items = S.completion(server, lsp.CompletionParams(text_document=ident(), position=lsp.Position(1, 7))).items
    assert set(_labels(items)) == set(vocab.SCORE_VALUES)


def test_completion_of_use_paths(server):
    open_document(server, "# T\nuse \n")
    items = S.completion(server, lsp.CompletionParams(text_document=ident(), position=lsp.Position(1, 4))).items
    assert "girls/fran" in _labels(items)


def test_every_completion_label_is_unique_per_category():
    items = S.completion_items("# T\n\n", 2, 1)
    assert len(items) == len({(item.label, item.kind) for item in items})


# --------------------------------------------------------------------------- hover


def test_hover_on_a_movement_describes_it(server):
    open_document(server, FRAN)
    result = S.hover(server, lsp.HoverParams(text_document=ident(), position=lsp.Position(3, 5)))
    assert result is not None
    text = result.contents.value
    assert "**Thruster**" in text
    assert "weightlifting" in text
    assert "Rx load: **43/30 kg**" in text
    assert "FR:" in text
    assert result.range.start.line == 3


def test_hover_uses_the_french_alias(server):
    open_document(server, "# T\nFor time\n  21 Traction\n")
    result = S.hover(server, lsp.HoverParams(text_document=ident(), position=lsp.Position(2, 8)))
    assert result is not None and "**Pull-up**" in result.contents.value


def test_hover_on_the_replacement_of_a_level_line(server):
    open_document(server, FRAN)
    result = S.hover(server, lsp.HoverParams(text_document=ident(), position=lsp.Position(8, 16)))
    assert result is not None and "**Jumping pull-up**" in result.contents.value


def test_hover_outside_a_movement_returns_none(server):
    open_document(server, FRAN)
    assert S.hover(server, lsp.HoverParams(text_document=ident(), position=lsp.Position(0, 2))) is None


# --------------------------------------------------------------------------- formatting


def _format(server, uri=URI):
    return S.formatting(
        server,
        lsp.DocumentFormattingParams(
            text_document=ident(uri), options=lsp.FormattingOptions(tab_size=2, insert_spaces=True)
        ),
    )


def test_formatting_rewrites_a_sloppy_document(server):
    open_document(server, "# t\nFOR TIME ,  cap 10:00\n      21 Thruster   43/30 kg\n      Pull-up\n")
    (edit,) = _format(server)
    assert edit.new_text == "# t\nFor time, cap 10:00\n  21 Thruster 43/30 kg\n  Pull-up\n"
    assert (edit.range.start.line, edit.range.start.character) == (0, 0)


def test_formatting_a_canonical_document_makes_no_edit(server):
    open_document(server, FRAN)
    assert _format(server) is None


def test_formatting_is_idempotent_on_the_standard_library(server):
    for path in sorted(LIBRARY_DIR.rglob("*.wod")):
        text = path.read_text(encoding="utf-8")
        once = analysis.format_document(text, str(path))
        assert once is None, f"{path.name} is not canonical"


def test_formatting_twice_reaches_a_fixed_point(server):
    messy = "#   Fran\nFOR TIME , cap 10:00\n  21 THRUSTER 43/30 KG\n"
    first = analysis.format_document(messy, None)
    assert first is not None
    assert analysis.format_document(first, None) is None


def test_formatting_refuses_a_document_with_syntax_errors(server):
    open_document(server, "# T\nFor time\n  21 Thruster (\n")
    assert _format(server) is None


# --------------------------------------------------------------------------- code actions


def _actions(server, line: int, uri: str = URI):
    return S.code_action(
        server,
        lsp.CodeActionParams(
            text_document=ident(uri),
            range=lsp.Range(lsp.Position(line, 0), lsp.Position(line, 40)),
            context=lsp.CodeActionContext(diagnostics=[]),
        ),
    )


def test_code_action_replaces_an_unknown_movement(server):
    open_document(server, "# T\n21-15-9 for time\n  Thrustr 43/30 kg\n  Pull-up\n")
    actions = _actions(server, 2)
    assert actions[0].title == "Replace with 'Thruster'"
    assert actions[0].kind == lsp.CodeActionKind.QuickFix
    assert actions[0].is_preferred is True
    (edit,) = actions[0].edit.changes[URI]
    assert edit.new_text == "Thruster"
    assert (edit.range.start.character, edit.range.end.character) == (2, 9)


def test_code_action_adds_a_missing_unit(server):
    open_document(server, "# T\nFor time\n  21 Thruster 43/30\n")
    titles = [action.title for action in _actions(server, 2)]
    assert titles[:2] == ["Add the unit 'kg'", "Add the unit 'lb'"]
    assert "Add 'units: kg' to the workout" in titles
    kg = _actions(server, 2)[0].edit.changes[URI][0]
    assert kg.new_text == " kg"
    assert kg.range.start == kg.range.end  # a pure insertion at the end of the load


def test_applying_the_unit_code_action_fixes_the_document(server):
    text = "# T\nFor time\n  21 Thruster 43/30\n"
    open_document(server, text)
    edit = _actions(server, 2)[0].edit.changes[URI][0]
    lines = text.split("\n")
    row = edit.range.start.line
    start, end = edit.range.start.character, edit.range.end.character
    lines[row] = lines[row][:start] + edit.new_text + lines[row][end:]
    fixed = "\n".join(lines)
    assert analysis.analyse(URI, fixed).own_diagnostics == []


def test_code_action_repairs_an_unknown_meta_key(server):
    open_document(server, "# T\ncpa: 10:00\nFor time\n  21 Thruster 43/30 kg\n")
    titles = [action.title for action in _actions(server, 1)]
    assert "Replace with 'cap:'" in titles


def test_code_action_repairs_a_decimal_comma(server):
    open_document(server, "# T\nFor time\n  21 Kettlebell swing 1,5 pood\n")
    actions = _actions(server, 2)
    assert any(action.title == "Replace with '1.5'" for action in actions)


def test_code_action_suggests_a_library_path(server, tmp_path):
    path = tmp_path / "main.wod"
    text = "# T\nuse girls/fram\n"
    path.write_text(text, encoding="utf-8")
    open_document(server, text, path.as_uri())
    titles = [action.title for action in _actions(server, 1, path.as_uri())]
    assert "Replace with 'use girls/fran'" in titles


def test_code_action_replaces_tabs_in_the_indentation(server):
    open_document(server, "# T\nFor time\n\t21 Thruster 43/30 kg\n")
    actions = _actions(server, 2)
    assert any(action.title == "Replace the tabs with spaces" for action in actions)


def test_no_code_action_without_a_diagnostic(server):
    open_document(server, FRAN)
    assert _actions(server, 3) == []


# --------------------------------------------------------------------------- document symbols


SESSION = """# Tuesday 23 September
date: 2026-09-23

## Warm-up
3 rounds
  10 Air squat
  10 Push-up

## Metcon
AMRAP 12:00
  Buy-in: 400 m Run
  10 Burpee
"""


def test_document_symbols_of_a_workout(server):
    open_document(server, FRAN)
    symbols = S.document_symbol(server, lsp.DocumentSymbolParams(text_document=ident()))
    assert [s.name for s in symbols] == ["Fran"]
    assert symbols[0].kind == lsp.SymbolKind.Namespace
    children = [child.name for child in symbols[0].children]
    assert "21-15-9 for time, cap 10:00" in children
    assert "Scaled:" in children


def test_document_symbols_of_a_session(server):
    open_document(server, SESSION)
    symbols = S.document_symbol(server, lsp.DocumentSymbolParams(text_document=ident()))
    (document,) = symbols
    assert document.name == "Tuesday 23 September"
    sections = [child.name for child in document.children]
    assert sections == ["Warm-up", "Metcon"]
    metcon = document.children[1]
    assert metcon.kind == lsp.SymbolKind.Module
    assert [b.name for b in metcon.children] == ["AMRAP 12:00"]
    assert [b.name for b in metcon.children[0].children] == ["Buy-in:"]


def test_document_symbol_ranges_cover_their_block(server):
    open_document(server, SESSION)
    (document,) = S.document_symbol(server, lsp.DocumentSymbolParams(text_document=ident()))
    warmup = document.children[0]
    assert warmup.range.start.line == 3  # "## Warm-up" is line 4
    assert warmup.range.end.line >= 6
    assert warmup.selection_range.start.line == warmup.range.start.line


def test_two_documents_in_one_file(server):
    open_document(server, FRAN + "\n" + "# Cindy\nAMRAP 20:00\n  5 Pull-up\n")
    symbols = S.document_symbol(server, lsp.DocumentSymbolParams(text_document=ident()))
    assert [s.name for s in symbols] == ["Fran", "Cindy"]


def test_symbols_of_the_standard_library_never_crash(server):
    for path in sorted(LIBRARY_DIR.rglob("*.wod")):
        result = analysis.analyse(path.as_uri(), path.read_text(encoding="utf-8"))
        assert analysis.document_symbols(result)


# --------------------------------------------------------------------------- positions


def test_utf16_conversion_round_trips_on_accented_text():
    text = "  21 Arraché 43/30 kg"
    for col in range(1, len(text) + 2):
        assert from_utf16(text, to_utf16(text, col)) == col


def test_diagnostic_columns_follow_utf16_units(server):
    # the emoji is a surrogate pair: its UTF-16 width is 2, its code-point width is 1
    line = '  21 Thruster ("\N{FLEXED BICEPS}") 43/30'
    open_document(server, f"# T\nFor time\n{line}\n")
    (diagnostic,) = [d for d in S.diagnostics_for(server.analyse(URI)) if d.code == "E031"]
    start, end = diagnostic.range.start.character, diagnostic.range.end.character
    assert line.encode("utf-16-le")[2 * start : 2 * end].decode("utf-16-le") == "43/30"
    assert start != line.index("43/30")  # a code-point column would have been wrong here


# --------------------------------------------------------------------------- server wiring


def test_create_server_registers_every_feature():
    server = S.create_server()
    registered = set(server.lsp.fm.features) if hasattr(server, "lsp") else set(server.protocol.fm.features)
    assert {
        lsp.TEXT_DOCUMENT_DID_OPEN,
        lsp.TEXT_DOCUMENT_DID_CHANGE,
        lsp.TEXT_DOCUMENT_DID_SAVE,
        lsp.TEXT_DOCUMENT_DID_CLOSE,
        lsp.TEXT_DOCUMENT_COMPLETION,
        lsp.TEXT_DOCUMENT_HOVER,
        lsp.TEXT_DOCUMENT_FORMATTING,
        lsp.TEXT_DOCUMENT_CODE_ACTION,
        lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL,
    } <= registered


def test_publish_diagnostics_does_not_raise_without_a_transport(server):
    open_document(server, "# T\nFor time\n  21 Thrustr 43/30 kg\n")
    assert "E020" in [d.code for d in S.publish_diagnostics(server, URI)]


# --------------------------------------------------------------------------- snippets


SNIPPETS = Path(__file__).resolve().parents[4] / "editor" / "vscode" / "snippets" / "wodcraft.json"


@pytest.mark.skipif(not SNIPPETS.is_file(), reason="the VS Code extension is not present")
def test_every_snippet_compiles():
    import json
    import re

    from wodcraft.api import compile_source

    placeholder = re.compile(r"\$\{\d+:([^{}]*)\}|\$\{\d+\|([^{},|]*)(?:,[^{}|]*)*\|\}|\$\d+")
    snippets = json.loads(SNIPPETS.read_text(encoding="utf-8"))
    assert snippets
    for name, snippet in snippets.items():
        body = snippet["body"]
        text = "\n".join(body) if isinstance(body, list) else body
        text = placeholder.sub(lambda m: m.group(1) or m.group(2) or "", text)
        text = text.replace("\\$", "$").replace("\t", "  ")
        result = compile_source(text + "\n")
        errors = [d for d in result.diagnostics if d.severity.value == "error"]
        assert not errors, f"snippet {name!r} does not compile: {[d.format() for d in errors]}\n{text}"
