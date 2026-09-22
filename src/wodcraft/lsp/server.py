"""The WODCraft language server (LSP), built on `pygls`.

Run it over stdio with ``python -m wodcraft.lsp``. Everything is computed in-process from
:mod:`wodcraft.api`: no subprocess is spawned and no temporary file is written.

Handlers are plain module-level functions, registered on a server instance by
:func:`create_server`. That keeps them directly callable from tests.
"""

from __future__ import annotations

import logging
from typing import Any

try:  # pygls >= 2
    from pygls.lsp.server import LanguageServer
except ImportError as exc:  # pragma: no cover - depends on the installed pygls
    raise ImportError(
        "The WODCraft language server needs pygls 2: pip install 'pygls>=2,<3'"
    ) from exc

from lsprotocol import types as lsp

from wodcraft import __version__
from wodcraft.lsp import vocabulary as vocab
from wodcraft.lsp.analysis import Analysis, AnalysisCache, Edit, Fix, analyse, code_actions, document_symbols, format_document, movement_at
from wodcraft.lsp.positions import line_text, position_to_col, span_range

logger = logging.getLogger(__name__)

SERVER_NAME = "wodcraft"
LANGUAGE_ID = "wodcraft"
DIAGNOSTIC_SOURCE = "wodcraft"
SPEC_URL = "https://github.com/Nicolas78240/WODCraft/blob/main/spec/SPEC.md#15-diagnostics"

SEVERITY = {
    "error": lsp.DiagnosticSeverity.Error,
    "warning": lsp.DiagnosticSeverity.Warning,
    "info": lsp.DiagnosticSeverity.Information,
}

SYMBOL_KIND = {
    "document": lsp.SymbolKind.Namespace,
    "section": lsp.SymbolKind.Module,
    "block": lsp.SymbolKind.Function,
}

COMPLETION_TRIGGERS = [" ", "@", "/", ":", "-", "%"]


