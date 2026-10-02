"""The shipped standard: the workout library index and the specification resources."""

from __future__ import annotations

import pytest

from wodcraft import library, resources

# --------------------------------------------------------------------------- library index


def test_entries_lists_the_whole_library():
    entries = library.entries()
    assert len(entries) >= 30
    assert {entry.path for entry in entries} >= {"girls/fran", "heroes/murph", "open/11_1"}


def test_an_entry_carries_its_path_title_and_file():
    (fran,) = [entry for entry in library.entries() if entry.path == "girls/fran"]
    assert fran.title == "Fran"
    assert fran.file.name == "fran.wod"
    assert fran.source.startswith("# Fran\n")


def test_entries_filters_by_path():
    assert [entry.path for entry in library.entries("girls/fran")] == ["girls/fran"]


def test_entries_filters_by_title():
    assert [entry.path for entry in library.entries("Open 11.1")] == ["open/11_1"]


def test_the_filter_is_case_insensitive():
    assert [entry.path for entry in library.entries("GIRLS/FRAN")] == ["girls/fran"]


def test_an_unmatched_filter_returns_nothing():
    assert library.entries("zzzz") == []


def test_entries_are_sorted_by_path():
    paths = [entry.path for entry in library.entries()]
    assert paths == sorted(paths)


def test_get_returns_one_entry():
    entry = library.get("girls/fran")
    assert entry is not None
    assert (entry.path, entry.title) == ("girls/fran", "Fran")


def test_get_accepts_an_explicit_extension():
    assert library.get("girls/fran.wod").title == "Fran"


def test_get_returns_none_for_an_unknown_path():
    assert library.get("girls/nowhere") is None


def test_get_refuses_to_escape_the_library():
    assert library.get("../../pyproject") is None
    assert library.get("../../../etc/passwd") is None


def test_every_entry_has_a_title_taken_from_its_heading():
    for entry in library.entries():
        assert entry.title
        assert entry.source.splitlines()[0] == f"# {entry.title}"


# --------------------------------------------------------------------------- resources


def test_the_specification_is_reachable():
    assert resources.spec_dir().is_dir()
    assert (resources.spec_dir() / "SPEC.md").is_file()


def test_the_specification_text_is_the_1_0_draft():
    text = resources.spec_text()
    assert text.startswith("# WODCraft Language Specification")
    assert "## 16. Conformance" in text


def test_the_schema_is_a_json_object():
    schema = resources.schema()
    assert isinstance(schema, dict)
    assert schema


def test_an_environment_override_wins(tmp_path, monkeypatch):
    (tmp_path / "SPEC.md").write_text("# Mine\n", encoding="utf-8")
    monkeypatch.setenv("WODCRAFT_SPEC_DIR", str(tmp_path))

    assert resources.spec_dir() == tmp_path
    assert resources.spec_text() == "# Mine\n"


def test_a_missing_specification_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("WODCRAFT_SPEC_DIR", str(tmp_path / "absent"))
    monkeypatch.setattr(resources, "_PACKAGED", tmp_path / "absent")
    monkeypatch.setattr(resources, "_REPO", tmp_path / "absent")

    with pytest.raises(FileNotFoundError) as excinfo:
        resources.spec_dir()

    assert "WODCRAFT_SPEC_DIR" in str(excinfo.value)


def test_the_filter_matches_a_substring_of_any_path_or_title():
    # "fran" is in Fran and in War Frank
    assert [entry.path for entry in library.entries("fran")] == ["girls/fran", "heroes/war_frank"]


def test_the_library_ships_the_girls_and_the_heroes():
    collections = [entry.path.split("/")[0] for entry in library.entries()]
    assert collections.count("girls") == 22
    assert collections.count("heroes") == 51
