"""Documents, sessions and block ownership (SPEC §3, §4.1)."""

from __future__ import annotations

import pytest

from conftest import blocks, coded_lines, compile_wod, first_block, only, parse
from wodcraft.syntax.ast import Block, MovementLine


def types(nodes: list[dict]) -> list[str]:
    return [n["type"] for n in nodes]


def names(nodes: list[dict]) -> list[str]:
    return [n.get("movement") or n["type"] for n in nodes]


# --------------------------------------------------------------------------- documents (§3)


def test_a_file_without_a_heading_is_one_untitled_document():
    source_file, diags = parse("For time\n  10 Burpee\n")
    assert len(source_file.documents) == 1
    assert source_file.documents[0].title is None
    assert diags.items == []


def test_a_hash_heading_starts_a_document():
    source_file, _ = parse("# Fran\nFor time\n  10 Burpee\n")
    (document,) = source_file.documents
    assert document.title == "Fran"
    assert document.span.line == 1


def test_several_documents_in_one_file():
    source = "# Part A\nAMRAP 5\n  10 Burpee\n\n# Part B\nFor time\n  50 Air squat\n"

    result = compile_wod(source)

    assert result.ok, result.report()
    assert [d["title"] for d in result.documents] == ["Part A", "Part B"]
    assert [d["blocks"][0]["type"] for d in result.documents] == ["amrap", "for_time"]


def test_lines_before_the_first_heading_form_an_untitled_document():
    result = compile_wod("AMRAP 5\n  10 Burpee\n\n# B\nFor time\n  10 Burpee\n")
    assert [d["title"] for d in result.documents] == [None, "B"]


def test_a_document_with_section_headings_is_a_session():
    source = "# Tuesday\ndate: 2026-09-23\n## Warm-up\n3 rounds\n  10 Air squat\n## Metcon\nAMRAP 10\n  10 Burpee\n"

    result = compile_wod(source)

    assert result.ok, result.report()
    session = result.document
    assert session["kind"] == "session"
    assert session["date"] == "2026-09-23"
    assert [s["title"] for s in session["sections"]] == ["Warm-up", "Metcon"]
    assert [s["workout"]["blocks"][0]["type"] for s in session["sections"]] == ["rounds", "amrap"]


def test_each_session_section_is_a_workout_document():
    result = compile_wod("# Day\n## Metcon\nAMRAP 10\n  10 Burpee\n")
    workout = result.document["sections"][0]["workout"]
    assert workout["kind"] == "workout"
    assert workout["title"] == "Metcon"
    assert workout["score"] == {"type": "rounds+reps"}


def test_a_session_preamble_accepts_only_meta_lines():
    result = compile_wod("# Day\n10 Burpee\n## Metcon\nAMRAP 10\n  10 Burpee\n")
    diagnostic = only(result)
    assert (diagnostic.code, diagnostic.span.line) == ("E014", 2)
    assert diagnostic.suggestion == "move this line under a '## Section' heading"


def test_a_heading_must_start_at_column_one():
    result = compile_wod("For time\n  10 Burpee\n  # Indented\n")
    assert ("E004", 3) in coded_lines(result)


def test_session_time_and_units_reach_the_document():
    result = compile_wod("# Day\ntime: 18:30\nunits: lb\ntags: class, evening\n## Metcon\nAMRAP 10\n  10 Burpee\n")
    session = result.document
    assert session["time"] == "18:30"
    assert session["units"] == "lb"
    assert session["tags"] == ["class", "evening"]


def test_session_units_are_the_default_for_its_sections():
    result = compile_wod("# Day\nunits: lb\n## Metcon\nFor time\n  21 Thruster 95\n")
    item = result.document["sections"][0]["workout"]["blocks"][0]["items"][0]
    assert item["load"] == {"kg": 43, "lb": 95, "unit": "lb", "written": 95}


# --------------------------------------------------------------------------- rule 1: indented children


def test_rule_1_indented_children_belong_to_the_block_above():
    # Arrange
    source = "3 rounds\n  10 Air squat\n  10 Push-up\n"

    # Act
    block = first_block(source)

    # Assert
    assert block["type"] == "rounds"
    assert names(block["items"]) == ["air_squat", "push_up"]


