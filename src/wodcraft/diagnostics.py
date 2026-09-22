"""Diagnostics: coded, located messages produced by every compiler stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Span:
    """A 1-based source location. ``end_col`` is exclusive; 0 means "end of line"."""

    line: int
    col: int = 1
    end_col: int = 0
    file: str | None = None

    def to_dict(self) -> dict[str, int]:
        return {"line": self.line, "col": self.col}


@dataclass
class Diagnostic:
    code: str
    message: str
    span: Span
    suggestion: str | None = None

    @property
    def severity(self) -> Severity:
        return {"E": Severity.ERROR, "W": Severity.WARNING}.get(self.code[0], Severity.INFO)

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "line": self.span.line,
            "col": self.span.col,
        }
        if self.span.end_col:
            out["end_col"] = self.span.end_col
        if self.span.file:
            out["file"] = self.span.file
        if self.suggestion:
            out["suggestion"] = self.suggestion
        return out

    def format(self, source_lines: list[str] | None = None) -> str:
        where = f"{self.span.file}:" if self.span.file else ""
        head = f"{where}{self.span.line}:{self.span.col}: {self.severity.value} {self.code}: {self.message}"
        parts = [head]
        if source_lines and 0 < self.span.line <= len(source_lines):
            text = source_lines[self.span.line - 1].rstrip("\n")
            width = (self.span.end_col - self.span.col) if self.span.end_col > self.span.col else 1
            parts.append(f"    {text}")
            parts.append("    " + " " * (self.span.col - 1) + "^" * max(1, width))
        if self.suggestion:
            parts.append(f"    help: {self.suggestion}")
        return "\n".join(parts)


@dataclass
class DiagnosticBag:
    items: list[Diagnostic] = field(default_factory=list)

    def add(self, code: str, message: str, span: Span, suggestion: str | None = None) -> None:
        self.items.append(Diagnostic(code, message, span, suggestion))

    def extend(self, other: "DiagnosticBag | list[Diagnostic]") -> None:
        self.items.extend(other.items if isinstance(other, DiagnosticBag) else other)

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.items)

    def sorted(self) -> list[Diagnostic]:
        return sorted(self.items, key=lambda d: (d.span.file or "", d.span.line, d.span.col, d.code))
