"""Check that a second implementation agrees with this one, source by source.

Conformance fixtures pin the cases someone thought of. This goes further: it feeds both
implementations the same sources — the library, the conformance corpus, the examples, and thousands
of mutations of them — and compares the diagnostics and the compiled documents.

    python scripts/differential_check.py path/to/wodcraftc [--cases 400] [--seed 0]

The other implementation must accept `compile FILE` and print
`{"ok": bool, "diagnostics": [{"code", "line", …}], "documents": [...]}` on standard output.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wodcraft.api import compile_source  # noqa: E402  (the package lives in src/)

MUTATION_CHARACTERS = '0123456789:/@()-,%"# \nkglbmi.'
# `estimate` is excluded from conformance, `source` spans are compared through the diagnostics
IGNORED_KEYS = ("estimate", "source")


def corpus() -> list[str]:
    files = [
        *(REPO / "src/wodcraft/library").rglob("*.wod"),
        *(REPO / "spec/conformance").glob("*.wod"),
        *(REPO / "examples").glob("*.wod"),
    ]
    return [path.read_text(encoding="utf-8") for path in files]


def mutate(text: str, rng: random.Random) -> str:
    characters = list(text)
    for _ in range(rng.randint(0, 4)):
        if not characters:
            break
        index = rng.randrange(len(characters))
        operation = rng.choice(["delete", "insert", "duplicate"])
        if operation == "delete":
            del characters[index]
        elif operation == "insert":
            characters.insert(index, rng.choice(MUTATION_CHARACTERS))
        else:
            characters.insert(index, characters[index])
    return "".join(characters)


def normalize(node):
    """An absent key and a null value mean the same thing in the compiled model."""
    if isinstance(node, dict):
        return {key: normalize(value) for key, value in node.items() if key not in IGNORED_KEYS and value is not None}
    if isinstance(node, list):
        return [normalize(value) for value in node]
    return node


def other(binary: str, path: Path) -> dict:
    process = subprocess.run([binary, "compile", str(path)], capture_output=True, text=True)
    if not process.stdout.strip():
        return {"ok": False, "diagnostics": [], "documents": [], "crashed": process.stderr.strip()[:200]}
    return json.loads(process.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("binary", help="the other implementation's command line")
    parser.add_argument("--cases", type=int, default=400)
    parser.add_argument("--seed", type=int, default=0)
    arguments = parser.parse_args()

    rng = random.Random(arguments.seed)
    sources = corpus()
    mismatches: list[str] = []

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "case.wod"
        for _ in range(arguments.cases):
            source = mutate(rng.choice(sources), rng)
            path.write_text(source, encoding="utf-8")
            mine = compile_source(source, str(path))
            theirs = other(arguments.binary, path)

            mine_diagnostics = [(d.code, d.span.line) for d in mine.diagnostics]
            their_diagnostics = [(d["code"], d["line"]) for d in theirs.get("diagnostics", [])]
            if mine.ok != theirs.get("ok") or mine_diagnostics != their_diagnostics:
                mismatches.append(f"diagnostics differ\n{source!r}\n  here:  {mine_diagnostics}\n  there: {their_diagnostics}")
            elif mine.ok:
                expected = normalize(json.loads(json.dumps(mine.documents)))
                found = normalize(theirs.get("documents", []))
                if expected != found:
                    mismatches.append(f"documents differ\n{source!r}\n  here:  {json.dumps(expected)[:400]}\n  there: {json.dumps(found)[:400]}")
            if len(mismatches) >= 5:
                break

    for mismatch in mismatches:
        print(mismatch, file=sys.stderr)
    print(f"{arguments.cases} sources compiled by both implementations, {len(mismatches)} mismatch(es)")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
