"""One test per diagnostic code of SPEC §15, checking the code *and* the line."""

from __future__ import annotations

import pytest

from conftest import coded_lines, compile_wod, only
from wodcraft.diagnostics import Diagnostic, DiagnosticBag, Severity, Span


def diagnose(source: str, **kwargs) -> list[tuple[str, int]]:
    return coded_lines(compile_wod(source, **kwargs))


# --------------------------------------------------------------------------- syntax: E001–E004


def test_e001_syntax_error():
    assert diagnose("AMRAP 10\n  10 Burpee\n  10 Air squat ?\n") == [("E001", 3)]


def test_e001_unexpected_end_of_line():
    assert diagnose("AMRAP 10\n  10 Burpee\n  10 Thruster @\n") == [("E001", 3)]


def test_e002_tab_in_indentation():
    assert diagnose("For time\n  10 Burpee\n\t10 Air squat\n") == [("E002", 3)]


def test_e003_decimal_comma():
    assert diagnose("For time\n  10 Thruster 43,5 kg\n") == [("E003", 2)]


def test_e004_inconsistent_indentation():
    assert diagnose("3 rounds\n  10 Burpee\n    10 Air squat\n") == [("E004", 3)]


# --------------------------------------------------------------------------- lines: E010–E016


def test_e010_unrecognised_line():
    assert diagnose("teams of 2\n  10 Burpee\n") == [("E010", 1)]


def test_e011_unknown_label():
    assert diagnose("EMOM 10\n  Warmup: 10 Burpee\n  10 Air squat\n") == [("E011", 2)]


def test_e011_suggests_the_known_labels():
    diagnostic = only(compile_wod("EMOM 10\n  Warmup: 10 Burpee\n  10 Air squat\n"))
    assert "Buy-in" in diagnostic.suggestion and "Scaled" in diagnostic.suggestion


def test_e012_unknown_meta_key():
    assert diagnose("focus: breathing\nAMRAP 10:00\n  10 Burpee\n") == [("E012", 1)]


def test_e012_suggests_the_known_keys():
    diagnostic = only(compile_wod("focus: breathing\nAMRAP 10:00\n  10 Burpee\n"))
    assert diagnostic.suggestion == "known keys: cap, date, note, score, stimulus, tags, tiebreak, time, units, vest"


@pytest.mark.parametrize(
    "line",
    ["score: bananas", "units: stone", "cap: later", "vest: heavy"],
)
def test_e013_invalid_meta_value(line):
    assert diagnose(f"{line}\nAMRAP 10:00\n  10 Burpee\n") == [("E013", 1)]


def test_e014_odd_outside_an_emom():
    # SPEC §15: "Odd: outside an EMOM" is E014, not the generic E015 nesting error.
    assert diagnose("For time\n  100 Burpee\n  Odd: 10 Air squat\n") == [("E014", 3)]


def test_e014_min_n_outside_an_interval_block():
    assert diagnose("AMRAP 10:00\n  10 Burpee\n  Min 1: 10 Air squat\n") == [("E014", 3)]


def test_e014_teams_of_is_not_on_the_outermost_format():
    assert diagnose("3 rounds\n  AMRAP 4, teams of 2\n    10 Burpee\n") == [("E014", 2)]


def test_e014_non_meta_line_in_a_session_preamble():
    assert diagnose("# Day\n10 Burpee\n## Metcon\nAMRAP 10:00\n  10 Burpee\n") == [("E014", 2)]


def test_e014_arrow_outside_a_level_block():
    assert diagnose("For time\n  10 Burpee\n  10 Pull-up -> Ring row\n") == [("E014", 3)]


def test_e014_a_level_block_cannot_change_a_quantity():
    assert diagnose("For time\n  100 Burpee\n\nScaled:\n  50 Burpee\n") == [("E014", 5)]


def test_e014_a_level_block_cannot_change_an_arbitrary_meta_key():
    assert diagnose("For time\n  100 Burpee\n\nScaled:\n  score: reps\n") == [("E014", 5)]


def test_e015_forbidden_nesting():
    assert diagnose("AMRAP 10:00\n  10 Burpee\n  EMOM 5\n    10 Air squat\n") == [("E015", 3)]


def test_e015_names_both_blocks():
    diagnostic = only(compile_wod("AMRAP 10:00\n  10 Burpee\n  EMOM 5\n    10 Air squat\n"))
    assert diagnostic.message == "A EMOM block is not allowed inside AMRAP."
    assert diagnostic.suggestion == "indent it under an untimed block, e.g. '3 rounds'"


