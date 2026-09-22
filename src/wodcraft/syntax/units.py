"""Unit vocabulary shared by the parser and the semantic stages."""

from __future__ import annotations

LOAD_UNITS = {"kg": "kg", "kgs": "kg", "lb": "lb", "lbs": "lb", "pood": "pood", "poods": "pood"}
HEIGHT_UNITS = {"in": "in", "inch": "in", "inches": "in", "cm": "cm", '"': "in"}
DISTANCE_UNITS = {"m": "m", "km": "km", "mi": "mi", "mile": "mi", "miles": "mi", "ft": "ft", "foot": "ft", "feet": "ft"}
CALORIE_UNITS = {"cal": "cal", "cals": "cal", "calorie": "cal", "calories": "cal"}
TIME_UNITS = {
    "s": "s",
    "sec": "s",
    "secs": "s",
    "second": "s",
    "seconds": "s",
    "min": "min",
    "mins": "min",
    "minute": "min",
    "minutes": "min",
}

KG_PER_LB = 0.45359237
KG_PER_POOD = 16.0
CM_PER_IN = 2.54
M_PER = {"m": 1.0, "km": 1000.0, "mi": 1609.344, "ft": 0.3048}


def unit_kind(word: str) -> tuple[str, str] | None:
    """Return (kind, canonical unit) for a unit word, or None."""
    w = word.lower()
    for kind, table in (
        ("load", LOAD_UNITS),
        ("height", HEIGHT_UNITS),
        ("distance", DISTANCE_UNITS),
        ("calories", CALORIE_UNITS),
        ("time", TIME_UNITS),
    ):
        if w in table:
            return kind, table[w]
    return None


def seconds(value: float, unit: str) -> float:
    return value * 60 if unit == "min" else value


def parse_clock(text: str) -> float:
    parts = [int(p) for p in text.split(":")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return float(total)


def format_clock(total: float) -> str:
    total = int(round(total))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"
