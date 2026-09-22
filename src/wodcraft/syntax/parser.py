"""Builds documents from source text: indentation tree, then block ownership (SPEC §3–§4)."""

from __future__ import annotations

from dataclasses import dataclass, field

from wodcraft.diagnostics import DiagnosticBag, Span
from wodcraft.syntax.ast import (
    LEVEL_LABELS,
    Block,
    Document,
    MetaLine,
    Section,
    SourceFile,
    Statement,
    WorkoutBody,
)
from wodcraft.syntax.lexer import Line, split_lines, tokenize
from wodcraft.syntax.lines import _meta_or_label, format_is_timed, is_format_start, parse_line


@dataclass
class _Node:
    line: Line
    children: list[_Node] = field(default_factory=list)
    previous: _Node | None = None  # the sibling before it, so a meta line can hand its body over


def _build_tree(lines: list[Line], diags: DiagnosticBag, file: str | None) -> list[_Node]:
    root: list[_Node] = []
    stack: list[tuple[int, list[_Node]]] = [(lines[0].indent if lines else 0, root)]
    last: list[_Node | None] = [None]
    for line in lines:
        while len(stack) > 1 and line.indent < stack[-1][0]:
            stack.pop()
            last.pop()
        if line.indent > stack[-1][0]:
            parent = last[-1]
            while parent is not None and _classify(parent.line) == "meta" and parent.previous is not None:
                parent = parent.previous  # a meta line is transparent: its body belongs to the block above
            if parent is None:
                diags.add("E004", "Unexpected indentation.", Span(line.number, 1, line.col0, file))
                line = Line(line.number, stack[-1][0], line.text, line.raw)
            else:
                stack.append((line.indent, parent.children))
                last.append(None)
        elif line.indent != stack[-1][0]:
            diags.add("E004", "Inconsistent indentation.", Span(line.number, 1, line.col0, file))
            line = Line(line.number, stack[-1][0], line.text, line.raw)
        node = _Node(line, previous=last[-1])
        stack[-1][1].append(node)
        last[-1] = node
    return root


def _classify(line: Line) -> str:
    """'format' | 'label' | 'level' | 'meta' | 'other' — cheap look-ahead, diagnostics discarded."""
    tokens = tokenize(line, DiagnosticBag(), None)
    if not tokens:
        return "other"
    found = _meta_or_label(line, tokens, None)
    if found is not None:
        kind, name, _ = found
        if kind == "meta":
            return "meta"
        if name in LEVEL_LABELS:
            return "level"
        return "label" if kind == "label" else "other"
    if is_format_start(tokens):
        return "format_timed" if format_is_timed(tokens) else "format"
    return "other"


def _group(
    nodes: list[_Node], diags: DiagnosticBag, file: str | None, top: bool, in_level: bool = False
) -> tuple[list[Statement], list[Block]]:
    statements: list[Statement] = []
    levels: list[Block] = []
    kinds = [_classify(n.line) for n in nodes]
    first_format_used = False
    i = 0
    while i < len(nodes):
        node, kind = nodes[i], kinds[i]
        stmt = parse_line(node.line, diags, file, allow_replace=in_level)
        i += 1
        if stmt is None:
            continue
        if not isinstance(stmt, Block):
            if node.children:
                first = node.children[0].line
                diags.add(
                    "E004",
                    "Only a format or label line can have indented children.",
                    Span(first.number, first.col0, file=file),
                )
                child_stmts, child_levels = _group(node.children, diags, file, top=False, in_level=in_level)
                statements.extend(child_stmts)
                levels.extend(child_levels)
            statements.append(stmt)
            continue

        is_level = kind == "level"
        owned: list[_Node] = []
        if node.children:
            owned = node.children
        elif stmt.children:
            pass  # inline content, e.g. "Odd: 10 Burpee"
        elif is_level:
            while i < len(nodes) and kinds[i] != "level":
                owned.append(nodes[i])
                i += 1
        elif top and not first_format_used and not stmt.is_label:
            # rule 2: the main format owns the rest of the body, up to the next timed format
            while i < len(nodes) and kinds[i] not in ("level", "format_timed"):
                owned.append(nodes[i])
                i += 1
            first_format_used = True
        else:
            while i < len(nodes) and kinds[i] not in ("format", "format_timed", "label", "level"):
                owned.append(nodes[i])
                i += 1
            if i < len(nodes) and kinds[i] == "format" and not stmt.is_label and not owned:
                owned.append(nodes[i])  # "For time" directly followed by "21-15-9"
                i += 1
        if owned:
            child_stmts, child_levels = _group(owned, diags, file, top=False, in_level=in_level or is_level)
            stmt.children.extend(child_stmts)
            levels.extend(child_levels)
        if is_level:
            levels.append(stmt)
        else:
            statements.append(stmt)
    return statements, levels


def _body(nodes: list[_Node], diags: DiagnosticBag, file: str | None) -> WorkoutBody:
    statements, levels = _group(nodes, diags, file, top=True)
    return WorkoutBody(statements, levels)


def _heading_level(line: Line) -> int:
    text = line.text
    if not text.startswith("#"):
        return 0
    return len(text) - len(text.lstrip("#"))


def parse_source(source: str, file: str | None = None) -> tuple[SourceFile, DiagnosticBag]:
    diags = DiagnosticBag()
    lines, raw_lines = split_lines(source, diags, file)
    documents: list[Document] = []
    current: list[Line] = []
    title: str | None = None
    title_span = Span(1, 1, file=file)

    def flush() -> None:
        if not current and title is None:
            return
        documents.append(_document(title, title_span, current, diags, file))

    for line in lines:
        level = _heading_level(line)
        if level == 1:
            flush()
            current = []
            title = line.text.lstrip("#").strip()
            title_span = Span(line.number, line.col0, file=file)
            if line.indent:
                diags.add("E004", "A heading must start at the beginning of the line.", title_span)
        else:
            current.append(line)
    flush()
    return SourceFile(documents, raw_lines, file), diags


def _document(title: str | None, span: Span, lines: list[Line], diags: DiagnosticBag, file: str | None) -> Document:
    section_starts = [i for i, line in enumerate(lines) if _heading_level(line) == 2]
    if not section_starts:
        return Document(title, span, body=_body(_build_tree(lines, diags, file), diags, file))

    preamble = lines[: section_starts[0]]
    meta: list[MetaLine] = []
    for line in preamble:
        stmt = parse_line(line, diags, file)
        if isinstance(stmt, MetaLine):
            meta.append(stmt)
        elif stmt is not None:
            diags.add(
                "E014",
                "Only meta lines are allowed between a session title and its first section.",
                Span(line.number, line.col0, file=file),
                "move this line under a '## Section' heading",
            )
    sections: list[Section] = []
    for k, start in enumerate(section_starts):
        end = section_starts[k + 1] if k + 1 < len(section_starts) else len(lines)
        head = lines[start]
        body_lines = lines[start + 1 : end]
        sections.append(
            Section(
                head.text.lstrip("#").strip(),
                Span(head.number, head.col0, file=file),
                _body(_build_tree(body_lines, diags, file), diags, file),
            )
        )
    return Document(title, span, meta=meta, sections=sections)