class WodcraftLanguageServer(LanguageServer):
    """A ``LanguageServer`` that keeps one :class:`Analysis` per open document."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cache = AnalysisCache()

    def analyse(self, uri: str) -> Analysis:
        document = self.workspace.get_text_document(uri)
        return self.cache.get(uri, document.source, getattr(document, "version", None))


# --------------------------------------------------------------------------- diagnostics


def to_lsp_diagnostic(diagnostic, lines: list[str]) -> lsp.Diagnostic:
    """A compiler diagnostic, with its exact span, as an LSP diagnostic."""
    (start_line, start_char), (end_line, end_char) = span_range(diagnostic.span, lines)
    message = diagnostic.message
    if diagnostic.suggestion:
        message = f"{message}\nhelp: {diagnostic.suggestion}"
    return lsp.Diagnostic(
        range=lsp.Range(lsp.Position(start_line, start_char), lsp.Position(end_line, end_char)),
        message=message,
        severity=SEVERITY.get(diagnostic.severity.value, lsp.DiagnosticSeverity.Information),
        code=diagnostic.code,
        code_description=lsp.CodeDescription(href=SPEC_URL),
        source=DIAGNOSTIC_SOURCE,
    )


def diagnostics_for(analysis: Analysis) -> list[lsp.Diagnostic]:
    return [to_lsp_diagnostic(d, analysis.lines) for d in analysis.own_diagnostics]


def publish_diagnostics(ls: WodcraftLanguageServer, uri: str) -> list[lsp.Diagnostic]:
    analysis = ls.analyse(uri)
    items = diagnostics_for(analysis)
    ls.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=uri, version=analysis.version, diagnostics=items)
    )
    return items


def did_open(ls: WodcraftLanguageServer, params: lsp.DidOpenTextDocumentParams) -> None:
    publish_diagnostics(ls, params.text_document.uri)


def did_change(ls: WodcraftLanguageServer, params: lsp.DidChangeTextDocumentParams) -> None:
    publish_diagnostics(ls, params.text_document.uri)


def did_save(ls: WodcraftLanguageServer, params: lsp.DidSaveTextDocumentParams) -> None:
    publish_diagnostics(ls, params.text_document.uri)


def did_close(ls: WodcraftLanguageServer, params: lsp.DidCloseTextDocumentParams) -> None:
    ls.cache.drop(params.text_document.uri)
    ls.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[])
    )


# --------------------------------------------------------------------------- completion


def _movement_items() -> list[lsp.CompletionItem]:
    items: list[lsp.CompletionItem] = []
    for movement in vocab.catalog().movements.values():
        items.append(
            lsp.CompletionItem(
                label=movement.name,
                kind=lsp.CompletionItemKind.Value,
                detail=vocab.movement_detail(movement),
                documentation=lsp.MarkupContent(lsp.MarkupKind.Markdown, vocab.movement_documentation(movement)),
                filter_text=vocab.movement_filter_text(movement),
                insert_text=movement.name,
                sort_text=f"20{movement.name}",
            )
        )
    return items


def _simple(label: str, kind: lsp.CompletionItemKind, detail: str, doc: str, order: str) -> lsp.CompletionItem:
    insert = label
    return lsp.CompletionItem(
        label=label.strip() or label,
        kind=kind,
        detail=detail,
        documentation=lsp.MarkupContent(lsp.MarkupKind.Markdown, doc),
        insert_text=insert,
        sort_text=f"{order}{label.strip()}",
    )


def completion_items(text: str, line: int, col: int, path: str | None = None) -> list[lsp.CompletionItem]:
    """The completions offered at the 1-based (line, col) cursor of ``text``."""
    from wodcraft.lsp.positions import text_lines

    lines = text_lines(text)
    prefix = line_text(lines, line)[: max(0, col - 1)]
    context = vocab.line_context(prefix)
    categories = context.categories
    items: list[lsp.CompletionItem] = []

    if "use_path" in categories:
        from pathlib import Path

        base = Path(path).parent if path else None
        return [
            _simple(target, lsp.CompletionItemKind.File, "library workout", f"`use {target}`", "10")
            for target in vocab.library_paths(base)
        ]
    if "score_value" in categories:
        return [_simple(value, lsp.CompletionItemKind.EnumMember, "score", "SPEC §12", "10") for value in vocab.SCORE_VALUES]
    if "units_value" in categories:
        return [_simple(value, lsp.CompletionItemKind.EnumMember, "default load unit", "SPEC §6", "10") for value in ("kg", "lb")]
    if "modifier" in categories:
        return [
            _simple(modifier, lsp.CompletionItemKind.Property, "modifier", "SPEC §7.5", "10")
            for modifier in vocab.MODIFIER_ITEMS
        ]

    if "format" in categories:
        items += [_simple(label, lsp.CompletionItemKind.Keyword, detail, doc, "00") for label, detail, doc in vocab.FORMATS]
    if "label" in categories:
        items += [_simple(label, lsp.CompletionItemKind.Keyword, detail, doc, "01") for label, detail, doc in vocab.LABEL_ITEMS]
    if "meta" in categories:
        items += [
            _simple(f"{key}: ", lsp.CompletionItemKind.Property, detail, doc, "02")
            for key, (detail, doc) in vocab.META_ITEMS.items()
        ]
    if "unit" in categories:
        items += [_simple(unit, lsp.CompletionItemKind.Unit, kind, "SPEC §2.2", "03") for unit, kind in vocab.UNITS]
    if "movement" in categories:
        items += _movement_items()
    return items


def completion(ls: WodcraftLanguageServer, params: lsp.CompletionParams) -> lsp.CompletionList:
    analysis = ls.analyse(params.text_document.uri)
    line = params.position.line + 1
    col = position_to_col(line_text(analysis.lines, line), params.position.character)
    return lsp.CompletionList(is_incomplete=False, items=completion_items(analysis.text, line, col, analysis.path))


# --------------------------------------------------------------------------- hover


def hover(ls: WodcraftLanguageServer, params: lsp.HoverParams) -> lsp.Hover | None:
    analysis = ls.analyse(params.text_document.uri)
    line = params.position.line + 1
    text = line_text(analysis.lines, line)
    col = position_to_col(text, params.position.character)
    found = movement_at(analysis, line, col)
    if found is None:
        return None
    movement, start_col, end_col = found
    from wodcraft.diagnostics import Span
    from wodcraft.lsp.positions import span_range as to_range

    (start_line, start_char), (end_line, end_char) = to_range(Span(line, start_col, end_col), analysis.lines)
    return lsp.Hover(
        contents=lsp.MarkupContent(lsp.MarkupKind.Markdown, vocab.movement_documentation(movement)),
        range=lsp.Range(lsp.Position(start_line, start_char), lsp.Position(end_line, end_char)),
    )


# --------------------------------------------------------------------------- formatting


def formatting(ls: WodcraftLanguageServer, params: lsp.DocumentFormattingParams) -> list[lsp.TextEdit] | None:
    analysis = ls.analyse(params.text_document.uri)
    formatted = format_document(analysis.text, analysis.path)
    if formatted is None:
        return None
    last = len(analysis.lines) - 1
    end = lsp.Position(max(0, last), len(analysis.lines[last]) if analysis.lines else 0)
    return [lsp.TextEdit(range=lsp.Range(lsp.Position(0, 0), end), new_text=formatted)]


# --------------------------------------------------------------------------- code actions


def _edit_to_lsp(edit: Edit, lines: list[str]) -> lsp.TextEdit:
    from wodcraft.diagnostics import Span

    (start_line, start_char), (end_line, end_char) = span_range(Span(edit.line, edit.col, edit.end_col), lines)
    return lsp.TextEdit(
        range=lsp.Range(lsp.Position(start_line, start_char), lsp.Position(end_line, end_char)),
        new_text=edit.new_text,
    )


def _fix_to_action(fix: Fix, uri: str, lines: list[str]) -> lsp.CodeAction:
    return lsp.CodeAction(
        title=fix.title,
        kind=lsp.CodeActionKind.QuickFix,
        diagnostics=[to_lsp_diagnostic(fix.diagnostic, lines)],
        is_preferred=fix.preferred or None,
        edit=lsp.WorkspaceEdit(changes={uri: [_edit_to_lsp(edit, lines) for edit in fix.edits]}),
    )


def code_action(ls: WodcraftLanguageServer, params: lsp.CodeActionParams) -> list[lsp.CodeAction]:
    analysis = ls.analyse(params.text_document.uri)
    fixes = code_actions(analysis, params.range.start.line + 1, params.range.end.line + 1)
    return [_fix_to_action(fix, params.text_document.uri, analysis.lines) for fix in fixes]


# --------------------------------------------------------------------------- document symbols


def _symbol_to_lsp(symbol, lines: list[str]) -> lsp.DocumentSymbol:
    from wodcraft.diagnostics import Span

    (start_line, start_char), _ = span_range(Span(symbol.line, symbol.col, symbol.end_col), lines)
    end_line = max(symbol.end_line, symbol.line)
    end_text = line_text(lines, end_line)
    full = lsp.Range(lsp.Position(start_line, 0), lsp.Position(max(0, end_line - 1), len(end_text)))
    selection_end = span_range(Span(symbol.line, symbol.col, symbol.end_col), lines)[1]
    selection = lsp.Range(
        lsp.Position(start_line, start_char),
        lsp.Position(selection_end[0], max(selection_end[1], start_char)),
    )
    return lsp.DocumentSymbol(
        name=symbol.name,
        detail=symbol.detail,
        kind=SYMBOL_KIND.get(symbol.kind, lsp.SymbolKind.Function),
        range=full,
        selection_range=selection,
        children=[_symbol_to_lsp(child, lines) for child in symbol.children] or None,
    )


def document_symbol(ls: WodcraftLanguageServer, params: lsp.DocumentSymbolParams) -> list[lsp.DocumentSymbol]:
    analysis = ls.analyse(params.text_document.uri)
    return [_symbol_to_lsp(symbol, analysis.lines) for symbol in document_symbols(analysis)]


# --------------------------------------------------------------------------- wiring


def create_server() -> WodcraftLanguageServer:
    """A fully wired server instance."""
    server = WodcraftLanguageServer(
        name=SERVER_NAME,
        version=__version__,
        text_document_sync_kind=lsp.TextDocumentSyncKind.Incremental,
    )
    server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)(did_open)
    server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)(did_change)
    server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)(did_save)
    server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)(did_close)
    server.feature(
        lsp.TEXT_DOCUMENT_COMPLETION,
        lsp.CompletionOptions(trigger_characters=COMPLETION_TRIGGERS, resolve_provider=False),
    )(completion)
    server.feature(lsp.TEXT_DOCUMENT_HOVER)(hover)
    server.feature(lsp.TEXT_DOCUMENT_FORMATTING)(formatting)
    server.feature(
        lsp.TEXT_DOCUMENT_CODE_ACTION,
        lsp.CodeActionOptions(code_action_kinds=[lsp.CodeActionKind.QuickFix], resolve_provider=False),
    )(code_action)
    server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)(document_symbol)
    return server


def main(argv: list[str] | None = None) -> int:
    """Start the server on stdio."""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m wodcraft.lsp", description="WODCraft language server (LSP).")
    parser.add_argument("--version", action="version", version=f"wodcraft-lsp {__version__}")
    parser.add_argument("--tcp", action="store_true", help="listen on TCP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2087)
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.WARNING))

    server = create_server()
    if args.tcp:
        server.start_tcp(args.host, args.port)
    else:
        server.start_io()
    return 0


__all__ = [
    "WodcraftLanguageServer",
    "analyse",
    "code_action",
    "completion",
    "completion_items",
    "create_server",
    "did_change",
    "did_close",
    "did_open",
    "did_save",
    "diagnostics_for",
    "document_symbol",
    "formatting",
    "hover",
    "main",
    "publish_diagnostics",
    "to_lsp_diagnostic",
]