def test_rule_1_nests_to_any_depth():
    source = "3 rounds\n  AMRAP 4\n    10 Burpee\n    10 Air squat\n  Rest 1:00\n"

    block = first_block(source)

    assert block["type"] == "rounds"
    assert types(block["items"]) == ["amrap", "rest"]
    assert names(block["items"][0]["items"]) == ["burpee", "air_squat"]
    assert block["items"][1]["seconds"] == 60.0


def test_rule_1_wins_over_rule_2():
    # "For time" has indented children, so it does not also swallow the sibling below.
    source = "For time\n  10 Burpee\n\n3 rounds\n  10 Air squat\n"

    compiled = blocks(source)

    assert types(compiled) == ["for_time", "rounds"]
    assert names(compiled[0]["items"]) == ["burpee"]


def test_indented_children_under_a_movement_line_are_e004():
    result = compile_wod("3 rounds\n  10 Burpee\n    10 Air squat\n")
    diagnostic = only(result)
    assert (diagnostic.code, diagnostic.span.line) == ("E004", 3)
    assert diagnostic.message == "Only a format or label line can have indented children."


def test_dedenting_below_the_first_line_is_e004():
    # The first line sets the base indentation; going below it is inconsistent.
    result = compile_wod("    3 rounds\n  10 Burpee\n")
    assert ("E004", 2) in coded_lines(result)


def test_a_partial_dedent_reattaches_to_the_nearest_shallower_line():
    # SPEC §2: "a line is a child of the nearest previous line with a smaller indentation",
    # so the 2-space line below a 4-space one is simply a child of "3 rounds".
    result = compile_wod("3 rounds\n    10 Burpee\n  10 Air squat\n")
    assert result.diagnostics == []
    assert names(result.document["blocks"][0]["items"]) == ["burpee", "air_squat"]


# --------------------------------------------------------------------------- rule 2: the main format


def test_rule_2_the_first_format_owns_the_rest_of_the_body():
    # SPEC §4.1 example: "For time" + an un-indented "21-15-9" with indented movements.
    source = "For time, cap 10:00\n21-15-9\n  Thruster 43/30 kg\n  Pull-up\n"

    block = first_block(source)

    # For time + a single untimed child merge into one canonical block (SPEC §13)
    assert block["type"] == "for_time"
    assert block["reps"] == [21, 15, 9]
    assert block["cap_s"] == 600.0
    assert names(block["items"]) == ["thruster", "pull_up"]


def test_rule_2_stops_at_the_next_timed_format():
    source = "AMRAP 5\n10 Burpee\nAMRAP 5\n10 Air squat\n"

    compiled = blocks(source)

    assert types(compiled) == ["amrap", "amrap"]
    assert names(compiled[0]["items"]) == ["burpee"]
    assert names(compiled[1]["items"]) == ["air_squat"]


def test_rule_2_stops_at_a_level_label():
    source = "For time\n100 Burpee\n\nScaled:\n  Burpee -> Knee push-up\n"

    result = compile_wod(source)

    assert result.ok, result.report()
    assert names(result.document["blocks"][0]["items"]) == ["burpee"]
    assert result.document["levels"]["scaled"][0]["replace_with"] == "knee_push_up"


def test_rule_2_takes_an_untimed_format_with_it():
    # "3 rounds" is untimed, so the main "For time" keeps owning it.
    source = "For time\n3 rounds\n  10 Burpee\n"

    block = first_block(source)

    assert block["type"] == "for_time"
    assert block["rounds"] == 3


def test_rule_2_applies_only_to_the_first_format_of_the_body():
    source = "For time\n21-15-9\n  Burpee\n"
    assert first_block(source)["reps"] == [21, 15, 9]


