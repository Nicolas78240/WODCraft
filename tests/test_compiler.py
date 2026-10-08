"""Semantics: benchmark workouts, duals, conversions, score, team, vest, use (SPEC §11–§13)."""

from __future__ import annotations

import pytest

from conftest import blocks, compile_wod, first_block, first_item, items
from wodcraft import SPEC_VERSION


def names(nodes: list[dict]) -> list[str]:
    return [n.get("movement") or n["type"] for n in nodes]


def score_of(source: str, **kwargs) -> dict:
    result = compile_wod(source, **kwargs)
    assert result.ok, result.report()
    return result.document["score"]


# --------------------------------------------------------------------------- envelope


def test_a_compiled_workout_carries_the_spec_version_and_kind():
    result = compile_wod("# Fran\nFor time\n  10 Burpee\n")
    document = result.document
    assert document["wodcraft"] == "1.0"  # the format of a document that uses nothing newer
    assert SPEC_VERSION == "1.2"
    assert document["kind"] == "workout"
    assert document["title"] == "Fran"
    assert set(document) == {"wodcraft", "kind", "title", "blocks", "score"}


def test_a_workout_using_a_1_1_construct_is_stamped_1_1():
    assert compile_wod("For time\n  10 Ring row | Scap pull\n").document["wodcraft"] == "1.1"
    session = compile_wod("# S\n## A\nFor time\n  10 Burpee\n## B\nFor time\n  10 Ring row | Scap pull\n").document
    assert session["wodcraft"] == "1.1"
    assert [s["workout"]["wodcraft"] for s in session["sections"]] == ["1.0", "1.1"]


def test_an_alternative_option_takes_the_first_quantity_when_it_has_none():
    item = compile_wod("For time\n  10 Ring row | Scap pull | 8 Pull-up\n").document["blocks"][0]["items"][0]
    assert item["movement"] == "ring_row"
    assert [(o["movement"], o["quantity"]["reps"]) for o in item["or"]] == [("scapular_pull_up", 10), ("pull_up", 8)]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("For time\n  10 Ring row |\n", [("E016", 1), ("E001", 2)]),
        ("For time\n  10 Ring row | Pull-up\n\nScaled:\n  Ring row -> Jumping pull-up | Burpee\n", [("E014", 5)]),
        ("For time\n  10 cal Row | Burpee\n", [("E033", 2)]),
    ],
)
def test_alternative_errors(source, expected):
    assert [(d.code, d.span.line) for d in compile_wod(source).diagnostics] == expected


def test_an_untitled_workout_has_a_null_title():
    assert compile_wod("For time\n  10 Burpee\n").document["title"] is None


# --------------------------------------------------------------------------- the benchmarks


def test_fran_compiles_to_a_capped_for_time_ladder(library_dir):
    # Arrange
    source = (library_dir / "girls" / "fran.wod").read_text(encoding="utf-8")

    # Act
    result = compile_wod(source)

    # Assert
    assert result.ok, result.report()
    document = result.document
    (block,) = document["blocks"]
    assert block["type"] == "for_time"
    assert block["reps"] == [21, 15, 9]
    assert block["cap_s"] == 600.0
    assert names(block["items"]) == ["thruster", "pull_up"]
    assert block["items"][0]["load"]["written"] == {"men": 95, "women": 65}
    assert block["items"][0]["load"]["kg"] == {"men": 43, "women": 30}
    # the pull-up takes its reps from the ladder, so it carries no quantity
    assert "quantity" not in block["items"][1]
    assert document["score"] == {"type": "time", "capped": "reps"}
    assert document["meta"]["tags"] == ["girls", "benchmark"]


def test_helen_compiles_to_three_rounds_for_time(library_dir):
    source = (library_dir / "girls" / "helen.wod").read_text(encoding="utf-8")

    document = compile_wod(source).document

    (block,) = document["blocks"]
    assert (block["type"], block["rounds"]) == ("for_time", 3)
    run, swing, pull_up = block["items"]
    assert run["quantity"] == {"m": 400, "unit": "m", "written": 400, "kind": "distance"}
    assert swing["quantity"] == {"kind": "reps", "reps": 21}
    assert swing["load"]["unit"] == "pood"
    assert swing["load"]["kg"] == {"men": 24, "women": 16}
    assert pull_up["quantity"] == {"kind": "reps", "reps": 12}
    assert document["score"] == {"type": "time"}


def test_murph_compiles_to_a_for_time_with_a_buy_in_and_a_cash_out(library_dir):
    source = (library_dir / "heroes" / "murph.wod").read_text(encoding="utf-8")

    document = compile_wod(source).document

    (block,) = document["blocks"]
    assert block["type"] == "for_time"
    assert [i["type"] for i in block["items"]] == ["buy_in", "movement", "movement", "movement", "cash_out"]
    assert block["items"][0]["items"][0]["quantity"]["m"] == 1609.344
    assert block["items"][-1]["items"][0]["quantity"]["m"] == 1609.344
    assert [i["quantity"]["reps"] for i in block["items"][1:4]] == [100, 200, 300]
    assert document["meta"]["vest"]["lb"] == {"men": 20, "women": 14}
    assert document["score"] == {"type": "time"}


