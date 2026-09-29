"""Line-level lexer: splits a source into logical lines and a line into tokens."""

from __future__ import annotations

import re
from dataclasses import dataclass

from wodcraft.diagnostics import DiagnosticBag, Span

_TOKEN_RE = re.compile(
    r"""
    (?P<STRING>"[^"]*")
  | (?P<CLOCK>\d+:\d{2}(?::\d{2})?)
  | (?P<SETS>\d+[xX×]\d+(?![\d.]))
  | (?P<DCOMMA>\d+,\d+)
  | (?P<NUM>\d+(?:\.\d+)?)
  | (?P<ELLIPSIS>\.\.\.|…)
  | (?P<ARROW>->|→)
  | (?P<WORD>[^\W\d_][\w'’+\-]*)
  | (?P<SYM>[/@(),:%\-#|])
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class Token:
    kind: str  # STRING CLOCK SETS NUM ELLIPSIS ARROW WORD SYM
    text: str
    col: int  # 1-based
    glued: bool  # True when not preceded by whitespace

    @property
    def end_col(self) -> int:
        return self.col + len(self.text)

    @property
    def lower(self) -> str:
        return self.text.lower()

    def is_word(self, *words: str) -> bool:
        return self.kind == "WORD" and self.lower in words

    def is_sym(self, sym: str) -> bool:
        return self.kind == "SYM" and self.text == sym


@dataclass
class Line:
    number: int  # 1-based
    indent: int
    text: str  # without indentation and comment, right-stripped
    raw: str
    comment: str | None = None  # "// …" text, without the slashes

    @property
    def col0(self) -> int:
        return self.indent + 1


def strip_comment(text: str) -> tuple[str, str | None]:
    """Split a line into code and its ``//`` comment. ``//`` only starts a comment at line start
    or after whitespace, and never inside a quoted string, so URLs such as ``https://…`` survive."""
    in_str = False
    for i, ch in enumerate(text):
        if ch == '"':
            in_str = not in_str
        elif ch == "/" and not in_str and text.startswith("//", i) and (i == 0 or text[i - 1].isspace()):
            return text[:i], text[i + 2 :].strip()
    return text, None


def split_lines(source: str, diags: DiagnosticBag, file: str | None = None) -> tuple[list[Line], list[str]]:
    raw_lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[Line] = []
    for n, raw in enumerate(raw_lines, start=1):
        body, comment = strip_comment(raw)
        body = body.rstrip()
        if not body.strip():
            if comment:
                out.append(Line(n, len(raw) - len(raw.lstrip()), "", raw, comment))
            continue
        stripped = body.lstrip(" \t")
        lead = body[: len(body) - len(stripped)]
        if "\t" in lead:
            diags.add("E002", "Tab in indentation; use spaces.", Span(n, lead.index("\t") + 1, file=file))
            lead = lead.replace("\t", "  ")
        out.append(Line(n, len(lead), stripped, raw, comment))
    return out, raw_lines


def tokenize(line: Line, diags: DiagnosticBag, file: str | None = None) -> list[Token]:
    tokens: list[Token] = []
    text = line.text
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(text, pos)
        col = line.indent + pos + 1
        glued = pos > 0 and not text[pos - 1].isspace()
        if not m:
            diags.add("E001", f"Unexpected character {text[pos]!r}.", Span(line.number, col, col + 1, file))
            pos += 1
            continue
        kind = m.lastgroup or "SYM"
        tok_text = m.group()
        if kind == "DCOMMA":
            fixed = tok_text.replace(",", ".")
            diags.add(
                "E003",
                f"Decimal comma in {tok_text!r}.",
                Span(line.number, col, col + len(tok_text), file),
                f"write {fixed!r}",
            )
            kind, tok_text_value = "NUM", fixed
            tokens.append(Token(kind, tok_text_value, col, glued))
            pos = m.end()
            continue
        if kind == "SETS":
            tok_text = tok_text.replace("X", "x").replace("×", "x")
        tokens.append(Token(kind, tok_text, col, glued))
        pos = m.end()
    return tokens
