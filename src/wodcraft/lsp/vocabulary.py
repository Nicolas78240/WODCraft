"""The vocabulary the editor offers: formats, labels, meta keys, units, and the movement catalog.

Everything here is plain data (no LSP types), so it can be unit-tested on its own and rendered
either as completion items or as hover documentation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from wodcraft.api import LIBRARY_DIR
from wodcraft.catalog import Catalog, Movement, load_catalog, normalize
from wodcraft.syntax.lexer import Token, tokenize
from wodcraft.syntax.lines import LABELS, META_KEYS, MODIFIERS
from wodcraft.syntax.units import CALORIE_UNITS, DISTANCE_UNITS, HEIGHT_UNITS, LOAD_UNITS, TIME_UNITS

FAMILIES = {"M": "monostructural", "G": "gymnastics", "W": "weightlifting"}

#: ``(insert text, detail, documentation)`` — SPEC §5.
FORMATS: tuple[tuple[str, str, str], ...] = (
    ("For time", "format", "Complete the work as fast as possible."),
    ("AMRAP ", "format · duration", "As many rounds (and reps) as possible: `AMRAP 20:00`."),
    ("EMOM ", "format · duration", "Every minute on the minute: `EMOM 12`."),
    ("E2MOM ", "format · duration", "Every 2 minutes; the duration is the total: `E2MOM 20`."),
    ("E3MOM ", "format · duration", "Every 3 minutes; the duration is the total: `E3MOM 15`."),
    ("Every ", "format · duration x N", "N intervals of a duration: `Every 2:00 x 10`."),
    ("Tabata", "format", "8 rounds (unless a count follows) of 20 s work / 10 s rest."),
    ("Death by", "format", "Minute *k*: perform *k* reps of the single child movement, until failure."),
    ("Max load", "format", "Build to the heaviest load for the prescribed reps."),
    ("rounds", "format · N rounds", "Repeat the block N times: `3 rounds`, `5 rounds for time`."),
    ("rounds for time", "format · N rounds for time", "Repeat the block N times, on the clock."),
    ("21-15-9", "rep ladder", "One round per value; children without a quantity take it."),
    ("for time", "option", "Puts an `N rounds` or ladder block on the clock."),
    ("cap ", "option · duration", "Time cap: `For time, cap 10:00`."),
    ("teams of ", "option · N", "Team size; only on the outermost format line."),
    ("Rest ", "rest line", "A timed pause: `Rest 2:00`."),
    ("use ", "use line", "Insert a workout from the library: `use girls/fran`."),
)

#: ``(insert text, detail, documentation)`` — SPEC §6.
LABEL_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("Buy-in: ", "label", "Work before the main block, inside the clock."),
    ("Cash-out: ", "label", "Work after the main block, inside the clock."),
    ("Odd: ", "label · EMOM", "Minutes 1, 3, 5…"),
    ("Even: ", "label · EMOM", "Minutes 2, 4, 6…"),
    ("Min 1: ", "label · interval", "The N-th interval of each cycle (cycle length = highest N)."),
    ("Scaled:", "level", "Level adaptations; list only the differences with the Rx work."),
    ("Intermediate:", "level", "Level adaptations; list only the differences with the Rx work."),
    ("Foundations:", "level", "Level adaptations; list only the differences with the Rx work."),
)

#: ``key -> (detail, documentation)`` — SPEC §6.
META_ITEMS: dict[str, tuple[str, str]] = {
    "cap": ("duration", "Time cap of the workout: `cap: 10:00`."),
    "score": ("time | rounds+reps | reps | load | distance | calories | none", "How the workout is scored."),
    "tiebreak": ("free text", "Tie-break rule."),
    "units": ("kg | lb", "Default unit for loads written without one."),
    "vest": ("load", "Weight vest: `vest: 20/14 lb`."),
    "stimulus": ("free text", "What the workout should feel like (repeatable)."),
    "note": ("free text", "Any other note (repeatable)."),
    "tags": ("comma-separated words", "`tags: girls, benchmark`."),
    "date": ("YYYY-MM-DD", "Session date."),
    "time": ("HH:MM", "Session start time (local)."),
}

SCORE_VALUES = ("time", "rounds+reps", "reps", "load", "distance", "calories", "none")

#: ``(unit, kind)`` — SPEC §2.2. Only the canonical spellings are offered.
UNITS: tuple[tuple[str, str], ...] = (
    ("kg", "load"),
    ("lb", "load"),
    ("pood", "load · 1 pood = 16 kg"),
    ("in", "height"),
    ("cm", "height"),
    ("m", "distance · never minutes"),
    ("km", "distance"),
    ("mi", "distance"),
    ("ft", "distance"),
    ("cal", "energy"),
    ("s", "time"),
    ("min", "time"),
    ("%", "relative · of a one-rep max"),
    ("bw", "relative · bodyweight"),
    ("RPE ", "relative · rate of perceived exertion 1-10"),
)

ALL_UNIT_WORDS = frozenset({*LOAD_UNITS, *HEIGHT_UNITS, *DISTANCE_UNITS, *CALORIE_UNITS, *TIME_UNITS})

MODIFIER_ITEMS: tuple[str, ...] = (*sorted(MODIFIERS), "per side", "rest ")

LABEL_DISPLAY: dict[str, str] = {
    "buy_in": "Buy-in",
    "cash_out": "Cash-out",
    "odd": "Odd",
    "even": "Even",
    "scaled": "Scaled",
    "intermediate": "Intermediate",
    "foundations": "Foundations",
}


def catalog() -> Catalog:
    """The standard movement catalog (cached by :func:`wodcraft.catalog.load_catalog`)."""
    return load_catalog()


# --------------------------------------------------------------------------- movement rendering


def rx_text(movement: Movement) -> str | None:
    """``"43/30 kg"`` — the usual Rx reference of a movement, or None."""
    if not movement.rx:
        return None
    unit = movement.rx.get("unit", "kg")
    men, women = movement.rx.get("men"), movement.rx.get("women")
    if men is None and women is None:
        return None
    if women is None or men == women:
        return f"{_num(men)} {unit}"
    return f"{_num(men)}/{_num(women)} {unit}"


def _num(value) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def movement_detail(movement: Movement) -> str:
    """The one-line completion detail: family, Rx, first French alias."""
    parts = [FAMILIES.get(movement.family, movement.family)]
    rx = rx_text(movement)
    if rx:
        parts.append(f"Rx {rx}")
    if movement.fr:
        parts.append(f"fr: {movement.fr[0]}")
    return " · ".join(parts)


def movement_documentation(movement: Movement) -> str:
    """Markdown shown on hover and in the completion details pane."""
    lines = [
        f"**{movement.name}** · `{movement.id}`",
        "",
        f"- Family: {FAMILIES.get(movement.family, movement.family)} (`{movement.family}`)"
        f" · equipment: {movement.equipment.replace('_', ' ')}",
        f"- Quantities: {', '.join(movement.quantities) or 'none'}",
        f"- Parameters: {', '.join(movement.params) if movement.params else 'none'}",
    ]
    rx = rx_text(movement)
    if rx:
        kind = "height" if "height" in movement.params and "load" not in movement.params else "load"
        lines.append(f"- Rx {kind}: **{rx}**")
    if movement.aliases:
        lines.append(f"- EN: {', '.join(movement.aliases)}")
    if movement.fr:
        lines.append(f"- FR: {', '.join(movement.fr)}")
    return "\n".join(lines)


def movement_filter_text(movement: Movement) -> str:
    """Label plus every alias, so typing `arraché` or `t2b` still finds the movement."""
    return " ".join(dict.fromkeys([movement.name, *movement.aliases, *movement.fr]))


# --------------------------------------------------------------------------- library paths


def library_paths(extra: Path | None = None) -> list[str]:
    """Every `use` target, as written in a `use` line (``girls/fran``)."""
    roots = [p for p in (extra, LIBRARY_DIR) if p is not None and p.is_dir()]
    out: list[str] = []
    for root in roots:
        for path in sorted(root.rglob("*.wod")):
            name = path.relative_to(root).with_suffix("").as_posix()
            if name not in out:
                out.append(name)
    return out


# --------------------------------------------------------------------------- line classification

_UNIT_ALTERNATION = "|".join(sorted(ALL_UNIT_WORDS, key=len, reverse=True))
_QUANTITY_ONLY = re.compile(
    rf"^\s*(?:\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?(?:\s*(?:{_UNIT_ALTERNATION}))?|max(?:\s+\w+)?)\s+$"
)
_AFTER_NUMBER = re.compile(r"(?:^|[\s@(])\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?\s*$")
_META_START = re.compile(r"^\s*([A-Za-z][\w-]*)\s*:\s*(.*)$")
_USE_START = re.compile(r"^\s*use\s+(\S*)$", re.IGNORECASE)
_IN_MODIFIER = re.compile(r"\([^)]*$")
_AT_SIGN = re.compile(r"@\s*$")
_FORMAT_LINE = re.compile(
    r"^\s*(?:for\s+time|amrap|e\d+mom|emom|every|tabata|death\s+by|max\s+load|teams\s+of|\d+\s*(?:rounds?|rft)|\d+(?:-\d+)+)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LineContext:
    """What makes sense at the cursor, given the text of the line before it."""

    categories: frozenset[str]
    word: str = ""
    meta_key: str | None = None
    use_prefix: str | None = None


def line_context(prefix: str) -> LineContext:
    """Classify the text of the current line up to the cursor.

    Categories: ``format``, ``label``, ``meta``, ``movement``, ``unit``, ``modifier``,
    ``score_value``, ``units_value``, ``use_path``.
    """
    word = re.search(r"[\w'’+%-]*$", prefix)
    typed = word.group(0) if word else ""

    use = _USE_START.match(prefix)
    if use is not None:
        return LineContext(frozenset({"use_path"}), typed, use_prefix=use.group(1))

    if _IN_MODIFIER.search(prefix):
        return LineContext(frozenset({"modifier"}), typed)

    meta = _META_START.match(prefix)
    if meta is not None and meta.group(1).lower() in META_KEYS:
        key = meta.group(1).lower()
        if key == "score":
            return LineContext(frozenset({"score_value"}), typed, meta_key=key)
        if key == "units":
            return LineContext(frozenset({"units_value"}), typed, meta_key=key)
        if key in ("cap", "vest"):
            return LineContext(frozenset({"unit"}), typed, meta_key=key)
        return LineContext(frozenset(), typed, meta_key=key)

    if not prefix.strip():
        return LineContext(frozenset({"format", "label", "meta", "movement"}), typed)

    if _AT_SIGN.search(prefix):
        return LineContext(frozenset({"unit"}), typed)

    if _QUANTITY_ONLY.match(prefix):
        # "400 " may still grow a unit ("400 m Run"); "400 m " cannot
        has_unit = any(word.lower() in ALL_UNIT_WORDS for word in re.findall(r"[A-Za-z%]+", prefix))
        return LineContext(frozenset({"movement"} if has_unit else {"movement", "unit"}), typed)

    if _AFTER_NUMBER.search(prefix):
        return LineContext(frozenset({"unit"}), typed)

    if _FORMAT_LINE.match(prefix):
        return LineContext(frozenset({"format", "unit"}), typed)

    # a bare word being typed at the start of a line may still become a format, label or meta key
    if re.fullmatch(r"\s*[A-Za-z][\w-]*", prefix):
        return LineContext(frozenset({"format", "label", "meta", "movement"}), typed)

    return LineContext(frozenset({"movement", "unit"}), typed)


def words_at(line: str, col: int) -> list[Token]:
    """The WORD tokens of ``line``; used to find the movement name under the cursor."""
    from wodcraft.diagnostics import DiagnosticBag
    from wodcraft.syntax.lexer import Line

    stripped = line.lstrip(" \t")
    indent = len(line) - len(stripped)
    logical = Line(1, indent, stripped.rstrip(), line)
    return [t for t in tokenize(logical, DiagnosticBag(), None) if t.kind == "WORD"]


def movement_in_line(line: str, col: int) -> tuple[Movement, int, int] | None:
    """Longest catalog name covering the 1-based ``col`` of ``line`` -> (movement, col, end_col)."""
    tokens = words_at(line, col)
    known = catalog()
    best: tuple[Movement, int, int] | None = None
    for start in range(len(tokens)):
        for end in range(len(tokens), start, -1):
            run = tokens[start:end]
            if not (run[0].col <= col <= run[-1].end_col):
                continue
            entry = known.get(" ".join(t.text for t in run))
            if entry is not None and (best is None or (run[-1].end_col - run[0].col) > (best[2] - best[1])):
                best = (entry, run[0].col, run[-1].end_col)
    return best


def closest(word: str, options: list[str], n: int = 3) -> list[str]:
    """Close matches of ``word`` among ``options``, case-insensitive."""
    import difflib

    lowered = {option.lower(): option for option in options}
    matches = difflib.get_close_matches(word.lower(), list(lowered), n=n, cutoff=0.6)
    return [lowered[m] for m in matches]


def normalized_movement_names() -> dict[str, str]:
    """``normalized alias -> canonical name`` for every catalog entry."""
    known = catalog()
    return {alias: known.movements[mid].name for alias, mid in known.index.items()}


__all__ = [
    "ALL_UNIT_WORDS",
    "FAMILIES",
    "FORMATS",
    "LABELS",
    "LABEL_DISPLAY",
    "LABEL_ITEMS",
    "LineContext",
    "META_ITEMS",
    "META_KEYS",
    "MODIFIER_ITEMS",
    "SCORE_VALUES",
    "UNITS",
    "catalog",
    "closest",
    "library_paths",
    "line_context",
    "movement_detail",
    "movement_documentation",
    "movement_filter_text",
    "movement_in_line",
    "normalize",
    "normalized_movement_names",
    "rx_text",
]
