"""Validate every workout of the standard library against spec/workout.schema.json."""

from __future__ import annotations

import sys

from jsonschema import Draft202012Validator

from wodcraft.api import LIBRARY_DIR, compile_file
from wodcraft.resources import schema


def main() -> int:
    validator = Draft202012Validator(schema())
    failures = 0
    files = sorted(LIBRARY_DIR.rglob("*.wod"))
    for path in files:
        result = compile_file(path)
        if not result.ok:
            print(f"{path}: does not compile\n{result.report()}")
            failures += 1
            continue
        for document in result.documents:
            for error in validator.iter_errors(document):
                print(f"{path}: {'/'.join(str(p) for p in error.path)}: {error.message}")
                failures += 1
    print(f"{len(files)} workouts checked against the schema, {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