def test_e015_death_by_takes_no_nested_block():
    assert diagnose("Death by\n  3 rounds\n    10 Burpee\n") == [("E016", 1), ("E015", 2)]


def test_e016_empty_block():
    assert diagnose("AMRAP 10:00\n") == [("E016", 1)]


def test_e016_names_the_empty_block():
    assert only(compile_wod("AMRAP 10:00\n")).message == "Empty AMRAP block."


def test_max_load_may_be_empty():
    # SPEC §7.1 lets Max load stand on its own line; E016 is not raised for it.
    assert diagnose("Max load\n") == []


# --------------------------------------------------------------------------- movements: E020–E036


def test_e020_unknown_movement():
    assert diagnose("AMRAP 10:00\n  10 Burpee\n  10 Frobnicate\n") == [("E020", 3)]


def test_e020_suggests_close_candidates():
    diagnostic = only(compile_wod("AMRAP 10:00\n  10 Burpee\n  10 Thrusterr 43 kg\n"))
    assert diagnostic.code == "E020"
    assert "Thruster" in diagnostic.suggestion


def test_e020_in_a_level_block():
    assert diagnose("For time\n  10 Pull-up\n\nScaled:\n  Pull-up -> Frobnicate\n") == [("E020", 5)]


def test_e030_missing_quantity():
    assert diagnose("For time\n  Thruster 43/30 kg\n  21 Pull-up\n") == [("E030", 2)]


def test_e030_is_not_raised_inside_a_ladder():
    assert diagnose("21-15-9 for time\n  Thruster 43/30 kg\n  Pull-up\n") == []


def test_e030_is_not_raised_under_max_load_or_death_by():
    assert diagnose("Max load\n  Back squat 5x5\n") == []
    assert diagnose("Death by Burpee\n") == []


def test_e031_load_without_a_unit_and_no_default():
    assert diagnose("For time\n  21 Thruster 43\n  21 Pull-up\n") == [("E031", 2)]


def test_e031_is_silenced_by_a_units_line():
    assert diagnose("units: kg\nFor time\n  21 Thruster 43\n") == []


@pytest.mark.parametrize(
    ("line", "line_number"),
    [("  10 Thruster 24/20 in", 2), ("  10 Box jump 43/30 kg", 2), ("  10 Air squat 43 kg", 2)],
)
def test_e032_parameter_kind_not_accepted(line, line_number):
    assert diagnose(f"AMRAP 10:00\n{line}\n") == [("E032", line_number)]


def test_e032_explains_what_the_movement_expects():
    diagnostic = only(compile_wod("AMRAP 10:00\n  10 Box jump 43/30 kg\n"))
    assert diagnostic.message == "Box jump takes a height (in, cm), not a load."


def test_e033_quantity_kind_not_accepted():
    assert diagnose("For time\n  400 m Thruster 43/30 kg\n") == [("E033", 2)]


def test_e033_explains_the_accepted_quantities():
    diagnostic = only(compile_wod("For time\n  400 m Thruster 43/30 kg\n"))
    assert diagnostic.message == "Thruster is not measured in distance."
    assert diagnostic.suggestion == "it is measured in reps"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("AMRAP\n  10 Burpee\n", [("E034", 1)]),
        ("EMOM\n  10 Burpee\n", [("E034", 1)]),
        ("Every 2:00\n  10 Burpee\n", [("E034", 1)]),
        ("Every x 5\n  10 Burpee\n", [("E034", 1)]),
    ],
)
def test_e034_format_without_its_duration_or_count(source, expected):
    assert diagnose(source) == expected


def test_e035_zero_rounds():
    assert diagnose("0 rounds for time\n  10 Burpee\n") == [("E035", 1)]


def test_e035_zero_in_a_rep_ladder():
    assert diagnose("21-15-0 for time\n  Burpee\n") == [("E035", 1)]


def test_e035_rpe_above_ten():
    assert diagnose("Max load\n  Back squat 5x5 @ RPE 14\n") == [("E035", 2)]


def test_e035_percent_above_two_hundred():
    assert diagnose("Max load\n  Back squat 5x5 @ 250%\n") == [("E035", 2)]


def test_e035_fractional_reps():
    assert diagnose("For time\n  10 Burpee\n  2.5 Air squat\n") == [("E035", 3)]


def test_e035_open_ladder_without_a_constant_step():
    assert diagnose("3-6-10 ... for time\n  Burpee\n") == [("E035", 1)]


