"""Generate the Swift view fixtures from the Python reference implementation.

`swift/WODCraftKit` proves it renders exactly like this implementation by comparing against these
expectations. Run it (or `make swift-resources`) after changing a renderer, the catalog or the
library, then run `swift test`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wodcraft.emit import board  # noqa: E402  (the package lives in src/)
from wodcraft.emit.markdown import to_markdown  # noqa: E402
from wodcraft.emit.timeline import render_timer, timeline  # noqa: E402

KIT = REPO / "swift/WODCraftKit"
LIBRARY = KIT / "Sources/WODCraftKit/Resources/library.json"
CONFORMANCE = KIT / "Tests/WODCraftKitTests/Resources/conformance"
OUTPUT = KIT / "Tests/WODCraftKitTests/ViewsFixtures.swift"

HEADER = """// Generated from the Python reference implementation. Do not edit by hand.
//
// Every compiled document of `Resources/library.json` and of the conformance corpus, rendered by
// `wodcraft.emit.board`, `wodcraft.emit.markdown` and `wodcraft.emit.timeline`. Regenerate with
// `make swift-resources`.

enum ViewsFixtures {
"""


def rendered(path: str, document: dict) -> dict:
    segments = timeline(document)
    return {
        "path": path,
        "board": board.render(document),
        "boardFr": board.render(document, lang="fr"),
        "markdown": to_markdown(document),
        "timer": render_timer(document),
        "segments": [
            {
                "at": segment["at_s"],
                "duration": segment["duration_s"],
                "label": segment["label"],
                "kind": segment["kind"],
                "openEnded": bool(segment.get("open_ended")),
            }
            for segment in segments
        ],
    }


def library_rows() -> list[dict]:
    workouts = json.loads(LIBRARY.read_text(encoding="utf-8"))["workouts"]
    return [rendered(workout["path"], workout["compiled"]) for workout in workouts]


def conformance_rows() -> list[dict]:
    rows: list[dict] = []
    for file in sorted(CONFORMANCE.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        if isinstance(data, list):  # a case holding several documents
            rows += [rendered(f"{file.stem}[{index}]", document) for index, document in enumerate(data)]
        elif isinstance(data, dict) and data.get("kind") in ("workout", "session"):
            rows.append(rendered(file.stem, data))
    return rows


def constant(name: str, rows: list[dict]) -> str:
    text = json.dumps(rows, ensure_ascii=False, indent=1)
    if '"""#' in text:
        raise SystemExit("a rendering contains the raw string delimiter; change the delimiter")
    return f'    static let {name}: String = #"""\n{text}\n"""#\n\n'


def main() -> int:
    library = library_rows()
    conformance = conformance_rows()
    OUTPUT.write_text(HEADER + constant("libraryJSON", library) + constant("conformanceJSON", conformance) + "}\n", encoding="utf-8")
    print(f"{len(library)} library rows, {len(conformance)} conformance rows -> {OUTPUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
