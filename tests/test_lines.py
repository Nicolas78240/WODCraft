"""Line parsing: durations, units, format lines, movement lines (SPEC §2.1, §2.2, §5, §7)."""

from __future__ import annotations

import pytest

from conftest import codes, compile_wod, first_item, items, only, tokens_of
from wodcraft.diagnostics import DiagnosticBag
from wodcraft.syntax.lexer import Line
from wodcraft.syntax.lines import (
    Cursor,
    LineError,
    is_format_start,
    parse_duration,
    parse_line,
)
from wodcraft.syntax.units import fmt_num, format_clock, parse_clock, seconds, unit_kind

# --------------------------------------------------------------------------- units table


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("kg", ("load", "kg")),
        ("kgs", ("load", "kg")),
        ("lb", ("load", "lb")),
        ("lbs", ("load", "lb")),
        ("pood", ("load", "pood")),
        ("in", ("height", "in")),
        ("inches", ("height", "in")),
        ("cm", ("height", "cm")),
        ("m", ("distance", "m")),
        ("km", ("distance", "km")),
        ("mi", ("distance", "mi")),
        ("miles", ("distance", "mi")),
        ("cal", ("calories", "cal")),
        ("calories", ("calories", "cal")),
        ("s", ("time", "s")),
        ("sec", ("time", "s")),
        ("min", ("time", "min")),
        ("minutes", ("time", "min")),
        ("KG", ("load", "kg")),
        ("MIN", ("time", "min")),
    ],
)
def test_unit_kind(word, expected):
    assert unit_kind(word) == expected


def test_unit_kind_of_an_unknown_word_is_none():
    assert unit_kind("stone") is None
    assert unit_kind("burpee") is None


def test_m_is_metres_never_minutes():
    # SPEC §2.1: "`m` is never minutes: it always means metres."
    assert unit_kind("m") == ("distance", "m")


# --------------------------------------------------------------------------- durations


def _duration(text: str, bare_minutes: bool = True) -> float:
    line = Line(1, 0, text, text)
    return parse_duration(Cursor(tokens_of(text), line), bare_minutes)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1:30", 90.0),
        ("12:00", 720.0),
        ("1:00:00", 3600.0),
        ("30 s", 30.0),
        ("30 sec", 30.0),
        ("2 min", 120.0),
        ("20", 1200.0),  # bare N = minutes, format lines only
    ],
)
def test_parse_duration(text, expected):
    assert _duration(text) == expected


def test_bare_number_outside_a_format_line_is_e001():
    with pytest.raises(LineError) as excinfo:
        _duration("5", bare_minutes=False)
    assert excinfo.value.code == "E001"
    assert excinfo.value.suggestion == "write '5:00' or '5 s'"


def test_duration_written_with_m_is_rejected_as_metres():
    # Arrange / Act
    with pytest.raises(LineError) as excinfo:
        _duration("12 m")

    # Assert
    error = excinfo.value
    assert error.code == "E001"
    assert error.message == "'m' means metres, not minutes."
    assert error.suggestion == "write '12 min' or '12:00'"


def test_amrap_with_m_is_e001_on_the_unit_column():
    result = compile_wod("AMRAP 12 m\n  10 Burpee\n")
    diagnostic = only(result)
    assert (diagnostic.code, diagnostic.span.line, diagnostic.span.col) == ("E001", 1, 10)


def test_rest_needs_an_explicit_duration_unit():
    result = compile_wod("3 rounds\n  10 Burpee\n  Rest 5\n")
    assert codes(result) == ["E001"]


@pytest.mark.parametrize(("text", "expected"), [("1:30", 90), ("0:45", 45), ("2:00:30", 7230)])
def test_parse_clock(text, expected):
    assert parse_clock(text) == expected


@pytest.mark.parametrize(("value", "expected"), [(90, "1:30"), (600, "10:00"), (3600, "1:00:00"), (3690, "1:01:30")])
def test_format_clock(value, expected):
    assert format_clock(value) == expected


def test_seconds_converts_minutes_only():
    assert seconds(2, "min") == 120
    assert seconds(30, "s") == 30


@pytest.mark.parametrize(("value", "expected"), [(5, "5"), (5.0, "5"), (1.5, "1.5"), (22.5, "22.5")])
def test_fmt_num(value, expected):
    assert fmt_num(value) == expected


# --------------------------------------------------------------------------- format lines


