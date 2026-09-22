"""The compiler's range, parameter and score checks that the main suite does not reach."""

from __future__ import annotations

import pytest
from conftest import coded_lines, compile_wod, first_item, only

from wodcraft.semantics.compiler import _score_compatible, format_duration


def diagnose(source: str, **kwargs) -> list[tuple[str, int]]:
    return coded_lines(compile_wod(source, **kwargs))


# --------------------------------------------------------------------------- ranges (E035)


@pytest.mark.parametrize(
    ("source", "line"),
    [
        ("AMRAP 0\n  10 Burpee\n", 1),
        ("EMOM 0\n  10 Burpee\n", 1),
        ("For time, cap 0\n  10 Burpee\n", 1),
        ("Every 0 x 5\n  10 Burpee\n", 1),
    ],
)
def test_a_zero_duration_interval_or_cap_is_e035(source, line):
    assert ("E035", line) in diagnose(source)


def test_a_zero_duration_names_what_is_wrong():
    diagnostic = only(compile_wod("AMRAP 0\n  10 Burpee\n"))
    assert diagnostic.message == "The duration must be greater than zero."


def test_tabata_needs_at_least_one_round():
    assert diagnose("Tabata 0\n  max Air squat\n") == [("E035", 1)]


def test_minutes_are_numbered_from_one():
    assert diagnose("EMOM 10:00\n  Min 0: 10 Burpee\n") == [("E035", 2)]


def test_a_zero_load_is_e035():
    assert diagnose("For time\n  10 Thruster 0 kg\n") == [("E035", 2)]


def test_a_negative_dual_load_is_e035():
    assert diagnose("For time\n  10 Thruster 43/0 kg\n") == [("E035", 2)]


# --------------------------------------------------------------------------- W105


def test_an_absurd_rep_count_is_w105():
    result = compile_wod("For time\n  5000 Burpee\n")
    assert [(d.code, d.span.line) for d in result.diagnostics] == [("W105", 2)]
    assert result.ok is True


def test_a_large_but_plausible_rep_count_is_not_flagged():
    assert diagnose("For time\n  300 Air squat\n") == []


# --------------------------------------------------------------------------- parameters


def test_a_distance_after_a_height_movement_is_read_as_a_height():
    # A wall-ball target written in feet rather than inches.
    item = first_item("AMRAP 10:00\n  10 Wall ball 9 kg 10 ft\n")
    assert item["height"]["unit"] == "cm"
    assert item["height"]["cm"] == pytest.approx(304.8, rel=1e-3)


def test_a_distance_parameter_on_a_rep_movement_is_e032():
    diagnostic = only(compile_wod("AMRAP 10:00\n  10 Thruster 43 kg 400 m\n"))
    assert diagnostic.code == "E032"
    assert diagnostic.suggestion == "write it as the quantity, before the movement name"


def test_a_calorie_parameter_on_a_rep_movement_is_e032():
    assert diagnose("AMRAP 10:00\n  10 Thruster 43 kg 20 cal\n") == [("E032", 2)]


def test_a_percentage_of_an_unknown_lift_is_e020():
    assert diagnose("Max load\n  Back squat 5x5 @ 75% Frobnicate\n") == [("E020", 2)]


def test_a_distance_after_the_name_becomes_the_quantity_when_none_was_written():
    # SPEC §7.4: "read as the quantity, when the movement accepts it and no quantity
    # was written".
    item = first_item("For time\n  Row 500 m\n")
    assert item["quantity"] == {"m": 500, "unit": "m", "written": 500, "kind": "distance"}


def test_a_distance_parameter_on_a_movement_that_is_not_measured_in_distance_is_e032():
    diagnostic = only(compile_wod("For time\n  10 Pull-up 400 m\n"))
    assert (diagnostic.code, diagnostic.span.line) == ("E032", 2)
    assert diagnostic.message == "Pull-up does not take a distance parameter."


# --------------------------------------------------------------------------- level blocks


def test_a_non_movement_statement_in_a_level_block_is_e014():
    assert diagnose("For time\n  100 Burpee\n\nScaled:\n  Rest 2:00\n") == [("E014", 5)]


def test_a_level_block_selector_can_carry_a_height():
    source = (
        "AMRAP 10:00\n  10 Box jump 24/20 in\n  10 Box jump 30/24 in\n\n"
        "Scaled:\n  Box jump 30/24 in -> Box jump 24/20 in\n"
    )
    result = compile_wod(source)
    assert result.ok, result.report()
    (operation,) = result.document["levels"]["scaled"]
    assert operation["when"]["height"]["written"] == {"men": 30, "women": 24}


# --------------------------------------------------------------------------- use nesting


def test_a_timed_workout_cannot_be_used_inside_another_timed_block():
    source = "AMRAP 10:00\n  10 Burpee\n  use girls/fran\n"

    result = compile_wod(source)

    codes = [(d.code, d.span.line) for d in result.diagnostics]
    assert ("E015", 3) in codes
    assert result.ok is False


def test_the_message_names_the_used_workout():
    diagnostic = next(d for d in compile_wod("AMRAP 10:00\n  10 Burpee\n  use girls/fran\n").diagnostics if d.code == "E015")
    assert "girls/fran" in diagnostic.message


def test_a_used_workout_fits_under_an_untimed_parent():
    result = compile_wod("3 rounds\n  use girls/fran\n")
    assert result.ok, result.report()


# --------------------------------------------------------------------------- score compatibility


@pytest.mark.parametrize(
    ("declared", "kind", "accepted"),
    [
        ("none", "for_time", True),
        ("reps", "emom", True),
        ("rounds", "emom", True),
        ("time", "emom", False),
        ("time", "for_time", True),
        ("reps", "for_time", True),
        ("load", "for_time", False),
        ("load", "rounds", True),
        ("rounds+reps", "amrap", True),
        ("time", "amrap", False),
        ("load", "max_load", True),
        ("time", "max_load", False),
        ("reps", "tabata", True),
        ("time", "tabata", False),
        ("anything", "unknown_format", True),
    ],
)
def test_score_compatibility_table(declared, kind, accepted):
    assert _score_compatible(declared, kind, None) is accepted


def test_an_untimed_ladder_may_declare_a_load_score():
    result = compile_wod("score: load\n10-9-8\n  Deadlift @ 1.5 bw\n")
    assert result.ok, result.report()
    assert result.document["score"]["type"] == "load"


def test_an_emom_may_declare_a_rounds_score():
    result = compile_wod("score: rounds\nEMOM 30:00\n  5 Pull-up\n")
    assert result.ok, result.report()
    assert result.document["score"]["type"] == "rounds"


# --------------------------------------------------------------------------- helpers


def test_format_duration_is_the_clock_format():
    assert format_duration(90) == "1:30"
    assert format_duration(3600) == "1:00:00"
