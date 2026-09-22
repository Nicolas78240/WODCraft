"""Duration estimates (SPEC §15 I200, W102, W103)."""

from __future__ import annotations

import pytest

from conftest import compile_wod
from wodcraft.diagnostics import DiagnosticBag
from wodcraft.semantics.estimate import (
    DEFAULT_REP_PACE,
    DEFAULT_SET_REST,
    FATIGUE,
    MAX_LOAD_FACTOR,
    SPREAD,
    block_seconds,
    estimate_workout,
    item_seconds,
    load_factor,
)


def estimate(source: str) -> dict | None:
    result = compile_wod(source, estimate=True)
    assert result.ok, result.report()
    return result.document.get("estimate")


# --------------------------------------------------------------------------- items


def test_reps_cost_the_catalog_pace(catalog):
    item = {"type": "movement", "movement": "burpee", "quantity": {"kind": "reps", "reps": 10}}
    assert item_seconds(item, catalog) == 10 * catalog.movements["burpee"].pace_for("reps")


def test_a_movement_without_a_pace_falls_back_to_the_default(catalog):
    item = {"type": "movement", "movement": "not_in_the_catalog", "quantity": {"kind": "reps", "reps": 10}}
    assert item_seconds(item, catalog) == 10 * DEFAULT_REP_PACE


def test_a_dual_quantity_is_estimated_on_the_men_value(catalog):
    item = {"type": "movement", "movement": "burpee", "quantity": {"kind": "reps", "reps": {"men": 20, "women": 10}}}
    assert item_seconds(item, catalog) == 20 * catalog.movements["burpee"].pace_for("reps")


def test_a_time_quantity_is_its_own_duration(catalog):
    item = {"type": "movement", "movement": "plank", "quantity": {"kind": "time", "s": 60}}
    assert item_seconds(item, catalog) == 60


def test_a_max_effort_costs_nothing_by_itself(catalog):
    item = {"type": "movement", "movement": "burpee", "quantity": {"kind": "max", "of": "reps"}}
    assert item_seconds(item, catalog) == 0.0


def test_a_distance_is_priced_per_metre(catalog):
    item = {"type": "movement", "movement": "run", "quantity": {"kind": "distance", "m": 400}}
    assert item_seconds(item, catalog) == 400 * catalog.movements["run"].pace_for("distance")


def test_calories_are_priced_per_calorie(catalog):
    item = {"type": "movement", "movement": "row", "quantity": {"kind": "calories", "cal": 20}}
    assert item_seconds(item, catalog) == 20 * catalog.movements["row"].pace_for("calories")


def test_sets_replace_the_quantity_and_add_rest_between_them(catalog):
    item = {"type": "movement", "movement": "back_squat", "sets": {"reps": [5, 5, 5]}}
    pace = catalog.movements["back_squat"].pace_for("reps") or DEFAULT_REP_PACE

    # 15 reps of work, plus the default rest after the first two sets
    assert item_seconds(item, catalog) == 15 * pace + 2 * DEFAULT_SET_REST


def test_a_rest_modifier_overrides_the_default_rest_between_sets(catalog):
    item = {"type": "movement", "movement": "back_squat", "sets": {"reps": [5, 5]}, "modifiers": ["rest 0:30"]}
    pace = catalog.movements["back_squat"].pace_for("reps") or DEFAULT_REP_PACE
    assert item_seconds(item, catalog) == 10 * pace + 30


def test_a_single_set_pays_no_rest(catalog):
    item = {"type": "movement", "movement": "back_squat", "sets": {"reps": [5]}}
    pace = catalog.movements["back_squat"].pace_for("reps") or DEFAULT_REP_PACE
    assert item_seconds(item, catalog) == 5 * pace


# --------------------------------------------------------------------------- load factor


def test_an_unloaded_movement_has_a_neutral_load_factor(catalog):
    assert load_factor({"type": "movement"}, catalog.movements["burpee"]) == 1.0


def test_a_heavier_load_slows_the_estimated_cadence(catalog):
    thruster = catalog.movements["thruster"]
    light = load_factor({"load": {"kg": 20}}, thruster)
    heavy = load_factor({"load": {"kg": 80}}, thruster)
    assert 1.0 < light < heavy


def test_the_load_factor_is_capped(catalog):
    assert load_factor({"load": {"kg": 5000}}, catalog.movements["thruster"]) == MAX_LOAD_FACTOR


def test_a_load_on_an_unknown_movement_is_neutral():
    assert load_factor({"load": {"kg": 100}}, None) == 1.0


def test_a_loaded_movement_is_estimated_slower_than_an_unloaded_one(catalog):
    light = item_seconds({"movement": "thruster", "quantity": {"kind": "reps", "reps": 10}, "load": {"kg": 20}}, catalog)
    heavy = item_seconds({"movement": "thruster", "quantity": {"kind": "reps", "reps": 10}, "load": {"kg": 80}}, catalog)
    assert heavy > light


# --------------------------------------------------------------------------- blocks


