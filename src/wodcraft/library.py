"""The standard workout library shipped with the package (Girls, Heroes, Open)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

LIBRARY_DIR = Path(__file__).parent / "library"


@dataclass(frozen=True)
class Entry:
    path: str  # "girls/fran"
    title: str
    file: Path

    @property
    def source(self) -> str:
        return self.file.read_text(encoding="utf-8")


def _title(file: Path) -> str:
    for line in file.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return file.stem


def entries(query: str | None = None) -> list[Entry]:
    """Every workout of the standard library, optionally filtered by name or title."""
    needle = (query or "").lower()
    found = []
    for file in sorted(LIBRARY_DIR.rglob("*.wod")):
        path = file.relative_to(LIBRARY_DIR).with_suffix("").as_posix()
        title = _title(file)
        if not needle or needle in path.lower() or needle in title.lower():
            found.append(Entry(path, title, file))
    return found


def get(path: str) -> Entry | None:
    """One workout by library path, e.g. ``girls/fran``."""
    name = path if path.endswith(".wod") else path + ".wod"
    file = (LIBRARY_DIR / name).resolve()
    if not file.is_file() or LIBRARY_DIR.resolve() not in file.parents:
        return None
    return Entry(file.relative_to(LIBRARY_DIR.resolve()).with_suffix("").as_posix(), _title(file), file)