def test_emom_owns_its_unindented_slot_labels():
    # SPEC §4.1 example
    source = "EMOM 12\nOdd: 12/10 cal Row\nEven: 10 Burpee\n"

    block = first_block(source)

    assert block["type"] == "emom"
    assert block["duration_s"] == 720.0
    assert [(i["type"], i["slot"]) for i in block["items"]] == [("slot", "odd"), ("slot", "even")]
    assert block["items"][0]["items"][0]["quantity"] == {"kind": "calories", "cal": {"men": 12, "women": 10}}
    assert block["items"][1]["items"][0]["movement"] == "burpee"


def test_min_n_slots():
    source = "EMOM 15\nMin 1: 10 Burpee\nMin 2: 15 Air squat\nMin 3: 12/10 cal Row\n"

    block = first_block(source)

    assert [i["slot"] for i in block["items"]] == [1, 2, 3]
    assert names(block["items"][1]["items"]) == ["air_squat"]


# --------------------------------------------------------------------------- rule 3: siblings


def test_rule_3_a_later_block_owns_the_following_siblings():
    # "AMRAP 4" is not the first format of the body, so it takes the sibling lines
    # below it up to the next format / label.
    source = "3 rounds\n  AMRAP 4\n  10 Burpee\n  10 Air squat\n"

    block = first_block(source)

    assert types(block["items"]) == ["amrap"]
    assert names(block["items"][0]["items"]) == ["burpee", "air_squat"]


def test_rule_3_stops_at_the_next_format_line():
    source = "3 rounds\n  AMRAP 2\n  10 Burpee\n  AMRAP 2\n  10 Air squat\n"

    block = first_block(source)

    assert types(block["items"]) == ["amrap", "amrap"]
    assert names(block["items"][0]["items"]) == ["burpee"]
    assert names(block["items"][1]["items"]) == ["air_squat"]


def test_rule_3_gives_a_format_block_the_labels_that_follow_it():
    # SPEC §4.1 rule 3: "Buy-in:" belongs to the For time it follows, not to the rounds above it.
    source = "3 rounds\n  For time\n  10 Burpee\n  Buy-in: 20 Double-under\n"

    block = first_block(source)

    assert types(block["items"]) == ["for_time"]
    assert types(block["items"][0]["items"]) == ["movement", "buy_in"]


def test_rule_3_stops_a_label_block_at_the_next_label():
    source = "3 rounds\n  Buy-in: 20 Double-under\n  Cash-out: 20 Sit-up\n"

    block = first_block(source)

    assert types(block["items"]) == ["buy_in", "cash_out"]


def test_a_label_takes_its_inline_movement_only():
    source = "For time\n  Buy-in: 50 Double-under\n  100 Burpee\n"

    block = first_block(source)

    assert types(block["items"]) == ["buy_in", "movement"]
    assert names(block["items"][0]["items"]) == ["double_under"]
    assert block["items"][1]["movement"] == "burpee"


def test_a_label_without_inline_content_owns_its_indented_children():
    source = "For time\n  Buy-in:\n    50 Double-under\n    20 Burpee\n  100 Air squat\n"

    block = first_block(source)

    assert types(block["items"]) == ["buy_in", "movement"]
    assert names(block["items"][0]["items"]) == ["double_under", "burpee"]


def test_buy_in_and_cash_out_wrap_the_main_work():
    source = "For time\n  Buy-in: 1 mi Run\n  100 Pull-up\n  Cash-out: 1 mi Run\n"

    block = first_block(source)

    assert types(block["items"]) == ["buy_in", "movement", "cash_out"]


def test_two_timed_blocks_in_sequence_need_an_untimed_parent():
    # SPEC §4.1: the indented form is the way to chain timed blocks.
    source = "3 rounds\n  AMRAP 4\n    10 Burpee\n  Rest 1:00\n"

    block = first_block(source)

    assert block["rounds"] == 3
    assert types(block["items"]) == ["amrap", "rest"]


# --------------------------------------------------------------------------- level blocks (§9)


