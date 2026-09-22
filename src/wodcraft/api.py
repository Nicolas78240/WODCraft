"""Public API: parse, check and compile WODCraft sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from wodcraft.catalog import load_catalog, load_equivalences
from wodcraft.diagnostics import Diagnostic, DiagnosticBag
from wodcraft.library import LIBRARY_DIR
from wodcraft.semantics.compiler import Compiler, Options
from wodcraft.syntax.parser import parse_source

__all__ = ["LIBRARY_DIR", "Library", "Result", "check_file", "compile_file", "compile_source", "format_source", "parse_file"]


@dataclass
class Result:
    documents: list[dict]
    diagnostics: list[Diagnostic]
    source_lines: list[str] = field(default_factory=list)
    path: str | None = None

    @property
    def ok(self) -> bool:
        return not any(d.severity.value == "error" for d in self.diagnostics)

    @property
    def document(self) -> dict | None:
        return self.documents[0] if self.documents else None

    def report(self) -> str:
        return "\n".join(d.format(self.source_lines) for d in self.diagnostics)


class Library:
    """Resolves ``use PATH`` against the local directory, extra paths and the standard library."""

    def __init__(self, paths: list[Path] | None = None, catalog=None, equivalences=None):
        self.paths = list(paths or [])
        self.catalog = catalog
        self.equivalences = equivalences
        self._stack: list[str] = []
        self._cache: dict[str, tuple[dict, DiagnosticBag] | None] = {}

    def find(self, path: str) -> Path | None:
        name = path if path.endswith(".wod") else path + ".wod"
        for base in [*self.paths, LIBRARY_DIR]:
            candidate = (base / name).resolve()
            if candidate.is_file():
                return candidate
        return None

    def load(self, path: str) -> tuple[dict, DiagnosticBag] | str | None:
        """The document and its diagnostics, None when unknown, or "cycle"."""
        if path in self._stack:
            return "cycle"
        if path in self._cache:
            return self._cache[path]
        found = self.find(path)
        if found is None:
            self._cache[path] = None
            return None
        self._stack.append(path)
        try:
            result = _compile(found.read_text(encoding="utf-8"), str(found), self)
        finally:
            self._stack.pop()
        bag = DiagnosticBag(list(result.diagnostics))
        out = (result.document or {}, bag)
        self._cache[path] = out
        return out


def _compile(source: str, file: str | None, library: Library, estimate: bool = True) -> Result:
    source_file, diags = parse_source(source, file)
    options = Options(
        catalog=library.catalog or load_catalog(),
        equivalences=library.equivalences or load_equivalences(),
        load_library=library.load,
        estimate=estimate,
    )
    compiler = Compiler(diags, options, file)
    documents = [compiler.document(doc) for doc in source_file.documents]
    return Result(documents, diags.sorted(), source_file.lines, file)


def compile_source(
    source: str,
    file: str | None = None,
    *,
    library_paths: list[Path] | None = None,
    catalog=None,
    equivalences=None,
    estimate: bool = True,
) -> Result:
    paths = list(library_paths or [])
    if file:
        paths.insert(0, Path(file).resolve().parent)
    return _compile(source, file, Library(paths, catalog, equivalences), estimate)


def compile_file(path: str | Path, **kwargs) -> Result:
    file = Path(path)
    return compile_source(file.read_text(encoding="utf-8"), str(file), **kwargs)


def check_file(path: str | Path, **kwargs) -> Result:
    return compile_file(path, **kwargs)


def format_source(source: str, file: str | None = None) -> tuple[str, list[Diagnostic]]:
    """The canonical form of a source, and the diagnostics found while parsing it.

    The text is returned unchanged when parsing failed."""
    from wodcraft.emit.source import format_source as _format

    source_file, diags = parse_source(source, file)
    if diags.has_errors:
        return source, diags.sorted()
    return _format(source_file), diags.sorted()


def parse_file(path: str | Path):
    file = Path(path)
    return parse_source(file.read_text(encoding="utf-8"), str(file))