def test_cindy_compiles_to_an_amrap_scored_by_rounds_and_reps(library_dir):
    source = (library_dir / "girls" / "cindy.wod").read_text(encoding="utf-8")

    document = compile_wod(source).document

    (block,) = document["blocks"]
    assert (block["type"], block["duration_s"]) == ("amrap", 1200.0)
    assert names(block["items"]) == ["pull_up", "push_up", "air_squat"]
    assert [i["quantity"]["reps"] for i in block["items"]] == [5, 10, 15]
    assert document["score"] == {"type": "rounds+reps"}
    assert document["levels"]["scaled"] == [
        {"movement": "pull_up", "replace_with": "ring_row", "name": "Ring row", "source": {"line": 10, "col": 3}},
        {"movement": "push_up", "replace_with": "knee_push_up", "name": "Knee push-up", "source": {"line": 11, "col": 3}},
    ]


# --------------------------------------------------------------------------- duals


def test_a_dual_load_keeps_both_categories():
    item = first_item("For time\n  21 Thruster 43/30 kg\n")
    assert item["load"]["kg"] == {"men": 43, "women": 30}
    assert item["load"]["written"] == {"men": 43, "women": 30}


def test_a_single_load_applies_to_both_categories():
    item = first_item("For time\n  21 Thruster 43 kg\n")
    assert item["load"]["kg"] == 43


def test_dual_reps():
    assert first_item("For time\n  50/40 Double-under\n")["quantity"]["reps"] == {"men": 50, "women": 40}


def test_dual_calories():
    assert first_item("For time\n  20/16 cal Row\n")["quantity"]["cal"] == {"men": 20, "women": 16}


def test_dual_height():
    assert first_item("For time\n  10 Box jump 24/20 in\n")["height"]["cm"] == {"men": 60, "women": 50}


def test_dual_distance():
    assert first_item("For time\n  400/300 m Run\n")["quantity"]["m"] == {"men": 400, "women": 300}


# --------------------------------------------------------------------------- conversions (§13)


def test_ninety_five_pounds_is_forty_three_kilos():
    # SPEC §13 names this equivalence explicitly.
    assert first_item("For time\n  21 Thruster 95 lb\n")["load"]["kg"] == 43


def test_twenty_four_inches_is_sixty_centimetres():
    assert first_item("For time\n  10 Box jump 24 in\n")["height"]["cm"] == 60


def test_a_mile_is_1609_344_metres():
    assert first_item("For time\n  1 mi Run\n")["quantity"]["m"] == 1609.344


def test_a_kilometre_is_a_thousand_metres():
    assert first_item("For time\n  2 km Row\n")["quantity"]["m"] == 2000


def test_one_pood_is_sixteen_kilos():
    assert first_item("For time\n  21 Kettlebell swing 1 pood\n")["load"]["kg"] == 16


def test_a_load_is_always_exposed_in_both_units():
    load = first_item("For time\n  21 Thruster 43/30 kg\n")["load"]
    assert set(load) == {"kg", "lb", "unit", "written"}
    assert load["lb"] == {"men": 95, "women": 65}


# --------------------------------------------------------------------------- units default (§6)


def test_units_kg_makes_a_bare_number_a_load_in_kilos():
    item = first_item("units: kg\nFor time\n  21 Thruster 43\n")
    assert item["load"] == {"kg": 43, "lb": 95, "unit": "kg", "written": 43}


def test_units_lb_makes_a_bare_number_a_load_in_pounds():
    item = first_item("units: lb\nFor time\n  21 Thruster 95\n")
    assert item["load"] == {"kg": 43, "lb": 95, "unit": "lb", "written": 95}


def test_units_is_not_copied_into_the_meta_block():
    result = compile_wod("units: lb\nFor time\n  21 Thruster 95\n")
    assert "meta" not in result.document


def test_units_do_not_leak_from_one_document_to_the_next():
    result = compile_wod("# A\nunits: lb\nFor time\n  21 Thruster 95\n\n# B\nFor time\n  21 Thruster 43\n")
    assert [d["title"] for d in result.documents] == ["A", "B"]
    # B has no units: line, so its bare load is an error
    assert [d.code for d in result.diagnostics] == ["E031"]


