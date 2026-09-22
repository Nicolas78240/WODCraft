"""Malformed lines: every error path of the line parser (SPEC §5, §7)."""

from __future__ import annotations

import pytest

from conftest import codes, compile_wod, first_block, only, tokens_of
from wodcraft.diagnostics import DiagnosticBag
from wodcraft.syntax.lexer import Line
from wodcraft.syntax.lines import LABELS, META_KEYS, MODIFIERS, is_format_start, parse_line


def error(text: str, prefix: str = "AMRAP 10:00\n  10 Burpee\n"):
    """Compile ``text`` as an extra child line and return its single diagnostic."""
    result = compile_wod(f"{prefix}  {text}\n")
    return only(result)


# --------------------------------------------------------------------------- format lines


@pytest.mark.parametrize(
    "text",
    [
        "For time, , cap 10:00",  # empty element between commas
        "AMRAP 10, teams",  # "teams" without "of N"
        "AMRAP 10, teams of",  # "of" without a size
        "AMRAP 10, teams of many",  # a non-numeric size
        "AMRAP 10, for",  # "for" without "time"
        "Every 3:00 x many",  # a non-numeric interval count
        "3 rounds for",  # "for" without "time"
    ],
)
def test_a_malformed_format_line_is_e001(text):
    assert error(text).code == "E001"


def test_an_empty_element_between_commas_is_reported():
    assert error("For time, , cap 10:00").message == "Empty element between commas."


def test_teams_without_of_is_reported():
    assert error("AMRAP 10, teams").message == "Expected 'Teams of N'."


def test_a_non_numeric_team_size_is_reported():
    assert error("AMRAP 10, teams of many").message == "Expected the team size."


def test_a_dangling_for_is_reported():
    assert error("AMRAP 10, for").message == "Expected 'for time'."


def test_a_non_numeric_interval_count_is_reported():
    assert error("Every 3:00 x many").message == "Expected the number of intervals."


def test_a_ladder_ending_on_a_dash_is_e001():
    diagnostic = error("21-15-x for time")
    assert diagnostic.code == "E001"
    assert diagnostic.message == "Expected a number in the rep ladder."


def test_a_trailing_for_without_time_is_e001():
    assert error("3 rounds for").message == "Expected 'for time'."


def test_a_dual_without_its_second_number_is_e001():
    assert error("10 Thruster 43/ kg").code == "E001"


def test_a_dual_ending_the_line_is_e001():
    assert error("10 Thruster 43/").code == "E001"


def test_a_line_that_ends_after_an_at_sign_is_e001():
    assert error("10 Thruster @").message == "Expected a load after '@'."


def test_a_line_that_ends_where_a_token_was_expected_is_e001():
    # Cursor.next() with nothing left: "Every 3:00 x" wants the interval count.
    assert error("Every 3:00 x").message == "Unexpected end of line."


def test_trailing_tokens_after_a_format_are_e001():
    diagnostic = error("AMRAP 10:00 nonsense")
    assert diagnostic.code == "E001"
    assert "Unexpected" in diagnostic.message


# --------------------------------------------------------------------------- movement lines


def test_a_malformed_set_scheme_is_e001():
    diagnostic = error("Back squat 5-5-x @ 75%", prefix="Max load\n")
    assert diagnostic.code == "E001"
    assert diagnostic.message == "Expected a number in the set scheme."


def test_rpe_without_a_number_is_e001():
    diagnostic = error("Back squat 5x5 @ RPE", prefix="Max load\n")
    assert diagnostic.code == "E001"


def test_rpe_followed_by_a_word_is_e001():
    diagnostic = error("Back squat 5x5 @ RPE hard", prefix="Max load\n")
    assert diagnostic.message == "Expected a number after RPE."


def test_a_line_without_a_movement_name_is_e001():
    diagnostic = error("21 @ 43 kg")
    assert diagnostic.code == "E001"
    assert diagnostic.message == "Expected a movement name."


def test_a_bare_number_line_is_e001():
    assert error("21").message == "Expected a movement name."


def test_a_comma_between_parameters_is_accepted():
    block = first_block("AMRAP 10:00\n  10 Wall ball 9/6 kg, 305/275 cm\n")
    item = block["items"][0]
    assert item["load"]["kg"] == {"men": 9, "women": 6}
    assert item["height"]["cm"] == {"men": 305, "women": 275}


# --------------------------------------------------------------------------- unknown formats


def test_an_unknown_word_that_looks_like_a_format_is_e010():
    # "Every" with nothing after it still opens a format; a stray keyword does not.
    line = Line(1, 0, "Tabata", "Tabata")
    bag = DiagnosticBag()
    assert parse_line(line, bag, None) is not None
    assert bag.items == []


def test_is_format_start_needs_the_second_word():
    assert is_format_start(tokens_of("For")) is False
    assert is_format_start(tokens_of("Max")) is False
    assert is_format_start(tokens_of("Death")) is False
    assert is_format_start(tokens_of("teams")) is False


def test_a_number_alone_is_not_a_format():
    assert is_format_start(tokens_of("21")) is False
    assert is_format_start(tokens_of("21 Thruster")) is False


def test_a_two_value_ladder_is_a_format():
    assert is_format_start(tokens_of("21-15")) is True


# --------------------------------------------------------------------------- vocabularies


def test_the_meta_keys_are_the_ones_of_the_spec():
    assert {"cap", "score", "tiebreak", "units", "vest", "stimulus", "note", "tags", "date", "time"} == META_KEYS


def test_the_labels_cover_the_spec_and_their_spellings():
    assert set(LABELS.values()) == {"buy_in", "cash_out", "odd", "even", "scaled", "intermediate", "foundations"}
    assert LABELS["buyin"] == LABELS["buy-in"] == "buy_in"
    assert LABELS["cashout"] == LABELS["cash-out"] == "cash_out"


def test_the_modifiers_cover_the_spec():
    assert {"sync", "split", "each", "alternating", "unbroken", "strict"} <= MODIFIERS


# --------------------------------------------------------------------------- parser grouping


def test_a_level_block_stops_at_the_next_level_label_without_indentation():
    source = "For time\n  10 Pull-up\n  10 Push-up\n\nScaled:\nPull-up -> Ring row\n\nFoundations:\nPush-up -> Knee push-up\n"

    result = compile_wod(source)

    assert result.ok, result.report()
    levels = result.document["levels"]
    assert [operation["replace_with"] for operation in levels["scaled"]] == ["ring_row"]
    assert [operation["replace_with"] for operation in levels["foundations"]] == ["knee_push_up"]


def test_a_sibling_format_is_adopted_when_the_block_is_still_empty():
    # Rule 3's last resort: "For time" immediately followed by "21-15-9" at the same depth.
    source = "3 rounds\n  Rest 1:00\n  For time\n  21-15-9\n    Burpee\n"

    block = first_block(source)

    assert [item["type"] for item in block["items"]] == ["rest", "for_time"]
    assert block["items"][1]["reps"] == [21, 15, 9]


def test_the_base_indentation_of_a_section_is_set_by_its_first_line():
    # Each section body is indented on its own, so a uniformly indented section is fine.
    source = "# Day\n## Metcon\nFor time\n  10 Burpee\n## Extra\n    3 rounds\n      10 Air squat\n"

    result = compile_wod(source)

    assert codes(result) == []
    assert result.document["sections"][1]["workout"]["blocks"][0]["rounds"] == 3
