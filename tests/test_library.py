"""The standard library shipped with the compiler (SPEC §10)."""

from __future__ import annotations

import json

import pytest

from wodcraft.api import LIBRARY_DIR, compile_file, parse_file
from wodcraft.emit.source import format_source

LIBRARY_FILES = sorted(LIBRARY_DIR.rglob("*.wod"))
IDS = [path.relative_to(LIBRARY_DIR).with_suffix("").as_posix() for path in LIBRARY_FILES]


def test_the_library_ships_the_standard_collections():
    # SPEC §10: "The standard library ships girls/, heroes/, open/ and, since 1.2, benchmarks/."
    collections = {path.parent.name for path in LIBRARY_FILES}
    assert {"girls", "heroes", "open", "benchmarks"} <= collections


def test_the_crossfit_total_adds_up_three_lifts_of_three_attempts():
    from wodcraft.api import compile_source

    result = compile_source("use benchmarks/crossfit_total\n")
    assert result.ok, result.report()
    workout = result.document
    assert workout["wodcraft"] == "1.2"
    lifts = [block for block in workout["blocks"] if block["type"] == "max_load"]
    assert [lift["items"][0]["movement"] for lift in lifts] == ["back_squat", "strict_press", "deadlift"]
    assert {lift["attempts"] for lift in lifts} == {3}
    assert workout["score"]["aggregate"] == "sum" and workout["score"]["unit"] == "load"


def test_the_library_is_not_empty():
    assert len(LIBRARY_FILES) >= 30


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_compiles_without_an_error(path):
    result = compile_file(path)
    assert result.ok, result.report()


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_compiles_without_a_warning(path):
    # The shipped workouts are the reference: they must not trip W100–W104 either.
    result = compile_file(path)
    assert [(d.code, d.span.line) for d in result.diagnostics] == []


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_is_written_in_canonical_form(path):
    source_file, diags = parse_file(path)
    assert not diags.has_errors
    assert format_source(source_file) == path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_has_a_title_and_a_stimulus(path):
    result = compile_file(path)
    document = result.document
    assert document["title"], path.name
    assert document.get("meta", {}).get("stimulus"), path.name


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_is_tagged_as_a_benchmark(path):
    tags = compile_file(path).document.get("meta", {}).get("tags", [])
    assert "benchmark" in tags, path.name
    # girls/, heroes/ and open/ name their collection in a tag; benchmarks/ already says "benchmark"
    assert path.parent.name in tags or path.parent.name == "benchmarks", path.name


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_has_exactly_one_document(path):
    assert len(compile_file(path).documents) == 1


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_is_json_serialisable(path):
    json.dumps(compile_file(path).document, ensure_ascii=False)


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_has_a_score(path):
    score = compile_file(path).document["score"]
    assert score["type"] in {"time", "rounds+reps", "rounds", "reps", "load", "distance", "calories", "none", "multi"}


def use_name(path) -> str:
    return path.relative_to(LIBRARY_DIR).with_suffix("").as_posix()


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_can_be_reached_by_use(path):
    from wodcraft.api import compile_source

    result = compile_source(f"use {use_name(path)}\n", "main.wod")

    assert result.ok, result.report()
    assert result.document["blocks"], use_name(path)
    assert result.document["blocks"][0]["used"]["path"] == use_name(path)


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_a_library_workout_can_also_be_used_with_its_extension(path):
    from wodcraft.api import compile_source

    result = compile_source(f"use {use_name(path)}.wod\n", "main.wod")

    assert result.ok, result.report()


@pytest.mark.parametrize("path", LIBRARY_FILES, ids=IDS)
def test_every_library_workout_can_be_rendered_and_resolved(path):
    from wodcraft.emit import board, markdown
    from wodcraft.emit.timeline import render_timeline, timeline
    from wodcraft.profile import Profile
    from wodcraft.semantics.resolve import resolve

    document = compile_file(path).document
    for profile in (Profile("men", "rx", "kg"), Profile("women", "scaled", "lb")):
        resolved = resolve(document, profile)
        assert board.render(resolved)
        assert markdown.to_markdown(resolved)
        render_timeline(timeline(resolved))


def test_the_library_titles_are_unique():
    titles = [compile_file(path).document["title"] for path in LIBRARY_FILES]
    assert len(titles) == len(set(titles))


def test_the_named_benchmarks_are_present():
    names = set(IDS)
    assert {"girls/fran", "girls/helen", "girls/cindy", "heroes/murph"} <= names
