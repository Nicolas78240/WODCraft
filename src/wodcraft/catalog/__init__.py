"""Movement catalog and unit equivalences (part of the standard, see SPEC §11)."""

from __future__ import annotations

import difflib
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@dataclass(frozen=True)
class Movement:
    id: str
    name: str
    family: str  # M | G | W
    quantities: tuple[str, ...]  # reps | distance | calories | time
    params: tuple[str, ...]  # accepted parameter kinds: load, height (empty = none)
    equipment: str
    aliases: tuple[str, ...] = ()
    fr: tuple[str, ...] = ()
    rx: dict[str, float] | None = None  # {"men": 43, "women": 30, "unit": "kg"}
    pace: dict[str, float] = field(default_factory=dict)  # seconds per rep / m / cal

    def pace_for(self, kind: str) -> float | None:
        return self.pace.get({"reps": "rep", "distance": "m", "calories": "cal"}.get(kind, kind))


def normalize(name: str) -> str:
    """Lower-case, collapse spaces/hyphens and drop a trailing plural 's'."""
    text = " ".join(name.lower().replace("-", " ").replace("’", "'").split())
    words = text.split(" ")
    if words and len(words[-1]) > 2 and words[-1].endswith("s") and not words[-1].endswith("ss"):
        words[-1] = words[-1][:-1]
    return " ".join(words)


@dataclass
class Catalog:
    movements: dict[str, Movement]
    index: dict[str, str]  # normalized alias -> movement id

    def get(self, name: str) -> Movement | None:
        key = normalize(name)
        mid = self.index.get(key)
        return self.movements.get(mid) if mid else None

    def suggest(self, name: str, n: int = 3) -> list[str]:
        matches = difflib.get_close_matches(normalize(name), list(self.index), n=n, cutoff=0.7)
        seen: list[str] = []
        for m in matches:
            display = self.movements[self.index[m]].name
            if display not in seen:
                seen.append(display)
        return seen

    def __len__(self) -> int:
        return len(self.movements)


def _params(raw: str | list[str]) -> tuple[str, ...]:
    values = [raw] if isinstance(raw, str) else list(raw)
    return tuple(v for v in values if v != "none")


def _load_catalog(path: Path) -> Catalog:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    movements: dict[str, Movement] = {}
    index: dict[str, str] = {}
    for mid, entry in data.get("movements", {}).items():
        mv = Movement(
            id=mid,
            name=entry["name"],
            family=entry.get("family", "G"),
            quantities=tuple(entry.get("quantities", ["reps"])),
            params=_params(entry.get("param", "none")),
            equipment=entry.get("equipment", "other"),
            aliases=tuple(entry.get("aliases", ())),
            fr=tuple(entry.get("fr", ())),
            rx=entry.get("rx"),
            pace=dict(entry.get("pace", {})),
        )
        movements[mid] = mv
        for alias in (mv.name, mid.replace("_", " "), *mv.aliases, *mv.fr):
            index.setdefault(normalize(alias), mid)
    return Catalog(movements, index)


@lru_cache(maxsize=4)
def load_catalog(path: str | None = None) -> Catalog:
    return _load_catalog(Path(path) if path else _DIR / "movements.toml")


@dataclass(frozen=True)
class Equivalences:
    load: tuple[tuple[float, float], ...]  # (kg, lb)
    height: tuple[tuple[float, float], ...]  # (cm, in)

    def kg_to_lb(self, kg: float) -> float | None:
        return next((pounds for kilos, pounds in self.load if abs(kilos - kg) < 1e-9), None)

    def lb_to_kg(self, lb: float) -> float | None:
        return next((k for k, pounds in self.load if abs(pounds - lb) < 1e-9), None)

    def cm_to_in(self, cm: float) -> float | None:
        return next((inches for centimetres, inches in self.height if abs(centimetres - cm) < 1e-9), None)

    def in_to_cm(self, inch: float) -> float | None:
        return next((centimetres for centimetres, inches in self.height if abs(inches - inch) < 1e-9), None)


@lru_cache(maxsize=4)
def load_equivalences(path: str | None = None) -> Equivalences:
    file = Path(path) if path else _DIR / "equivalences.toml"
    if not file.exists():
        return Equivalences((), ())
    data = tomllib.loads(file.read_text(encoding="utf-8"))
    return Equivalences(
        tuple((float(row["kg"]), float(row["lb"])) for row in data.get("load", [])),
        tuple((float(row["cm"]), float(row["in"])) for row in data.get("height", [])),
    )
