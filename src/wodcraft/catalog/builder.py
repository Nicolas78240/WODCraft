#!/usr/bin/env python3
"""Unified catalog builder (package version).

Thin wrapper reusing the repo scripts logic to build data/movements_catalog.json.
"""
import json
from pathlib import Path


def main():
    # Reuse repository script if available; else fail gracefully.
    root = Path(__file__).resolve().parents[3]
    script = root / "scripts" / "build_catalog.py"
    if script.exists():
        import runpy
        runpy.run_path(str(script))
    else:
        raise SystemExit("Catalog builder script not found. Run within repository.")


if __name__ == "__main__":
    main()