def test_a_level_label_owns_the_lines_below_it():
    source = "21-15-9 for time\n  Thruster 95/65 lb\n  Pull-up\n\nScaled:\n  Thruster 65/45 lb\n  Pull-up -> Jumping pull-up\n"

    result = compile_wod(source)

    assert result.ok, result.report()
    operations = result.document["levels"]["scaled"]
    assert [o["movement"] for o in operations] == ["thruster", "pull_up"]
    assert operations[0]["load"]["written"] == {"men": 65, "women": 45}
    assert operations[1]["replace_with"] == "jumping_pull_up"


def test_a_level_block_ends_at_the_next_level_label():
    source = (
        "AMRAP 12:00\n  10 Box jump 24/20 in\n  10 Wall ball 20/14 lb\n\n"
        "Intermediate:\n  Box jump 20/16 in\n\n"
        "Scaled:\n  Box jump -> Step-up 20/16 in\n  Wall ball 14/10 lb\n"
    )

    levels = compile_wod(source).document["levels"]

    assert sorted(levels) == ["intermediate", "scaled"]
    assert len(levels["intermediate"]) == 1
    assert len(levels["scaled"]) == 2


def test_levels_are_not_part_of_the_blocks():
    result = compile_wod("For time\n  10 Pull-up\n\nScaled:\n  Pull-up -> Ring row\n")
    assert types(result.document["blocks"]) == ["for_time"]
    assert names(result.document["blocks"][0]["items"]) == ["pull_up"]


def test_an_arrow_outside_a_level_block_is_e014():
    result = compile_wod("For time\n  10 Burpee\n  10 Pull-up -> Ring row\n")
    diagnostic = only(result)
    assert (diagnostic.code, diagnostic.span.line) == ("E014", 3)


def test_three_levels_keep_their_own_operations():
    source = (
        "AMRAP 12:00\n  10 Box jump 24/20 in\n\n"
        "Intermediate:\n  Box jump 20/16 in\n\n"
        "Scaled:\n  Box jump -> Step-up 20/16 in\n\n"
        "Foundations:\n  Box jump -> Step-up 12/12 in\n"
    )
    levels = compile_wod(source).document["levels"]
    assert levels["intermediate"][0]["height"]["in"] == {"men": 20, "women": 16}
    assert levels["scaled"][0]["replace_with"] == "step_up"
    assert levels["foundations"][0]["height"]["in"] == {"men": 12, "women": 12}


# --------------------------------------------------------------------------- AST shape


def test_the_parsed_tree_keeps_block_and_movement_nodes():
    source_file, _ = parse("3 rounds\n  21 Thruster 43/30 kg\n")
    (document,) = source_file.documents
    (block,) = document.body.statements
    assert isinstance(block, Block)
    assert (block.kind, block.rounds) == ("rounds", 3)
    (movement,) = block.children
    assert isinstance(movement, MovementLine)
    assert movement.name == "Thruster"
    assert movement.quantity.kind == "reps"
    assert movement.quantity.value.men == 21
    assert movement.params[0].kind == "load"
    assert (movement.params[0].value.men, movement.params[0].value.women) == (43, 30)


def test_source_spans_are_one_based():
    block = first_block("# A\n\nFor time\n  10 Burpee\n")
    assert block["source"] == {"line": 3, "col": 1}
    assert block["items"][0]["source"] == {"line": 4, "col": 6}


def test_source_file_keeps_the_raw_lines():
    source_file, _ = parse("For time\n  10 Burpee\n")
    assert source_file.lines[:2] == ["For time", "  10 Burpee"]
    assert source_file.path == "test.wod"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("For time\n  10 Burpee\n", ["for_time"]),
        ("AMRAP 10\n  10 Burpee\n", ["amrap"]),
        ("EMOM 10\n  10 Burpee\n", ["emom"]),
        ("Every 1:00 x 10\n  10 Burpee\n", ["every"]),
        ("Tabata\n  max Burpee\n", ["tabata"]),
        ("Death by Burpee\n", ["death_by"]),
        ("Max load\n  Back squat 5x5\n", ["max_load"]),
        ("3 rounds\n  10 Burpee\n", ["rounds"]),
        ("21-15-9\n  Burpee\n", ["ladder"]),
    ],
)
def test_every_format_reaches_the_compiled_tree(source, expected):
    assert types(blocks(source)) == expected