# --------------------------------------------------------------------------- score (§12)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("For time\n  10 Burpee\n", "time"),
        ("3 rounds for time\n  10 Burpee\n", "time"),
        ("21-15-9 for time\n  Burpee\n", "time"),
        ("AMRAP 10\n  10 Burpee\n", "rounds+reps"),
        ("EMOM 10\n  10 Burpee\n", "none"),
        ("Every 1:00 x 10\n  10 Burpee\n", "none"),
        ("Tabata\n  max Air squat\n", "reps"),
        ("Death by Burpee\n", "rounds+reps"),
        ("Max load\n  Back squat 5x5\n", "load"),
        ("3 rounds\n  10 Burpee\n", "none"),
        ("21-15-9\n  Burpee\n", "none"),
    ],
)
def test_score_is_inferred_from_the_main_format(source, expected):
    assert score_of(source)["type"] == expected


def test_an_emom_with_a_max_effort_scores_reps():
    assert score_of("EMOM 10\n  max cal Row\n")["type"] == "reps"


def test_a_capped_for_time_records_the_capped_score():
    assert score_of("For time, cap 10:00\n  100 Burpee\n") == {"type": "time", "capped": "reps"}


def test_a_cap_meta_line_also_caps_the_main_block():
    block = first_block("cap: 12:00\nFor time\n  100 Burpee\n")
    assert block["cap_s"] == 720.0


def test_an_explicit_score_overrides_the_inferred_one():
    assert score_of("score: reps\nAMRAP 20:00\n  400 m Run\n  max Pull-up\n")["type"] == "reps"


def test_an_explicit_score_may_restate_the_inferred_one():
    assert score_of("score: time\nFor time\n  100 Burpee\n")["type"] == "time"


def test_a_tiebreak_is_attached_to_the_score():
    score = score_of("tiebreak: time at the last pull-up\nFor time\n  100 Burpee\n")
    assert score["tiebreak"] == "time at the last pull-up"


def test_several_timed_blocks_produce_a_multi_score():
    score = score_of("AMRAP 5\n  10 Burpee\n\nAMRAP 5\n  10 Air squat\n")
    assert score == {"type": "multi", "parts": [{"type": "rounds+reps", "block": 0}, {"type": "rounds+reps", "block": 1}]}


def test_an_explicit_score_collapses_a_multi_part_workout():
    assert score_of("score: reps\nAMRAP 5\n  10 Burpee\n\nAMRAP 5\n  10 Air squat\n")["type"] == "reps"


# --------------------------------------------------------------------------- team and vest


def test_teams_of_n_becomes_the_team_size():
    result = compile_wod("AMRAP 20, teams of 2\n  10 Burpee\n")
    assert result.document["team"] == {"size": 2}
    # and it is removed from the block itself
    assert "teams" not in result.document["blocks"][0]


def test_a_workout_without_teams_has_no_team_key():
    assert "team" not in compile_wod("AMRAP 20\n  10 Burpee\n").document


def test_vest_is_normalised_like_a_load():
    meta = compile_wod("vest: 20/14 lb\nFor time\n  100 Burpee\n").document["meta"]
    assert meta["vest"] == {"kg": {"men": 9, "women": 6}, "lb": {"men": 20, "women": 14}, "unit": "lb", "written": {"men": 20, "women": 14}}


def test_vest_without_a_unit_uses_the_units_default():
    meta = compile_wod("units: kg\nvest: 9\nFor time\n  100 Burpee\n").document["meta"]
    assert meta["vest"]["kg"] == 9


# --------------------------------------------------------------------------- meta (§6)


def test_notes_and_stimulus_are_repeatable():
    meta = compile_wod("note: one\nnote: two\nstimulus: hard\nFor time\n  10 Burpee\n").document["meta"]
    assert meta["notes"] == ["one", "two"]
    assert meta["stimulus"] == ["hard"]


def test_tags_are_split_on_commas():
    meta = compile_wod("tags: girls, benchmark , 2026\nFor time\n  10 Burpee\n").document["meta"]
    assert meta["tags"] == ["girls", "benchmark", "2026"]


def test_a_meta_value_is_free_text_and_is_not_lexed():
    meta = compile_wod("note: 50 % of the work is the run — see https://a.b\nFor time\n  10 Burpee\n").document["meta"]
    assert meta["notes"] == ["50 % of the work is the run — see https://a.b"]


def test_meta_keys_are_case_insensitive():
    meta = compile_wod("NOTE: hello\nFor time\n  10 Burpee\n").document["meta"]
    assert meta["notes"] == ["hello"]


# --------------------------------------------------------------------------- use (§10)


def test_use_inlines_the_library_workout():
    result = compile_wod("use girls/fran\n")
    assert result.ok, result.report()
    (block,) = result.document["blocks"]
    assert block["type"] == "for_time"
    assert block["reps"] == [21, 15, 9]
    assert block["used"] == {"path": "girls/fran", "title": "Fran"}


