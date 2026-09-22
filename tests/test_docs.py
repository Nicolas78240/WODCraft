"""Every WODCraft snippet written in the documentation must compile.

This is the house rule of the project: documentation that drifts from the implementation is how the
previous version of WODCraft died. Any ```wod block in a Markdown file, and any whiteboard example
in the README console blocks, is checked here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wodcraft.api import compile_source

ROOT = Path(__file__).resolve().parents[1]
# The original proposal is kept as a historical note; its snippets are sketches, not 1.0 syntax.
SKIPPED = {"docs/PROPOSITION-v1.md"}
MARKDOWN = sorted(
    path
    for path in [
        *ROOT.glob("*.md"),
        *(ROOT / "docs").glob("*.md"),
        *(ROOT / "spec").glob("*.md"),
        *(ROOT / "src/wodcraft/library").glob("*.md"),
    ]
    if path.is_file() and path.relative_to(ROOT).as_posix() not in SKIPPED
)
FENCE = re.compile(r"^```wod\n(.*?)^```", re.MULTILINE | re.DOTALL)


def snippets() -> list[tuple[str, int, str]]:
    found = []
    for path in MARKDOWN:
        text = path.read_text(encoding="utf-8")
        for match in FENCE.finditer(text):
            line = text[: match.start()].count("\n") + 1
            found.append((path.relative_to(ROOT).as_posix(), line, match.group(1)))
    return found


SNIPPETS = snippets()
IDS = [f"{name}:{line}" for name, line, _ in SNIPPETS]


def test_the_documentation_actually_contains_snippets():
    assert len(SNIPPETS) >= 8


@pytest.mark.parametrize(("name", "line", "source"), SNIPPETS, ids=IDS)
def test_every_documented_snippet_compiles(name, line, source):
    if "..." in source and "3-6-9" not in source:
        pytest.skip(f"{name}:{line} is an elided example")
    result = compile_source(source, f"{name}:{line}")
    assert result.ok, f"{name} line {line}:\n{result.report()}"


@pytest.mark.parametrize(("name", "line", "source"), SNIPPETS, ids=IDS)
def test_every_documented_snippet_is_canonical_or_explicitly_loose(name, line, source):
    """Snippets may be written loosely, but they must survive a format round-trip."""
    if "..." in source and "3-6-9" not in source:
        pytest.skip(f"{name}:{line} is an elided example")
    from wodcraft.api import format_source

    formatted, diagnostics = format_source(source, f"{name}:{line}")
    assert not [d for d in diagnostics if d.severity.value == "error"]
    again, _ = format_source(formatted, f"{name}:{line}")
    assert again == formatted, f"{name} line {line}: formatting is not a fixed point"


# --------------------------------------------------------------------------- console transcripts

CONSOLE = re.compile(r"^```console\n\$ (wodc [^\n]*)\n(.*?)^```", re.MULTILINE | re.DOTALL)


def transcripts() -> list[tuple[str, int, str, str]]:
    found = []
    for path in MARKDOWN:
        text = path.read_text(encoding="utf-8")
        for match in CONSOLE.finditer(text):
            if "\n$ " in match.group(2):  # a block with several commands: skipped, one command per block
                continue
            line = text[: match.start()].count("\n") + 1
            found.append((path.relative_to(ROOT).as_posix(), line, match.group(1), match.group(2)))
    return found


TRANSCRIPTS = transcripts()


@pytest.mark.parametrize(
    ("name", "line", "command", "expected"),
    TRANSCRIPTS,
    ids=[f"{name}:{line}" for name, line, _, _ in TRANSCRIPTS],
)
def test_every_console_transcript_matches_the_real_output(name, line, command, expected, capsys, monkeypatch):
    """A README transcript is a promise: run the command and compare, word for word."""
    from wodcraft.cli import main

    monkeypatch.chdir(ROOT)
    argv = command.split()[1:]
    missing = [a for a in argv if (a.endswith(".wod") or a.endswith(".toml")) and not (ROOT / a).exists()]
    if missing:
        pytest.skip(f"{name}:{line} refers to files that are not in the repository: {missing}")

    assert main(argv) == 0
    printed = capsys.readouterr().out
    assert printed.strip() == expected.strip(), f"{name} line {line}: the transcript no longer matches"
