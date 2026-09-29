"""Shared fixtures and helpers for the WODCraft test suite.

Everything here is deliberately thin: the tests assert on precise AST / JSON values,
so the helpers only remove boilerplate (compiling a snippet, listing diagnostic codes,
dropping the volatile ``source`` and ``estimate`` keys before comparing documents).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wodcraft.api import LIBRARY_DIR, Result, compile_source
from wodcraft.catalog import load_catalog, load_equivalences
from wodcraft.diagnostics import DiagnosticBag
from wodcraft.syntax.lexer import Line, split_lines
from wodcraft.syntax.lexer import tokenize as _tokenize
from wodcraft.syntax.parser import parse_source

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFORMANCE_DIR = REPO_ROOT / "spec" / "conformance"


# --------------------------------------------------------------------------- compiling


def compile_wod(source: str, *, file: str = "test.wod", estimate: bool = False, **kwargs) -> Result:
    """Compile a snippet. Estimates are off by default: they add W102/W103 noise."""
    return compile_source(source, file, estimate=estimate, **kwargs)


def codes(result: Result) -> list[str]:
    return [d.code for d in result.diagnostics]


def coded_lines(result: Result) -> list[tuple[str, int]]:
    """``[(code, line), …]`` — what most diagnostic assertions compare against."""
    return [(d.code, d.span.line) for d in result.diagnostics]


def only(result: Result):
    """The single diagnostic of a result, asserting there is exactly one."""
    assert len(result.diagnostics) == 1, coded_lines(result)
    return result.diagnostics[0]


def blocks(source: str, **kwargs) -> list[dict]:
    result = compile_wod(source, **kwargs)
    assert result.ok, result.report()
    return result.document["blocks"]


def first_block(source: str, **kwargs) -> dict:
    return blocks(source, **kwargs)[0]


def items(source: str, **kwargs) -> list[dict]:
    return first_block(source, **kwargs)["items"]


def first_item(source: str, **kwargs) -> dict:
    return items(source, **kwargs)[0]


# --------------------------------------------------------------------------- comparing


def strip_source(obj):
    """Drop ``source`` spans so two documents can be compared on meaning alone."""
    if isinstance(obj, dict):
        return {k: strip_source(v) for k, v in obj.items() if k != "source"}
    if isinstance(obj, list):
        return [strip_source(x) for x in obj]
    return obj


def strip_estimate(obj):
    """Drop ``estimate`` — excluded from conformance comparison by SPEC §16."""
    if isinstance(obj, dict):
        return {k: strip_estimate(v) for k, v in obj.items() if k != "estimate"}
    if isinstance(obj, list):
        return [strip_estimate(x) for x in obj]
    return obj


# --------------------------------------------------------------------------- lexing


def tokens_of(text: str, indent: int = 0) -> list:
    """Tokenize one line of source, ignoring diagnostics."""
    return _tokenize(Line(1, indent, text, text), DiagnosticBag(), None)


def token_texts(text: str) -> list[str]:
    return [t.text for t in tokens_of(text)]


def lex(source: str) -> tuple[list[Line], DiagnosticBag]:
    bag = DiagnosticBag()
    lines, _ = split_lines(source, bag, "test.wod")
    return lines, bag


def parse(source: str, file: str = "test.wod"):
    return parse_source(source, file)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="session")
def catalog():
    return load_catalog()


@pytest.fixture(scope="session")
def equivalences():
    return load_equivalences()


@pytest.fixture(scope="session")
def library_dir() -> Path:
    return LIBRARY_DIR


@pytest.fixture(scope="session")
def library_files(library_dir: Path) -> list[Path]:
    files = sorted(library_dir.rglob("*.wod"))
    assert files, "the standard library must ship at least one .wod file"
    return files


@pytest.fixture(scope="session")
def conformance_dir() -> Path:
    return CONFORMANCE_DIR


@pytest.fixture
def fran(library_dir: Path) -> str:
    return (library_dir / "girls" / "fran.wod").read_text(encoding="utf-8")


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch) -> Path:
    """A clean cwd, so ``Profile.discover`` never picks up the developer's athlete.toml."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