def test_e036_score_incompatible_with_the_format():
    assert diagnose("score: rounds+reps\nFor time\n  100 Burpee\n") == [("E036", 2)]


def test_e036_points_at_the_main_block_and_names_the_real_score():
    diagnostic = only(compile_wod("score: rounds+reps\nFor time\n  100 Burpee\n"))
    assert diagnostic.message == "A For time workout cannot be scored by 'rounds+reps'."
    assert diagnostic.suggestion == "this workout scores 'time'"


def test_e036_load_is_not_measurable_by_a_for_time():
    assert diagnose("score: load\nFor time\n  100 Burpee\n") == [("E036", 2)]


def test_score_none_is_always_accepted():
    assert diagnose("score: none\nAMRAP 10:00\n  10 Burpee\n") == []


# --------------------------------------------------------------------------- levels: E040–E041


def test_e040_level_references_a_movement_absent_from_the_rx_work():
    assert diagnose("For time\n  100 Burpee\n\nScaled:\n  Thruster 30/20 kg\n") == [("E040", 5)]


def test_e040_message_names_the_movement():
    diagnostic = only(compile_wod("For time\n  100 Burpee\n\nScaled:\n  Thruster 30/20 kg\n"))
    assert diagnostic.message == "Thruster does not appear in the Rx work."


def test_e041_duplicate_level_block():
    source = "For time\n  21 Thruster 43/30 kg\n\nScaled:\n  Thruster 30/20 kg\n\nScaled:\n  Thruster 20/15 kg\n"
    assert diagnose(source) == [("E041", 7)]


# --------------------------------------------------------------------------- use: E050–E051


def test_e050_use_path_not_found():
    assert diagnose("use girls/nowhere\n") == [("E050", 1)]


def test_e050_suggests_a_working_path():
    assert only(compile_wod("use girls/nowhere\n")).suggestion == "e.g. 'use girls/fran'"


def test_e050_when_no_library_is_configured():
    from wodcraft.diagnostics import DiagnosticBag as Bag
    from wodcraft.semantics.compiler import Compiler, Options
    from wodcraft.syntax.parser import parse_source

    source_file, bag = parse_source("use girls/fran\n", "test.wod")
    compiler = Compiler(bag, Options(load_library=None), "test.wod")
    compiler.document(source_file.documents[0])
    assert [(d.code, d.span.line) for d in bag.items] == [("E050", 1)]
    assert isinstance(bag, Bag)


def test_e051_use_cycle(tmp_path):
    (tmp_path / "a.wod").write_text("# A\nuse b\n", encoding="utf-8")
    (tmp_path / "b.wod").write_text("# B\nuse a\n", encoding="utf-8")

    from wodcraft.api import compile_file

    result = compile_file(tmp_path / "a.wod")

    assert [(d.code, d.span.line) for d in result.diagnostics if d.code == "E051"] == [("E051", 2)]
    assert result.ok is False


# --------------------------------------------------------------------------- warnings: W100–W104


def test_w100_implausible_distance():
    assert diagnose("For time\n  1 m Run\n  10 Burpee\n") == [("W100", 2)]


def test_w100_suggests_miles():
    diagnostic = only(compile_wod("For time\n  1 m Run\n  10 Burpee\n"))
    assert diagnostic.severity is Severity.WARNING
    assert diagnostic.suggestion == "did you mean miles ('1 mi')?"


def test_w100_is_not_raised_for_a_real_run():
    assert diagnose("For time\n  400 m Run\n") == []


def test_w100_is_not_raised_for_a_short_gymnastics_distance():
    # a 15 m handstand walk is normal: the warning only targets monostructural work
    assert diagnose("For time\n  15 m Handstand walk\n") == []


def test_w101_women_load_heavier_than_men():
    assert diagnose("For time\n  21 Thruster 30/43 kg\n") == [("W101", 2)]


def test_w101_is_not_raised_on_a_normal_dual():
    assert diagnose("For time\n  21 Thruster 43/30 kg\n") == []


def test_w102_emom_interval_overloaded():
    assert diagnose("EMOM 10\n  50 Burpee\n", estimate=True) == [("W102", 2)]


def test_w102_message_gives_the_work_and_the_interval():
    result = compile_wod("EMOM 10\n  50 Burpee\n", estimate=True)
    assert result.diagnostics[0].message.endswith("s interval.")
    assert result.diagnostics[0].suggestion == "lower the reps or lengthen the interval"


def test_w102_is_not_raised_on_a_sane_emom():
    assert diagnose("EMOM 10\n  5 Burpee\n", estimate=True) == []


