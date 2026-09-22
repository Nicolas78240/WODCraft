"""Syntax tree produced by the parser. Values are still in source units; nothing is resolved."""

from __future__ import annotations

from dataclasses import dataclass, field

from wodcraft.diagnostics import Span


@dataclass(frozen=True)
class Dual:
    """A value for the men and women categories. ``is_dual`` is False for a single written value."""

    men: float
    women: float
    is_dual: bool = False

    @classmethod
    def single(cls, value: float) -> Dual:
        return cls(value, value, False)


@dataclass
class Quantity:
    kind: str  # reps | distance | calories | time | max
    value: Dual | None  # None for "max"
    unit: str | None  # m, km, mi, cal, s — or, for max: None/cal/m
    span: Span


@dataclass
class Param:
    kind: str  # load | height | percent | rpe | bw | distance | calories
    value: Dual
    unit: str | None  # kg, lb, pood, in, cm, m, km, mi, cal — None when omitted
    span: Span
    of: str | None = None  # percent: name of the reference lift
    of_span: Span | None = None


@dataclass
class Sets:
    reps: list[int]  # one entry per set: 5x5 -> [5, 5, 5, 5, 5]
    span: Span
    notation: str  # "nxm" | "ladder"


@dataclass
class MovementLine:
    name: str
    name_span: Span
    span: Span
    quantity: Quantity | None = None
    sets: Sets | None = None
    params: list[Param] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)
    replace_with: str | None = None  # level blocks: "A -> B"
    replace_span: Span | None = None
    selector_params: list[Param] = field(default_factory=list)  # level blocks: params written before "->"


@dataclass
class RestLine:
    seconds: float
    span: Span


@dataclass
class UseLine:
    path: str
    span: Span


@dataclass
class CommentLine:
    text: str
    span: Span


@dataclass
class MetaLine:
    key: str
    value: str
    span: Span
    value_span: Span


@dataclass
class Block:
    """A format block (for_time, amrap…) or a label block (buy_in, odd, scaled…)."""

    kind: str
    span: Span
    children: list[Statement] = field(default_factory=list)
    duration_s: float | None = None
    interval_s: float | None = None
    rounds: int | None = None
    reps: list[int] | None = None
    reps_open: bool = False  # ladder written "3-6-9 ..." — continues until the cap
    cap_s: float | None = None
    teams: int | None = None
    for_time: bool = False
    slot: str | int | None = None  # odd | even | N for "Min N:"
    is_label: bool = False


Statement = Block | MovementLine | RestLine | UseLine | MetaLine | CommentLine

LEVEL_LABELS = ("scaled", "intermediate", "foundations")


@dataclass
class WorkoutBody:
    statements: list[Statement] = field(default_factory=list)
    levels: list[Block] = field(default_factory=list)  # kind in LEVEL_LABELS


@dataclass
class Section:
    title: str
    span: Span
    body: WorkoutBody


@dataclass
class Document:
    title: str | None
    span: Span
    meta: list[MetaLine] = field(default_factory=list)  # session preamble only
    body: WorkoutBody | None = None  # workout
    sections: list[Section] | None = None  # session

    @property
    def is_session(self) -> bool:
        return self.sections is not None


@dataclass
class SourceFile:
    documents: list[Document]
    lines: list[str]
    path: str | None = None
