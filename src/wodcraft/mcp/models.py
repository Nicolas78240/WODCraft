"""Typed payloads returned by the WODCraft MCP tools (structured tool output)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DiagnosticOut(BaseModel):
    """One coded, located compiler message (SPEC §15)."""

    code: str = Field(description="Diagnostic code, e.g. E020 or W103")
    severity: Literal["error", "warning", "info"] = Field(description="error stops compilation")
    line: int = Field(description="1-based source line")
    col: int = Field(description="1-based source column")
    end_col: int | None = Field(default=None, description="exclusive end column, when known")
    message: str = Field(description="What is wrong")
    suggestion: str | None = Field(default=None, description="How to fix it, when the compiler knows")


class _WithDiagnostics(BaseModel):
    ok: bool = Field(description="True when no diagnostic has severity 'error'")
    diagnostics: list[DiagnosticOut] = Field(default_factory=list)
    errors: int = 0
    warnings: int = 0


class CheckResult(_WithDiagnostics):
    """Result of `check_wod`."""

    summary: str = Field(description="One line, human readable")


class CompileResult(_WithDiagnostics):
    """Result of `compile_wod`."""

    document: dict[str, Any] | None = Field(default=None, description="The first compiled document")
    documents: list[dict[str, Any]] = Field(default_factory=list, description="Every document of the source")


class ShowResult(_WithDiagnostics):
    """Result of `show_wod`."""

    board: str = Field(default="", description="The whiteboard view, ready to display")
    resolved_for: dict[str, str] | None = Field(
        default=None, description="Athlete profile applied: category, level, units (null = raw Rx view)"
    )


class FormatResult(_WithDiagnostics):
    """Result of `format_wod`."""

    formatted: str = Field(default="", description="The canonical source")
    changed: bool = Field(default=False, description="True when the input was not already canonical")


class TimelineSegment(BaseModel):
    at_s: float = Field(description="Start of the segment, in seconds from the start")
    duration_s: float = Field(description="Length in seconds (0 = untimed item)")
    label: str
    kind: str = Field(description="work, rest or interval")
    open_ended: bool = Field(default=False, description="True when the length is an estimate, not a cap")
    section: str | None = Field(default=None, description="Session section the segment belongs to")


class TimelineResult(_WithDiagnostics):
    """Result of `timeline_wod`."""

    total_s: float = 0.0
    segments: list[TimelineSegment] = Field(default_factory=list)
    rendered: str = Field(default="", description="The timeline as printed by `wodc timer`")


class MovementOut(BaseModel):
    """One entry of the movement catalog (SPEC §11)."""

    id: str = Field(description="Catalog identifier, as it appears in the compiled JSON")
    name: str = Field(description="Canonical English name, as written in a .wod file")
    family: Literal["M", "G", "W"] = Field(description="M monostructural, G gymnastics, W weightlifting")
    family_name: str
    quantities: list[str] = Field(description="Quantity kinds accepted: reps, distance, calories, time")
    param: list[str] = Field(description="Parameter kinds accepted: load, height (empty = none)")
    equipment: str
    aliases: list[str] = Field(description="English aliases accepted on a movement line")
    fr: list[str] = Field(description="French aliases accepted on a movement line")
    rx: dict[str, float | str] | None = Field(default=None, description="Reference Rx load, e.g. {men, women, unit}")


class MovementSearchResult(BaseModel):
    """Result of `search_movements`."""

    count: int = Field(description="Movements returned")
    total: int = Field(description="Movements matching the query, before the limit")
    catalog_size: int
    truncated: bool
    movements: list[MovementOut]


class LibraryEntry(BaseModel):
    path: str = Field(description="Library path, as used by `use`, e.g. girls/fran")
    title: str
    tags: list[str] = Field(default_factory=list)


class LibraryList(BaseModel):
    """Result of `library_list`."""

    count: int
    total: int
    workouts: list[LibraryEntry]


class LibraryWorkout(LibraryEntry):
    """Result of `library_get`."""

    source: str = Field(description="The .wod source")
    use_line: str = Field(description="The line to paste in a session to pull this workout in")
    ok: bool = True
    diagnostics: list[DiagnosticOut] = Field(default_factory=list)
