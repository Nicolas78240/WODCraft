"""Where the MCP server finds the spec and the standard workout library."""

from __future__ import annotations

from pathlib import Path

from wodcraft.api import LIBRARY_DIR
from wodcraft.resources import spec_dir

__all__ = ["LIBRARY_DIR", "library_file", "library_paths", "spec_file"]


def spec_file() -> Path | None:
    """``SPEC.md``, shipped inside the package (see :mod:`wodcraft.resources`)."""
    try:
        return spec_dir() / "SPEC.md"
    except FileNotFoundError:
        return None


def library_paths() -> list[str]:
    """Every workout of the standard library, as ``use`` paths, sorted."""
    return sorted(p.relative_to(LIBRARY_DIR).with_suffix("").as_posix() for p in LIBRARY_DIR.rglob("*.wod"))


def library_file(path: str) -> Path | None:
    """The file behind a ``use`` path, or None when it is unknown or escapes the library."""
    cleaned = (path or "").strip().strip("/")
    if not cleaned:
        return None
    if cleaned.endswith(".wod"):
        cleaned = cleaned[: -len(".wod")]
    candidate = (LIBRARY_DIR / (cleaned + ".wod")).resolve()
    root = LIBRARY_DIR.resolve()
    if not candidate.is_file() or not candidate.is_relative_to(root):
        return None
    return candidate
