"""The public API surface: compile_source, compile_file, parse_file, Result."""

from __future__ import annotations

import json

import pytest

from wodcraft.api import LIBRARY_DIR, Library, Result, check_file, compile_file, compile_source, parse_file
from wodcraft.catalog import load_catalog, load_equivalences


def test_compile_source_returns_a_result():
    result = compile_source("For time\n  10 Burpee\n", "a.wod")
    assert isinstance(result, Result)
    assert result.ok is True
    assert result.path == "a.wod"
    assert result.source_lines[0] == "For time"


def test_compile_source_works_without_a_file_name():
    result = compile_source("For time\n  10 Burpee\n")
    assert result.ok is True
    assert result.path is None
    assert result.diagnostics == []


def test_the_document_property_is_the_first_document():
    result = compile_source("# A\nFor time\n  10 Burpee\n\n# B\nAMRAP 5\n  10 Burpee\n")
    assert result.document is result.documents[0]
    assert result.document["title"] == "A"


def test_the_document_property_is_none_when_nothing_compiled():
    result = compile_source("")
    assert result.documents == []
    assert result.document is None


def test_ok_is_false_when_an_error_is_present():
    assert compile_source("For time\n  10 Frobnicate\n").ok is False


def test_ok_stays_true_with_only_warnings():
    result = compile_source("For time\n  1 m Run\n")
    assert result.ok is True
    assert [d.code for d in result.diagnostics] == ["W100"]


def test_report_renders_every_diagnostic_with_its_source_line():
    report = compile_source("For time\n  10 Frobnicate\n", "a.wod").report()
    assert "a.wod:2:6: error E020" in report
    assert "  10 Frobnicate" in report


def test_report_of_a_clean_file_is_empty():
    assert compile_source("For time\n  10 Burpee\n").report() == ""


def test_diagnostics_are_sorted_by_position():
    result = compile_source("For time\n  10 Frobnicate\n  10 Nonsense\n")
    lines = [d.span.line for d in result.diagnostics]
    assert lines == sorted(lines)


def test_compile_file_reads_the_file(library_dir):
    result = compile_file(library_dir / "girls" / "fran.wod")
    assert result.ok, result.report()
    assert result.document["title"] == "Fran"
    assert result.path.endswith("fran.wod")


def test_check_file_is_compile_file(library_dir):
    path = library_dir / "girls" / "fran.wod"
    assert check_file(path).document == compile_file(path).document


def test_parse_file_returns_the_syntax_tree_and_the_bag(library_dir):
    source_file, diags = parse_file(library_dir / "girls" / "fran.wod")
    assert [d.title for d in source_file.documents] == ["Fran"]
    assert diags.items == []


def test_a_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        compile_file("does-not-exist.wod")


def test_the_compiled_document_is_json_serialisable(library_files):
    for path in library_files:
        for document in compile_file(path).documents:
            json.dumps(document, ensure_ascii=False)


def test_estimates_can_be_disabled():
    assert "estimate" not in compile_source("For time\n  100 Burpee\n", estimate=False).document
    assert "estimate" in compile_source("For time\n  100 Burpee\n", estimate=True).document


def test_a_custom_catalog_can_be_injected(tmp_path):
    path = tmp_path / "mini.toml"
    path.write_text('[movements.jump]\nname = "Jump"\nfamily = "G"\nquantities = ["reps"]\nparam = "none"\n', encoding="utf-8")

    result = compile_source("For time\n  10 Jump\n", catalog=load_catalog(str(path)))

    assert result.ok, result.report()
    assert result.document["blocks"][0]["items"][0]["movement"] == "jump"
    # and the real catalog is no longer reachable
    assert compile_source("For time\n  10 Burpee\n", catalog=load_catalog(str(path))).ok is False


def test_custom_equivalences_can_be_injected(tmp_path):
    path = tmp_path / "eq.toml"
    path.write_text("load = [{ kg = 43, lb = 999 }]\nheight = []\n", encoding="utf-8")

    result = compile_source("For time\n  10 Thruster 43 kg\n", equivalences=load_equivalences(str(path)))

    assert result.document["blocks"][0]["items"][0]["load"]["lb"] == 999


# --------------------------------------------------------------------------- library resolution (§10)


def test_the_standard_library_directory_exists():
    assert LIBRARY_DIR.is_dir()
    assert (LIBRARY_DIR / "girls" / "fran.wod").is_file()


def test_library_find_resolves_a_standard_path():
    assert Library().find("girls/fran").name == "fran.wod"


def test_library_find_accepts_an_explicit_extension():
    assert Library().find("girls/fran.wod").name == "fran.wod"


def test_library_find_returns_none_for_an_unknown_path():
    assert Library().find("girls/nowhere") is None


def test_extra_library_paths_take_precedence(tmp_path):
    (tmp_path / "girls").mkdir()
    (tmp_path / "girls" / "fran.wod").write_text("# Mine\nAMRAP 5\n  10 Burpee\n", encoding="utf-8")

    result = compile_source("use girls/fran\n", library_paths=[tmp_path])

    assert result.document["blocks"][0]["used"]["title"] == "Mine"


def test_the_file_directory_is_searched_first(tmp_path):
    (tmp_path / "local.wod").write_text("# Local\nAMRAP 5\n  10 Burpee\n", encoding="utf-8")
    result = compile_source("use local\n", str(tmp_path / "main.wod"))
    assert result.ok, result.report()


def test_a_library_workout_is_loaded_once(tmp_path):
    used = tmp_path / "used.wod"
    used.write_text("# Used\nAMRAP 5\n  10 Burpee\n", encoding="utf-8")
    library = Library([tmp_path])

    first = library.load("used")
    second = library.load("used")

    assert first is second


def test_diagnostics_of_a_used_file_are_reported_with_its_own_path(tmp_path):
    (tmp_path / "broken.wod").write_text("# Broken\nFor time\n  10 Frobnicate\n", encoding="utf-8")

    result = compile_source("use broken\n", str(tmp_path / "main.wod"))

    codes = [(d.code, d.span.line, (d.span.file or "").endswith("broken.wod")) for d in result.diagnostics]
    assert ("E020", 3, True) in codes
    assert result.ok is False