def test_use_accepts_an_explicit_wod_extension():
    result = compile_wod("use girls/fran.wod\n")
    assert result.ok, result.report()
    assert result.document["blocks"][0]["used"]["path"] == "girls/fran.wod"


def test_use_accepts_a_path_with_digits_and_underscores():
    result = compile_wod("use open/11_1\n")
    assert result.ok, result.report()
    assert result.document["blocks"][0]["used"] == {"path": "open/11_1", "title": "Open 11.1"}


def test_use_resolves_against_a_local_directory(tmp_path):
    (tmp_path / "local.wod").write_text("# Local\nAMRAP 5\n  10 Burpee\n", encoding="utf-8")
    result = compile_wod("use local\n", file=str(tmp_path / "main.wod"))
    assert result.ok, result.report()
    assert result.document["blocks"][0]["used"] == {"path": "local", "title": "Local"}


def test_use_can_be_mixed_with_local_blocks():
    result = compile_wod("use girls/fran\n\nAMRAP 5\n  10 Burpee\n")
    assert result.ok, result.report()
    assert [b["type"] for b in result.document["blocks"]] == ["for_time", "amrap"]


# --------------------------------------------------------------------------- normalisation (§13)


def test_for_time_plus_a_single_ladder_merge_into_one_block():
    compiled = blocks("For time\n21-15-9\n  Burpee\n")
    assert len(compiled) == 1
    assert compiled[0]["type"] == "for_time"
    assert compiled[0]["reps"] == [21, 15, 9]


def test_the_merge_does_not_happen_when_the_child_carries_a_cap():
    compiled = blocks("For time\n  3 rounds\n    AMRAP 4\n      10 Burpee\n")
    assert compiled[0]["type"] == "for_time"
    assert compiled[0]["rounds"] == 3


def test_an_amrap_with_a_single_rounds_child_merges_too():
    compiled = blocks("AMRAP 12:00\n3 rounds\n  10 Burpee\n")
    assert compiled[0]["type"] == "amrap"
    assert compiled[0]["rounds"] == 3
    assert compiled[0]["duration_s"] == 720.0


def test_a_ladder_gives_its_reps_to_children_without_a_quantity():
    compiled_items = items("21-15-9 for time\n  Thruster 43 kg\n  Pull-up\n")
    assert all("quantity" not in item for item in compiled_items)


def test_a_child_with_its_own_quantity_keeps_it_inside_a_ladder():
    compiled_items = items("21-15-9 for time\n  Thruster 43 kg\n  200 m Run\n")
    assert compiled_items[1]["quantity"]["m"] == 200


# --------------------------------------------------------------------------- movement resolution (§7.2)


@pytest.mark.parametrize(
    ("written", "movement_id"),
    [
        ("Pull-up", "pull_up"),
        ("pull up", "pull_up"),
        ("pullup", "pull_up"),
        ("PULL-UPS", "pull_up"),
        ("Toes-to-bar", "toes_to_bar"),
        ("T2B", "toes_to_bar"),
        ("Double-under", "double_under"),
        ("DU", "double_under"),
        ("Handstand push-up", "handstand_push_up"),
        ("HSPU", "handstand_push_up"),
        ("Burpees", "burpee"),
    ],
)
def test_names_aliases_and_plurals_resolve_to_the_catalog_id(written, movement_id):
    assert first_item(f"For time\n  10 {written}\n")["movement"] == movement_id


def test_the_canonical_name_is_stored_next_to_the_id():
    item = first_item("For time\n  10 t2b\n")
    assert (item["movement"], item["name"]) == ("toes_to_bar", "Toes-to-bar")


THERE_AND_BACK = "For time, cap 25:00, teams of 2, there and back\n  50 cal Row\n  40 Pull-up\n  10 Wall walk\n"


def test_there_and_back_is_a_block_option_that_the_score_carries():
    document = compile_wod(THERE_AND_BACK).document
    block = document["blocks"][0]
    assert block["there_and_back"] is True
    assert document["score"] == {"type": "time", "capped": "reps", "there_and_back": True}
    assert document["wodcraft"] == "1.1"
    assert compile_wod(THERE_AND_BACK.replace("there and back", "aller-retour")).document["blocks"][0]["there_and_back"]


def test_there_and_back_counts_the_whole_path_in_the_estimate():
    there = compile_wod(THERE_AND_BACK, estimate=True).document["estimate"]
    once = compile_wod(THERE_AND_BACK.replace(", there and back", ""), estimate=True).document["estimate"]
    assert there["min_s"] > once["min_s"] * 1.5


def test_there_and_back_does_not_merge_a_ladder_into_its_parent():
    block = compile_wod("For time, there and back\n  21-15-9\n    Thruster 43/30 kg\n    Pull-up\n").document["blocks"][0]
    assert block["there_and_back"] and block["items"][0]["type"] == "ladder"
