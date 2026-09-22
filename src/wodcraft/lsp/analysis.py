"""Everything the server computes from a document, expressed without any LSP type.

The functions here take the text of a document (and, when it is saved, its filesystem path) and
return plain Python data. ``server.py`` turns that data into ``lsprotocol`` objects. Nothing runs
an external process and nothing is written to disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from wodcraft.api import compile_source
from wodcraft.diagnostics import Diagnostic, Span
from wodcraft.emit.source import format_source
from wodcraft.lsp import vocabulary as vocab
from wodcraft.lsp.positions import text_lines
from wodcraft.syntax.ast import Block, Document, MovementLine, Section, SourceFile, Statement, WorkoutBody
from wodcraft.syntax.parser import parse_source

MAX_CACHE = 32


# --------------------------------------------------------------------------- analysis cache


@dataclass
class Analysis:
    """A parsed and compiled document."""

    uri: str
    text: str
    version: int | None
    path: str | None
    source_file: SourceFile
    diagnostics: list[Diagnostic]
    lines: list[str] = field(default_factory=list)

    @property
    def own_diagnostics(self) -> list[Diagnostic]:
        """Diagnostics located in this document (a `use`d file reports its own)."""
        return [d for d in self.diagnostics if d.span.file in (None, self.path)]


def analyse(uri: str, text: str, version: int | None = None) -> Analysis:
    """Parse and compile ``text``; never raises, never touches the disk except to resolve `use`."""
    path = _fs_path(uri)
    source_file, _ = parse_source(text, path)
    try:
        result = compile_source(text, path)
        diagnostics = list(result.diagnostics)
    except Exception:  # pragma: no cover - a compiler crash must not kill the server
        diagnostics = []
    return Analysis(uri, text, version, path, source_file, diagnostics, text_lines(text))


def _fs_path(uri: str) -> str | None:
    if not uri.startswith("file://"):
        return None
    from urllib.parse import unquote, urlparse

    parsed = urlparse(uri)
    if parsed.netloc not in ("", "localhost"):
        return None
    return unquote(parsed.path)


class AnalysisCache:
    """Keeps the last analysis of each open document, keyed by URI and text."""

    def __init__(self, limit: int = MAX_CACHE) -> None:
        self._items: dict[str, Analysis] = {}
        self._limit = limit

    def get(self, uri: str, text: str, version: int | None = None) -> Analysis:
        cached = self._items.get(uri)
        if cached is not None and cached.text == text:
            return cached
        analysis = analyse(uri, text, version)
        if len(self._items) >= self._limit:
            self._items.pop(next(iter(self._items)), None)
        self._items[uri] = analysis
        return analysis

    def drop(self, uri: str) -> None:
        self._items.pop(uri, None)


# --------------------------------------------------------------------------- formatting


def format_document(text: str, path: str | None = None) -> str | None:
    """The canonical form of ``text``, or None when it cannot be parsed or is already canonical."""
    source_file, diags = parse_source(text, path)
    if diags.has_errors:
        return None
    formatted = format_source(source_file)
    return None if formatted == text else formatted


# --------------------------------------------------------------------------- document symbols


@dataclass
class Symbol:
    name: str
    detail: str
    kind: str  # "document" | "section" | "block"
    line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    col: int = 1
    end_col: int = 0
    children: list["Symbol"] = field(default_factory=list)


def document_symbols(analysis: Analysis) -> list[Symbol]:
    """The outline: `#` documents, `##` sections, then the block tree (SPEC §3-§4)."""
    documents = analysis.source_file.documents
    total = len(analysis.lines)
    symbols: list[Symbol] = []
    for index, doc in enumerate(documents):
        next_line = documents[index + 1].span.line - 1 if index + 1 < len(documents) else total
        symbols.extend(_document_symbol(doc, max(1, next_line)))
    return symbols


def _document_symbol(doc: Document, end_line: int) -> list[Symbol]:
    children: list[Symbol] = []
    if doc.is_session:
        for section in doc.sections or []:
            children.append(_section_symbol(section, end_line))
        for index in range(len(children) - 1):
            children[index].end_line = max(children[index].line, children[index + 1].line - 1)
    elif doc.body is not None:
        children = _body_symbols(doc.body)
    if doc.title is None:
        return children
    return [
        Symbol(
            doc.title,
            "session" if doc.is_session else "workout",
            "document",
            doc.span.line,
            max(end_line, doc.span.line),
            children=children,
        )
    ]


def _section_symbol(section: Section, end_line: int) -> Symbol:
    children = _body_symbols(section.body)
    last = max([child.end_line for child in children] or [section.span.line])
    return Symbol(section.title, "section", "section", section.span.line, max(last, section.span.line), children=children)


def _body_symbols(body: WorkoutBody) -> list[Symbol]:
    return [s for stmt in [*body.statements, *body.levels] for s in _statement_symbols(stmt)]


def _statement_symbols(stmt: Statement) -> list[Symbol]:
    if not isinstance(stmt, Block):
        return []
    children = [s for child in stmt.children for s in _statement_symbols(child)]
    last = max([child.end_line for child in children] or [stmt.span.line], default=stmt.span.line)
    return [
        Symbol(
            block_label(stmt),
            "level" if stmt.kind in ("scaled", "intermediate", "foundations") else ("label" if stmt.is_label else "format"),
            "block",
            stmt.span.line,
            max(last, _last_line(stmt)),
            stmt.span.col,
            stmt.span.end_col,
            children,
        )
    ]


def _last_line(stmt: Statement) -> int:
    span = getattr(stmt, "span", None)
    line = span.line if span is not None else 1
    if isinstance(stmt, Block):
        for child in stmt.children:
            line = max(line, _last_line(child))
    return line


def block_label(block: Block) -> str:
    """A short human label for a block, close to its canonical source form."""
    from wodcraft.syntax.units import format_clock

    kind = block.kind
    if kind == "slot":
        if block.slot == "odd":
            return "Odd:"
        if block.slot == "even":
            return "Even:"
        return f"Min {block.slot}:"
    if kind in vocab.LABEL_DISPLAY and block.is_label:
        return f"{vocab.LABEL_DISPLAY[kind]}:"
    head = {
        "for_time": "For time",
        "death_by": "Death by",
        "max_load": "Max load",
    }.get(kind)
    if head is None:
        if kind == "amrap":
            head = f"AMRAP {format_clock(block.duration_s or 0)}"
        elif kind == "emom":
            every = int((block.interval_s or 60) // 60)
            head = f"{'EMOM' if every <= 1 else f'E{every}MOM'} {format_clock(block.duration_s or 0)}"
        elif kind == "every":
            head = f"Every {format_clock(block.interval_s or 0)} x {block.rounds}"
        elif kind == "tabata":
            head = "Tabata" + ("" if (block.rounds or 8) == 8 else f" {block.rounds}")
        elif kind == "rounds":
            head = f"{block.rounds} rounds"
        elif kind == "ladder":
            head = "-".join(str(r) for r in (block.reps or [])) + (" ..." if block.reps_open else "")
        else:
            head = kind
    if block.for_time and kind in ("rounds", "ladder"):
        head += " for time"
    if block.teams:
        head += f", teams of {block.teams}"
    if block.cap_s:
        head += f", cap {format_clock(block.cap_s)}"
    return head


# --------------------------------------------------------------------------- hover


def movement_at(analysis: Analysis, line: int, col: int):
    """The catalog movement under the 1-based cursor -> ``(Movement, col, end_col)`` or None.

    Uses the parsed tree first — it knows exactly where each name starts and ends — and falls back
    to matching catalog names against the raw line when the line did not parse.
    """
    for mv in _movement_lines(analysis.source_file):
        for span, name in ((mv.name_span, mv.name), (mv.replace_span, mv.replace_with)):
            if span is None or name is None or span.line != line:
                continue
            end = span.end_col or col + 1
            if span.col <= col <= end:
                entry = vocab.catalog().get(name)
                if entry is not None:
                    return entry, span.col, end
    from wodcraft.lsp.positions import line_text

    return vocab.movement_in_line(line_text(analysis.lines, line), col)


def _movement_lines(source_file: SourceFile):
    for doc in source_file.documents:
        bodies = [section.body for section in (doc.sections or [])] if doc.is_session else ([doc.body] if doc.body else [])
        for body in bodies:
            if body is None:
                continue
            for stmt in [*body.statements, *body.levels]:
                yield from _walk_movements(stmt)


def _walk_movements(stmt: Statement):
    if isinstance(stmt, MovementLine):
        yield stmt
    elif isinstance(stmt, Block):
        for child in stmt.children:
            yield from _walk_movements(child)


# --------------------------------------------------------------------------- code actions


@dataclass(frozen=True)
class Edit:
    """A replacement in the document, with 1-based line and columns (``end_col`` exclusive)."""

    line: int
    col: int
    end_col: int
    new_text: str


@dataclass(frozen=True)
class Fix:
    title: str
    diagnostic: Diagnostic
    edits: tuple[Edit, ...]
    preferred: bool = False


_QUOTED = re.compile(r"'([^']+)'")
_TRAILING_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*$")


def code_actions(analysis: Analysis, start_line: int, end_line: int) -> list[Fix]:
    """Quick fixes for the diagnostics whose line falls in [start_line, end_line] (1-based)."""
    fixes: list[Fix] = []
    for diagnostic in analysis.own_diagnostics:
        if not start_line <= diagnostic.span.line <= end_line:
            continue
        fixes.extend(_fixes_for(analysis, diagnostic))
    return fixes


def _fixes_for(analysis: Analysis, diagnostic: Diagnostic) -> list[Fix]:
    from wodcraft.lsp.positions import line_text

    text = line_text(analysis.lines, diagnostic.span.line)
    code = diagnostic.code
    suggestion = diagnostic.suggestion or ""
    candidates = _QUOTED.findall(suggestion)

    if code == "E020":
        return [
            Fix(f"Replace with '{name}'", diagnostic, (_replace(text, diagnostic.span, name),), index == 0)
            for index, name in enumerate(candidates)
        ]
    if code == "E031":
        fixes = [
            Fix(f"Add the unit '{unit}'", diagnostic, (_append(text, diagnostic.span, f" {unit}"),), unit == "kg")
            for unit in ("kg", "lb")
        ]
        insert_line = _units_insert_line(analysis, diagnostic.span.line)
        fixes.append(Fix("Add 'units: kg' to the workout", diagnostic, (Edit(insert_line, 1, 1, "units: kg\n"),)))
        return fixes
    if code in ("E003", "E030"):
        return [Fix(f"Replace with '{c}'", diagnostic, (_replace(text, diagnostic.span, c),), True) for c in candidates[:1]]
    if code == "E012":
        return [
            Fix(f"Replace with '{key}:'", diagnostic, (_replace(text, diagnostic.span, f"{key}:"),), index == 0)
            for index, key in enumerate(vocab.closest(_word(text, diagnostic.span).rstrip(":"), sorted(vocab.META_KEYS)))
        ]
    if code == "E011":
        names = sorted(set(vocab.LABEL_DISPLAY.values()))
        return [
            Fix(f"Replace with '{name}:'", diagnostic, (_replace(text, diagnostic.span, f"{name}:"),), index == 0)
            for index, name in enumerate(vocab.closest(_word(text, diagnostic.span).rstrip(":"), names))
        ]
    if code == "E050":
        wanted = _QUOTED.findall(diagnostic.message)
        base = Path(analysis.path).parent if analysis.path else None
        options = vocab.library_paths(base)
        return [
            Fix(f"Replace with 'use {path}'", diagnostic, (_replace(text, diagnostic.span, f"use {path}"),), index == 0)
            for index, path in enumerate(vocab.closest(wanted[0] if wanted else "", options))
        ]
    if code == "E002":
        fixed = _detab(text)
        return [Fix("Replace the tabs with spaces", diagnostic, (Edit(diagnostic.span.line, 1, len(text) + 1, fixed),), True)]
    if code == "E001" and candidates:
        return [Fix(f"Replace with '{c}'", diagnostic, (_replace(text, diagnostic.span, c),), index == 0) for index, c in enumerate(candidates)]
    return []


def _word(text: str, span: Span) -> str:
    end = span.end_col if span.end_col else len(text) + 1
    return text[span.col - 1 : end - 1]


def _replace(text: str, span: Span, new_text: str) -> Edit:
    """Replace the span. When the replacement restates a number that already precedes the span
    (``'m' means metres`` -> ``write '12 min'``), the edit is widened to cover that number."""
    end = span.end_col if span.end_col else len(text) + 1
    current = text[span.col - 1 : end - 1]
    if new_text and new_text[0].isdigit() and not new_text.lower().startswith(current.lower()):
        before = _TRAILING_NUMBER.search(text[: span.col - 1])
        if before is not None and new_text.startswith(before.group(1)):
            return Edit(span.line, before.start(1) + 1, end, new_text)
    return Edit(span.line, span.col, end, new_text)


def _append(text: str, span: Span, suffix: str) -> Edit:
    end = span.end_col if span.end_col else len(text) + 1
    return Edit(span.line, end, end, suffix)


def _detab(text: str) -> str:
    stripped = text.lstrip(" \t")
    indent = text[: len(text) - len(stripped)]
    return indent.replace("\t", "  ") + stripped


def _units_insert_line(analysis: Analysis, line: int) -> int:
    """The line at which a `units:` meta line should be inserted for the document owning ``line``."""
    start = 1
    for doc in analysis.source_file.documents:
        if doc.title is not None and doc.span.line <= line:
            start = doc.span.line + 1
    return start