@pytest.mark.parametrize(
    "text",
    [
        "For time",
        "AMRAP 12",
        "EMOM 10",
        "E2MOM 20",
        "Every 3:00 x 5",
        "Tabata",
        "Death by",
        "Max load",
        "3 rounds",
        "21-15-9",
        "teams of 2",
    ],
)
def test_is_format_start_accepts_every_format(text):
    assert is_format_start(tokens_of(text)) is True


@pytest.mark.parametrize("text", ["21 Thruster", "Rest 2:00", "For the win", "Max effort", "Death march", "use girls/fran", "10 Burpee"])
def test_is_format_start_rejects_non_formats(text):
    assert is_format_start(tokens_of(text)) is False


def test_for_time_block():
    block = _block("For time")
    assert (block.kind, block.for_time, block.cap_s) == ("for_time", True, None)


def test_for_time_with_cap():
    block = _block("For time, cap 10:00")
    assert (block.kind, block.cap_s) == ("for_time", 600.0)


def test_cap_accepts_bare_minutes():
    assert _block("For time, cap 20").cap_s == 1200.0


def test_rounds_for_time():
    block = _block("3 rounds for time")
    assert (block.kind, block.rounds, block.for_time) == ("rounds", 3, True)


def test_rounds_untimed():
    block = _block("3 rounds")
    assert (block.kind, block.rounds, block.for_time) == ("rounds", 3, False)


def test_rft_abbreviation():
    block = _block("5 rft")
    assert (block.kind, block.rounds, block.for_time) == ("rounds", 5, True)


def test_rep_ladder():
    block = _block("21-15-9 for time")
    assert (block.kind, block.reps, block.for_time) == ("ladder", [21, 15, 9], True)


def test_long_rep_ladder():
    assert _block("10-9-8-7-6-5-4-3-2-1 for time").reps == [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]


def test_open_rep_ladder():
    block = _block("3-6-9 ...")
    assert (block.reps, block.reps_open) == ([3, 6, 9], True)


def test_open_ladder_needs_a_constant_step():
    line = Line(1, 0, "3-6-10 ...", "3-6-10 ...")
    bag = DiagnosticBag()
    assert parse_line(line, bag, None) is None
    assert [(d.code, d.span.line) for d in bag.items] == [("E035", 1)]


def test_amrap_duration_forms():
    assert _block("AMRAP 12").duration_s == 720.0
    assert _block("AMRAP 12:00").duration_s == 720.0


def test_emom_interval_is_one_minute():
    block = _block("EMOM 10")
    assert (block.kind, block.duration_s, block.interval_s) == ("emom", 600.0, 60.0)


@pytest.mark.parametrize(("text", "interval"), [("E2MOM 20", 120.0), ("E3MOM 15", 180.0), ("e90mom 90", 5400.0)])
def test_enmom_interval(text, interval):
    block = _block(text)
    assert block.kind == "emom"
    assert block.interval_s == interval


def test_enmom_duration_is_the_total():
    assert _block("E2MOM 20").duration_s == 1200.0


@pytest.mark.parametrize("text", ["Every 3:00 x 5", "Every 3:00 x5", "Every 3:00 for 5 rounds"])
def test_every_interval_and_count(text):
    block = _block(text)
    assert (block.kind, block.interval_s, block.rounds) == ("every", 180.0, 5)


def test_tabata_defaults_to_eight_rounds():
    block = _block("Tabata")
    assert (block.kind, block.rounds, block.interval_s) == ("tabata", 8, 30.0)


def test_tabata_with_an_explicit_round_count():
    assert _block("Tabata 6").rounds == 6


def test_death_by_takes_the_rest_of_the_line_as_its_movement():
    block = _block("Death by Burpee")
    assert block.kind == "death_by"
    assert block.interval_s == 60.0
    assert [child.name for child in block.children] == ["Burpee"]


def test_death_by_alone_opens_a_block():
    block = _block("Death by")
    assert (block.kind, block.children) == ("death_by", [])


def test_max_load():
    assert _block("Max load").kind == "max_load"


def test_teams_of_is_an_option_not_a_format():
    block = _block("AMRAP 20, teams of 2")
    assert (block.kind, block.teams) == ("amrap", 2)


def test_keywords_are_case_insensitive():
    for text in ("for time", "For time", "FOR TIME"):
        assert _block(text).kind == "for_time"


def test_unknown_option_is_e001_with_the_list_of_options():
    result = compile_wod("AMRAP 10, banana\n  10 Burpee\n")
    diagnostic = only(result)
    assert diagnostic.code == "E001"
    assert diagnostic.suggestion == "options are: cap, teams of N, for time, there and back, N attempts"


