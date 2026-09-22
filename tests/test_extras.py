"""Localisation, the api formatting helper and the remaining CLI options."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import compile_wod
from wodcraft import api
from wodcraft.cli import EXIT_DIAGNOSTICS, EXIT_OK, main
from wodcraft.emit import board


def document(source: str, estimate: bool = False) -> dict:
    result = compile_wod(source, estimate=estimate)
    assert result.ok, result.report()
    return result.document


def run(argv, capsys) -> tuple[int, str, str]:
    status = main(argv)
    captured = capsys.readouterr()
    return status, captured.out, captured.err


# --------------------------------------------------------------------------- display names


def test_the_english_name_is_the_default(catalog):
    assert catalog.get("Thruster").display_name() == "Thruster"
    assert catalog.get("Thruster").display_name("en") == "Thruster"


def test_a_french_name_falls_back_to_the_first_alias(catalog):
    burpee = catalog.get("Pull-up")
    assert burpee.display_name("fr") == burpee.fr[0][:1].upper() + burpee.fr[0][1:]


def test_every_catalog_entry_has_a_french_display_name(catalog):
    # Nothing in the catalog falls back to English today; the fallback is still exercised
    # by the synthetic entry below.
    assert [m.id for m in catalog.movements.values() if m.display_name("fr") == m.name and not m.fr] == []


def test_a_movement_without_a_french_alias_keeps_its_english_name():
    from wodcraft.catalog import Movement

    lonely = Movement(id="x", name="Thing", family="G", quantities=("reps",), params=(), equipment="other")

    assert lonely.display_name("fr") == "Thing"


def test_an_unknown_language_falls_back_to_english(catalog):
    assert catalog.get("Thruster").display_name("de") == "Thruster"


# --------------------------------------------------------------------------- board localisation


def test_the_board_can_be_rendered_in_french():
    english = board.render(document("For time\n  100 Pull-up\n"))
    french = board.render(document("For time\n  100 Pull-up\n"), lang="fr")
    assert "Pull-up" in english
    assert french != english
    assert "Traction" in french


def test_localisation_does_not_mutate_the_document():
    compiled = document("For time\n  100 Pull-up\n")
    board.render(compiled, lang="fr")
    assert compiled["blocks"][0]["items"][0]["name"] == "Pull-up"


def test_localisation_reaches_nested_items():
    compiled = document("3 rounds\n  AMRAP 4:00\n    10 Pull-up\n")
    assert "Traction" in board.render(compiled, lang="fr")


def test_localisation_reaches_every_section_of_a_session():
    compiled = document("# Day\n## A\nFor time\n  10 Pull-up\n## B\nAMRAP 5:00\n  10 Pull-up\n")
    assert board.render(compiled, lang="fr").count("Traction") == 2


def test_an_unknown_movement_id_is_left_alone():
    compiled = {"kind": "workout", "blocks": [{"type": "for_time", "items": [{"type": "movement", "movement": "nope", "name": "Nope"}]}]}
    assert "Nope" in board.render(compiled, lang="fr")


# --------------------------------------------------------------------------- api.format_source


def test_format_source_returns_the_canonical_text():
    text, diagnostics = api.format_source("for time, cap 10\n      400m Run\n", "a.wod")
    assert text == "For time, cap 10:00\n  400 m Run\n"
    assert diagnostics == []


def test_format_source_returns_the_input_unchanged_when_parsing_failed():
    source = "AMRAP 12 m\n  10 Burpee\n"

    text, diagnostics = api.format_source(source, "a.wod")

    assert text == source
    assert [d.code for d in diagnostics] == ["E001"]


def test_format_source_reports_warnings_without_giving_up():
    # a warning is not a reason to refuse: the text is still canonical, the warning is reported
    text, diagnostics = api.format_source("for time\n  1 m Run\n")
    assert text == "For time\n  1 m Run\n"
    assert [d.code for d in diagnostics] == ["W100"]


def test_format_source_refuses_a_source_that_does_not_compile():
    # "AMRAP" without a duration parses but does not compile: formatting it would invent "AMRAP 0:00"
    source = "AMRAP\n  10 Burpee\n"
    text, diagnostics = api.format_source(source)
    assert text == source
    assert [d.code for d in diagnostics] == ["E034"]


def test_format_source_is_exported():
    assert "format_source" in api.__all__


# --------------------------------------------------------------------------- cli extras


def test_show_can_render_in_french(tmp_path, capsys):
    path = tmp_path / "a.wod"
    path.write_text("For time\n  100 Pull-up\n", encoding="utf-8")

    _, out, _ = run(["show", "--lang", "fr", str(path)], capsys)

    assert "Traction" in out


def test_check_strict_turns_warnings_into_a_failure(tmp_path, capsys):
    path = tmp_path / "a.wod"
    path.write_text("For time\n  1 m Run\n", encoding="utf-8")

    status, out, _ = run(["check", "--strict", str(path)], capsys)

    assert status == EXIT_DIAGNOSTICS
    assert "--strict" in out


def test_check_strict_stays_green_on_a_clean_file(tmp_path, capsys):
    path = tmp_path / "a.wod"
    path.write_text("For time\n  100 Burpee\n", encoding="utf-8")

    status, out, _ = run(["check", "--strict", str(path)], capsys)

    assert status == EXIT_OK
    assert "valid" in out


def test_exporting_a_workout_without_a_date_to_ics_fails_cleanly(tmp_path, capsys):
    path = tmp_path / "a.wod"
    path.write_text("# Fran\nFor time\n  100 Burpee\n", encoding="utf-8")

    status, _, err = run(["export", "ics", str(path)], capsys)

    assert status == EXIT_DIAGNOSTICS
    assert "add 'date: YYYY-MM-DD'" in err
    assert "a.wod" in err


def test_timer_resolves_with_a_profile(tmp_path, capsys):
    path = tmp_path / "a.wod"
    path.write_text("EMOM 2:00\n  10 Thruster 43/30 kg\n", encoding="utf-8")

    status, out, _ = run(["timer", "--category", "women", str(path)], capsys)

    assert status == EXIT_OK
    assert "30 kg" in out


def test_timer_of_a_broken_file_exits_one(tmp_path, capsys):
    path = tmp_path / "a.wod"
    path.write_text("For time\n  10 Frobnicate\n", encoding="utf-8")

    status, _, err = run(["timer", str(path)], capsys)

    assert status == EXIT_DIAGNOSTICS
    assert "E020" in err


def test_show_of_a_broken_file_exits_one(tmp_path, capsys):
    path = tmp_path / "a.wod"
    path.write_text("For time\n  10 Frobnicate\n", encoding="utf-8")

    status, _, err = run(["show", str(path)], capsys)

    assert status == EXIT_DIAGNOSTICS
    assert "E020" in err


def test_build_json_stays_parsable_for_every_conformance_case(conformance_dir, tmp_path, capsys):
    cases = [c for c in sorted(conformance_dir.glob("*.wod")) if c.with_suffix(".json").exists()]

    status, out, _ = run(["build", *[str(c) for c in cases]], capsys)

    assert status == EXIT_OK
    assert len(json.loads(out)) >= len(cases)


def test_the_title_of_a_library_file_without_a_heading_is_its_stem(tmp_path):
    from wodcraft import library

    path = tmp_path / "x.wod"
    path.write_text("For time\n  10 Burpee\n", encoding="utf-8")
    assert library._title(path) == "x"


def test_profile_discover_falls_back_to_the_user_config(tmp_path, monkeypatch):
    from wodcraft.profile import Profile

    home = tmp_path / "home"
    (home / ".config" / "wodcraft").mkdir(parents=True)
    (home / ".config" / "wodcraft" / "athlete.toml").write_text('units = "lb"\n', encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    empty = tmp_path / "empty"
    empty.mkdir()

    profile = Profile.discover(empty)

    assert profile is not None
    assert profile.units == "lb"
