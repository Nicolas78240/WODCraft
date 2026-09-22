"""The JSON bundle an application embeds: the catalog, the library and the schema.

TOML is the authoring format of the catalog; JSON is what a mobile or web application wants, because
every platform parses it natively. ``wodc bundle`` writes that view out.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from wodcraft import SPEC_VERSION, __version__, library
from wodcraft.api import compile_file
from wodcraft.catalog import load_catalog, load_equivalences
from wodcraft.resources import schema


@dataclass
class BundleReport:
    files: dict[str, int]  # path -> bytes written
    workouts: int
    movements: int
    failures: list[str]


def catalog_json() -> dict:
    catalog = load_catalog()
    equivalences = load_equivalences()
    return {
        "wodcraft": SPEC_VERSION,
        "movements": [
            {
                "id": movement.id,
                "name": movement.name,
                "family": movement.family,
                "quantities": list(movement.quantities),
                "params": list(movement.params),
                "equipment": movement.equipment,
                "aliases": list(movement.aliases),
                "fr": list(movement.fr),
                "fr_name": movement.display_name("fr"),
                "rx": movement.rx,
                "pace": movement.pace,
            }
            for movement in sorted(catalog.movements.values(), key=lambda m: m.id)
        ],
        "equivalences": {
            "load": [{"kg": kg, "lb": lb} for kg, lb in equivalences.load],
            "height": [{"cm": cm, "in": inches} for cm, inches in equivalences.height],
        },
    }


def library_json() -> tuple[dict, list[str]]:
    """The standard library: source and compiled document for every workout."""
    workouts = []
    failures = []
    for entry in library.entries():
        result = compile_file(entry.file)
        if not result.ok:
            failures.append(entry.path)
            continue
        workouts.append({"path": entry.path, "title": entry.title, "source": entry.source, "compiled": result.document})
    return {"wodcraft": SPEC_VERSION, "workouts": workouts}, failures


def write_bundle(directory: str | Path, compact: bool = True) -> BundleReport:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    workouts, failures = library_json()
    documents = {
        "catalog.json": catalog_json(),
        "library.json": workouts,
        "workout.schema.json": schema(),
        "bundle.json": {"wodcraft": SPEC_VERSION, "wodcraft_version": __version__, "files": ["catalog.json", "library.json", "workout.schema.json"]},
    }
    written: dict[str, int] = {}
    for name, payload in documents.items():
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":") if compact else None, indent=None if compact else 2)
        path = target / name
        path.write_text(text + "\n", encoding="utf-8")
        written[str(path)] = len(text.encode("utf-8")) + 1
    return BundleReport(written, len(workouts["workouts"]), len(documents["catalog.json"]["movements"]), failures)


def report_to_dict(report: BundleReport) -> dict:
    return asdict(report)