def test_a_line_with_only_options_is_e010():
    result = compile_wod("teams of 2\n  10 Burpee\n")
    diagnostic = only(result)
    assert diagnostic.code == "E010"
    assert diagnostic.span.line == 1


# --------------------------------------------------------------------------- movement lines


def test_quantity_reps():
    item = first_item("For time\n  21 Thruster 43 kg\n")
    assert item["quantity"] == {"kind": "reps", "reps": 21}


def test_quantity_dual_reps():
    item = first_item("For time\n  50/40 Double-under\n")
    assert item["quantity"] == {"kind": "reps", "reps": {"men": 50, "women": 40}}


def test_quantity_distance_glued_and_spaced_agree():
    glued = first_item("For time\n  400m Run\n")
    spaced = first_item("For time\n  400 m Run\n")
    assert glued["quantity"] == spaced["quantity"] == {"m": 400, "unit": "m", "written": 400, "kind": "distance"}


def test_quantity_calories_dual():
    item = first_item("For time\n  15/12 cal Row\n")
    assert item["quantity"] == {"kind": "calories", "cal": {"men": 15, "women": 12}}


def test_quantity_time_from_a_clock():
    item = first_item("For time\n  1:00 Plank\n")
    assert item["quantity"] == {"kind": "time", "s": 60}


def test_quantity_time_from_seconds():
    assert first_item("For time\n  30 s Plank\n")["quantity"] == {"kind": "time", "s": 30}


def test_quantity_max():
    assert first_item("EMOM 10\n  max Burpee\n")["quantity"] == {"kind": "max", "of": "reps"}


def test_quantity_max_with_a_unit():
    assert first_item("EMOM 10\n  max cal Row\n")["quantity"] == {"kind": "max", "of": "calories"}


def test_fractional_reps_are_e035():
    result = compile_wod("For time\n  10 Burpee\n  2.5 Air squat\n")
    assert codes(result) == ["E035"]


def test_a_load_written_where_the_quantity_belongs_is_e030():
    result = compile_wod("For time\n  10 Burpee\n  43 kg Thruster\n")
    diagnostic = only(result)
    assert (diagnostic.code, diagnostic.span.line) == ("E030", 3)
    assert diagnostic.suggestion == "write the quantity first, e.g. '21 Thruster 43/30 kg'"


# --------------------------------------------------------------------------- names


def test_multi_word_names_stop_at_the_first_number():
    item = first_item("For time\n  10 Hang power clean 61 kg\n")
    assert item["movement"] == "hang_power_clean"


def test_a_name_may_contain_hyphens_and_the_word_to():
    item = first_item("For time\n  10 Dumbbell hang clean-to-overhead 22.5 kg\n")
    assert item["movement"] == "dumbbell_hang_clean_to_overhead"


def test_plural_names_resolve():
    assert first_item("For time\n  10 Burpees\n")["movement"] == "burpee"


def test_french_aliases_resolve():
    assert first_item("For time\n  10 Tractions\n")["movement"] == "pull_up"


# --------------------------------------------------------------------------- sets


def test_sets_nxm_expands_to_one_entry_per_set():
    item = first_item("Max load\n  Back squat 5x5\n")
    assert item["sets"] == {"reps": [5, 5, 5, 5, 5]}


def test_set_ladder():
    item = first_item("Max load\n  Deadlift 5-5-3-3-1-1\n")
    assert item["sets"] == {"reps": [5, 5, 3, 3, 1, 1]}


# --------------------------------------------------------------------------- parameters


def test_load_with_and_without_at_agree():
    plain = first_item("For time\n  21 Thruster 43/30 kg\n")
    at = first_item("For time\n  21 Thruster @ 43/30 kg\n")
    assert plain["load"] == at["load"]


def test_percent_of_the_movement_itself():
    item = first_item("Max load\n  Back squat 5x5 @ 75%\n")
    assert item["percent"] == {"value": 75, "of": "back_squat"}


def test_percent_of_a_named_lift():
    item = first_item("Max load\n  Front squat 3x3 @ 70% Back squat\n")
    assert item["percent"] == {"value": 70, "of": "back_squat"}


def test_percent_accepts_the_noise_word_of():
    item = first_item("Max load\n  Front squat 3x3 @ 70% of Back squat\n")
    assert item["percent"] == {"value": 70, "of": "back_squat"}


def test_percent_of_1rm_spelling_is_accepted():
    # "@ 70% of 1RM Back squat" reads naturally on a whiteboard and means the same thing.
    item = first_item("Max load\n  Front squat 3x3 @ 70% of 1RM Back squat\n")
    assert item["percent"] == {"value": 70, "of": "back_squat"}


