"""Conversions between WODCraft spans (1-based, code points) and LSP positions (0-based, UTF-16).

The compiler reports ``Span(line, col, end_col)`` with 1-based line and column numbers counted in
Python characters; ``end_col`` is exclusive and ``0`` means "up to the end of the line".
LSP counts lines and characters from 0 and, unless the client negotiates otherwise, measures
characters in UTF-16 code units.
"""

from __future__ import annotations

from wodcraft.diagnostics import Span


def text_lines(text: str) -> list[str]:
    """Split a document the way the compiler does (CRLF and CR normalised to LF)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def line_text(lines: list[str], line: int) -> str:
    """The 1-based ``line`` of ``lines``, or "" when out of range."""
    return lines[line - 1] if 0 < line <= len(lines) else ""


def to_utf16(text: str, col: int) -> int:
    """1-based code-point column -> 0-based UTF-16 offset."""
    prefix = text[: max(0, col - 1)]
    return len(prefix.encode("utf-16-le")) // 2


def from_utf16(text: str, offset: int) -> int:
    """0-based UTF-16 offset -> 1-based code-point column."""
    if offset <= 0:
        return 1
    units = 0
    for index, char in enumerate(text):
        if units >= offset:
            return index + 1
        units += 2 if ord(char) > 0xFFFF else 1
    return len(text) + 1


def span_range(span: Span, lines: list[str]) -> tuple[tuple[int, int], tuple[int, int]]:
    """``Span`` -> ((start_line, start_char), (end_line, end_char)), 0-based and UTF-16."""
    text = line_text(lines, span.line)
    start_col = max(1, min(span.col, len(text) + 1))
    end_col = span.end_col if span.end_col else len(text) + 1
    end_col = max(start_col, min(end_col, len(text) + 1))
    row = max(0, span.line - 1)
    return (row, to_utf16(text, start_col)), (row, to_utf16(text, end_col))


def position_to_col(text: str, character: int) -> int:
    """An LSP character offset on ``text`` -> 1-based code-point column."""
    return from_utf16(text, character)


def span_contains(span: Span, line: int, col: int) -> bool:
    """True when the 1-based (line, col) cursor sits inside ``span`` (end inclusive)."""
    if span.line != line:
        return False
    end = span.end_col if span.end_col else col + 1
    return span.col <= col <= end
