"""Athlete profile: category, level, preferred units and one-rep maxes (SPEC §14)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

LEVEL_ORDER = ["rx", "intermediate", "scaled", "foundations"]
DEFAULT_FILES = ("athlete.toml", ".wodcraft/athlete.toml")


@dataclass
class Profile:
    category: str = "men"  # men | women
    level: str = "rx"
    units: str = "kg"
    bodyweight_kg: float | None = None
    one_rm: dict[str, float] = field(default_factory=dict)  # movement id -> kg
    name: str | None = None

    @classmethod
    def load(cls, path: str | Path) -> Profile:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            category=str(data.get("category", "men")).lower(),
            level=str(data.get("level", "rx")).lower(),
            units=str(data.get("units", "kg")).lower(),
            bodyweight_kg=data.get("bodyweight_kg"),
            one_rm={k.lower(): float(v) for k, v in (data.get("1rm") or data.get("one_rm") or {}).items()},
            name=data.get("name"),
        )

    @classmethod
    def discover(cls, start: Path | None = None) -> Profile | None:
        """Look for athlete.toml in the current directory, its parents, then the user's config."""
        here = (start or Path.cwd()).resolve()
        for directory in [here, *here.parents]:
            for name in DEFAULT_FILES:
                candidate = directory / name
                if candidate.is_file():
                    return cls.load(candidate)
        for candidate in (Path.home() / ".config" / "wodcraft" / "athlete.toml", Path.home() / ".wodcraft" / "athlete.toml"):
            if candidate.is_file():
                return cls.load(candidate)
        return None

    def levels_to_try(self) -> list[str]:
        """The asked level, then the closest ones, ending with Rx (SPEC §14)."""
        if self.level not in LEVEL_ORDER:
            return [self.level, "rx"]
        index = LEVEL_ORDER.index(self.level)
        ordered = LEVEL_ORDER[index:] + LEVEL_ORDER[:index][::-1]
        return ordered