def test_w102_checks_each_slot_separately():
    assert diagnose("EMOM 10\nOdd: 5 Burpee\nEven: 60 Air squat\n", estimate=True) == [("W102", 3)]


def test_w103_estimate_longer_than_the_cap():
    assert diagnose("For time, cap 1:00\n  100 Thruster 43/30 kg\n", estimate=True) == [("W103", 1)]


def test_w103_is_not_raised_when_the_cap_is_generous():
    assert diagnose("For time, cap 30:00\n  10 Burpee\n", estimate=True) == []


def test_w104_load_far_above_the_catalog_reference():
    assert diagnose("For time\n  10 Thruster 300 kg\n") == [("W104", 2)]


def test_w104_names_the_reference_load():
    diagnostic = only(compile_wod("For time\n  10 Thruster 300 kg\n"))
    assert diagnostic.message == "300 kg is far above the usual load for Thruster (43 kg)."


def test_w104_is_not_raised_on_a_heavy_but_plausible_load():
    assert diagnose("For time\n  10 Thruster 100 kg\n") == []


def test_warnings_do_not_make_compilation_fail():
    result = compile_wod("For time\n  1 m Run\n  21 Thruster 30/43 kg\n")
    assert result.ok is True
    assert [d.code for d in result.diagnostics] == ["W100", "W101"]


# --------------------------------------------------------------------------- the Diagnostic type


def test_severity_is_derived_from_the_code_prefix():
    assert Diagnostic("E001", "x", Span(1)).severity is Severity.ERROR
    assert Diagnostic("W100", "x", Span(1)).severity is Severity.WARNING
    assert Diagnostic("I200", "x", Span(1)).severity is Severity.INFO


def test_to_dict_carries_the_location_and_the_optional_fields():
    diagnostic = Diagnostic("E020", "Unknown movement.", Span(4, 6, 12, "a.wod"), "did you mean 'Burpee'?")
    assert diagnostic.to_dict() == {
        "code": "E020",
        "severity": "error",
        "message": "Unknown movement.",
        "line": 4,
        "col": 6,
        "end_col": 12,
        "file": "a.wod",
        "suggestion": "did you mean 'Burpee'?",
    }


def test_to_dict_omits_what_is_not_set():
    assert Diagnostic("W100", "x", Span(2, 3)).to_dict() == {
        "code": "W100",
        "severity": "warning",
        "message": "x",
        "line": 2,
        "col": 3,
    }


def test_format_underlines_the_offending_span():
    diagnostic = Diagnostic("E020", "Unknown movement 'Frobnicate'.", Span(2, 6, 16), "add it to the catalog")
    rendered = diagnostic.format(["AMRAP 10", "  10 Frobnicate"])
    assert rendered.splitlines() == [
        "2:6: error E020: Unknown movement 'Frobnicate'.",
        "      10 Frobnicate",
        "         ^^^^^^^^^^",
        "    help: add it to the catalog",
    ]


def test_format_without_source_lines_is_a_single_line():
    assert Diagnostic("E001", "boom", Span(3, 2)).format() == "3:2: error E001: boom"


def test_format_prefixes_the_file_when_there_is_one():
    assert Diagnostic("E001", "boom", Span(3, 2, file="a.wod")).format().startswith("a.wod:3:2:")


def test_the_bag_reports_errors_and_sorts_by_position():
    bag = DiagnosticBag()
    bag.add("W100", "second", Span(5, 1))
    bag.add("E001", "first", Span(2, 3))
    assert bag.has_errors is True
    assert [d.message for d in bag.sorted()] == ["first", "second"]


def test_a_bag_of_warnings_has_no_errors():
    bag = DiagnosticBag()
    bag.add("W100", "careful", Span(1, 1))
    assert bag.has_errors is False


def test_a_bag_can_absorb_another_bag():
    left, right = DiagnosticBag(), DiagnosticBag()
    right.add("E001", "x", Span(1))
    left.extend(right)
    left.extend([Diagnostic("W100", "y", Span(2))])
    assert [d.code for d in left.items] == ["E001", "W100"]


def test_span_to_dict_keeps_only_line_and_column():
    assert Span(7, 3, 9, "a.wod").to_dict() == {"line": 7, "col": 3}


def test_result_ok_is_false_as_soon_as_one_error_is_present():
    assert compile_wod("For time\n  10 Frobnicate\n").ok is False


def test_result_report_renders_every_diagnostic():
    report = compile_wod("For time\n  10 Frobnicate\n").report()
    assert "E016" in report and "E020" in report
