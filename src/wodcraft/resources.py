"""Access to the files that make up the standard: the specification and the JSON schema.

They live in ``spec/`` at the root of the repository and are shipped inside the package, so that
``pip install wodcraft`` carries the specification it implements.
"""

from __future__ import annotations

import json
from pathlib import Path

_PACKAGED = Path(__file__).parent / "spec"
_REPO = Path(__file__).resolve().parents[2] / "spec"
_ENV = "WODCRAFT_SPEC_DIR"


def spec_dir() -> Path:
    import os

    override = os.environ.get(_ENV)
    for candidate in (Path(override) if override else None, _PACKAGED, _REPO):
        if candidate and (candidate / "SPEC.md").is_file():
            return candidate
    raise FileNotFoundError(f"specification not found; set {_ENV} to the directory holding SPEC.md")


def spec_text() -> str:
    return (spec_dir() / "SPEC.md").read_text(encoding="utf-8")


def schema() -> dict:
    return json.loads((spec_dir() / "workout.schema.json").read_text(encoding="utf-8"))