def test_a_rest_block_costs_its_seconds(catalog):
    assert block_seconds({"type": "rest", "seconds": 90}, catalog) == 90


def test_a_timed_block_costs_its_declared_duration(catalog):
    assert block_seconds({"type": "amrap", "duration_s": 600, "items": []}, catalog) == 600
    assert block_seconds({"type": "emom", "duration_s": 300, "items": []}, catalog) == 300


def test_an_every_block_costs_its_interval_times_its_count(catalog):
    assert block_seconds({"type": "every", "interval_s": 180, "rounds": 5, "items": []}, catalog) == 900


def test_rounds_multiply_their_body(catalog):
    body = [{"type": "movement", "movement": "burpee", "quantity": {"kind": "reps", "reps": 10}}]
    one = block_seconds({"type": "rounds", "rounds": 1, "items": body}, catalog)
    three = block_seconds({"type": "rounds", "rounds": 3, "items": body}, catalog)
    assert three == pytest.approx(3 * one)


def test_a_trailing_rest_is_not_performed_after_the_last_round(catalog):
    body = [
        {"type": "movement", "movement": "burpee", "quantity": {"kind": "reps", "reps": 10}},
        {"type": "rest", "seconds": 60},
    ]
    work = block_seconds({"type": "rounds", "rounds": 1, "items": body[:1]}, catalog)
    total = block_seconds({"type": "rounds", "rounds": 3, "items": body}, catalog)
    assert total == pytest.approx(3 * work + 2 * 60)


def test_a_ladder_pays_each_movement_once_per_ladder_value(catalog):
    body = [{"type": "movement", "movement": "burpee"}]
    total = block_seconds({"type": "for_time", "reps": [21, 15, 9], "items": body}, catalog)
    assert total == pytest.approx(45 * catalog.movements["burpee"].pace_for("reps"))


def test_a_ladder_pays_a_fixed_child_once_per_round(catalog):
    body = [
        {"type": "movement", "movement": "burpee"},
        {"type": "movement", "movement": "run", "quantity": {"kind": "distance", "m": 100}},
    ]
    total = block_seconds({"type": "for_time", "reps": [3, 2, 1], "items": body}, catalog)
    burpees = 6 * catalog.movements["burpee"].pace_for("reps")
    runs = 3 * 100 * catalog.movements["run"].pace_for("distance")
    assert total == pytest.approx(burpees + runs)


# --------------------------------------------------------------------------- the workout estimate


def test_the_estimate_is_a_range_around_the_central_value():
    result = estimate("For time\n  100 Burpee\n")
    assert result is not None
    assert result["min_s"] < result["max_s"]
    assert result["capped_s"] is None
    # the spread is symmetric around the central estimate
    centre = (result["min_s"] + result["max_s"]) / 2
    assert result["max_s"] == pytest.approx(centre * (1 + SPREAD), rel=0.01)


def test_the_spread_is_a_documented_fraction():
    assert 0 < SPREAD < 1


def test_an_open_workout_pays_the_fatigue_factor(catalog):
    body = [{"type": "movement", "movement": "burpee", "quantity": {"kind": "reps", "reps": 100}}]
    work = block_seconds({"type": "for_time", "items": body}, catalog)
    result = estimate("For time\n  100 Burpee\n")
    centre = (result["min_s"] + result["max_s"]) / 2
    assert centre == pytest.approx(work * FATIGUE, rel=0.01)


def test_a_single_fixed_block_has_an_exact_estimate():
    result = estimate("AMRAP 12:00\n  10 Burpee\n")
    assert result == {"min_s": 720, "max_s": 720, "capped_s": None}


def test_the_cap_is_reported_in_the_estimate():
    assert estimate("For time, cap 10:00\n  100 Burpee\n")["capped_s"] == 600.0


def test_an_empty_workout_has_no_estimate():
    assert estimate_workout({"blocks": []}, None, DiagnosticBag(), None) is None


def test_a_workout_whose_work_is_zero_has_no_estimate(catalog):
    workout = {"blocks": [{"type": "max_load", "items": []}]}
    assert estimate_workout(workout, catalog, DiagnosticBag(), None) is None


def test_estimates_can_be_switched_off():
    assert "estimate" not in compile_wod("For time\n  100 Burpee\n", estimate=False).document


def test_a_workout_made_only_of_max_efforts_has_no_estimate():
    # Lynne: every set goes to failure, so no duration can be estimated.
    assert estimate("5 rounds\n  max Bench press bw\n  max Pull-up\n") is None


def test_the_whole_library_gets_an_estimate_or_is_pure_max_effort(library_files):
    from wodcraft.api import compile_file

    without = []
    for path in library_files:
        result = compile_file(path)
        for document in result.documents:
            workouts = [s["workout"] for s in document.get("sections", [])] if document["kind"] == "session" else [document]
            for workout in workouts:
                if "estimate" not in workout:
                    without.append(path.stem)
    assert without == ["lynne"]