def test_rpe():
    assert first_item("Max load\n  Deadlift 5x3 @ RPE 8\n")["rpe"] == 8


def test_bare_bw_is_one_bodyweight():
    assert first_item("For time\n  10 Bench press bw\n")["bodyweight"] == 1


def test_bw_with_a_multiplier():
    assert first_item("For time\n  10 Deadlift @ 1.5 bw\n")["bodyweight"] == 1.5


def test_height_parameter():
    item = first_item("For time\n  10 Box jump 24/20 in\n")
    assert item["height"]["in"] == {"men": 24, "women": 20}


def test_a_duration_after_the_name_is_e032():
    result = compile_wod("For time\n  10 Burpee\n  10 Plank 30 s\n")
    diagnostic = only(result)
    assert (diagnostic.code, diagnostic.span.line) == ("E032", 3)
    assert diagnostic.suggestion == "put the duration first: '30 s Plank'"


# --------------------------------------------------------------------------- modifiers


@pytest.mark.parametrize("modifier", ["sync", "split", "each", "alternating", "unbroken", "strict", "per side"])
def test_known_modifiers(modifier):
    item = first_item(f"AMRAP 10\n  10 Burpee ({modifier})\n")
    assert item["modifiers"] == [modifier]


def test_rest_modifier_keeps_its_duration():
    item = first_item("Max load\n  Back squat 5x5 (rest 2:00)\n")
    assert item["modifiers"] == ["rest 2:00"]


def test_several_modifiers_are_kept_in_order():
    item = first_item('AMRAP 10\n  10 Burpee (unbroken, alternating, "chest to the floor")\n')
    assert item["modifiers"] == ["unbroken", "alternating", "chest to the floor"]


def test_free_text_modifier_loses_its_quotes():
    item = first_item('AMRAP 10\n  10 Burpee ("lateral over the dumbbell")\n')
    assert item["modifiers"] == ["lateral over the dumbbell"]


def test_unknown_modifier_is_e001():
    result = compile_wod("AMRAP 10\n  10 Air squat\n  10 Burpee (sideways)\n")
    diagnostic = only(result)
    assert diagnostic.code == "E001"
    assert "known modifiers" in (diagnostic.suggestion or "")


def test_unclosed_modifier_list_is_e001():
    assert codes(compile_wod("AMRAP 10\n  10 Air squat\n  10 Burpee (unbroken\n")) == ["E001"]


def test_empty_modifier_is_e001():
    assert codes(compile_wod("AMRAP 10\n  10 Air squat\n  10 Burpee ()\n")) == ["E001"]


def test_a_rejected_line_can_leave_its_block_empty():
    # A line the parser rejects is dropped, so a block whose only child was that line
    # reports E016 on top of the line's own error. Both diagnostics are expected.
    result = compile_wod("AMRAP 10\n  10 Burpee (sideways)\n")
    assert [(d.code, d.span.line) for d in result.diagnostics] == [("E016", 1), ("E001", 2)]


# --------------------------------------------------------------------------- rest and use


def test_rest_line():
    rest = items("3 rounds\n  10 Burpee\n  Rest 2:00\n")[1]
    assert rest == {"type": "rest", "seconds": 120.0, "source": {"line": 3, "col": 3}}


def test_use_line_keeps_its_path():
    result = compile_wod("use girls/fran\n")
    assert result.ok, result.report()
    assert result.document["blocks"][0]["used"]["path"] == "girls/fran"


def test_use_without_a_path_is_e001():
    diagnostic = only(compile_wod("use\n"))
    assert diagnostic.code == "E001"
    assert diagnostic.suggestion == "e.g. 'use girls/fran'"


# --------------------------------------------------------------------------- helper


def _block(text: str):
    line = Line(1, 0, text, text)
    bag = DiagnosticBag()
    statement = parse_line(line, bag, None)
    assert not bag.items, [(d.code, d.message) for d in bag.items]
    return statement


@pytest.mark.parametrize(("written", "kept"), [("hold", "hold"), ("hold 10 s", "hold 10 s"), ("hold 0:30", "hold 0:30")])
def test_hold_modifier_keeps_its_duration(written, kept):
    item = first_item(f"AMRAP 10\n  1 Wall walk ({written})\n")
    assert item["modifiers"] == [kept]


def test_hold_takes_a_duration_or_nothing():
    result = compile_wod("AMRAP 10\n  5 Burpee\n  1 Wall walk (hold ten)\n")
    assert (only(result).code, only(result).span.line) == ("E001", 3)
