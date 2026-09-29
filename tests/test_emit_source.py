"""The canonical source form produced by ``wodc fmt``."""

from __future__ import annotations

import pytest

from conftest import compile_wod, parse, strip_source
from wodcraft.emit.source import format_source


def fmt(source: str) -> str:
    source_file, diags = parse(source)
    assert not diags.has_errors, [d.format() for d in diags.items]
    return format_source(source_file)


def meaning(source: str):
    """The compiled document with source spans removed — what formatting must preserve."""
    result = compile_wod(source)
    assert result.ok, result.report()
    return strip_source(result.documents)


def assert_round_trip(source: str) -> str:
    """Formatting is idempotent and meaning-preserving."""
    once = fmt(source)
    assert fmt(once) == once, "formatting is not idempotent"
    assert meaning(once) == meaning(source), "formatting changed the compiled document"
    return once


# --------------------------------------------------------------------------- canonical shapes


@pytest.mark.parametrize(
    ("written", "canonical"),
    [
        ("for time", "For time\n  10 Burpee\n"),
        ("FOR TIME", "For time\n  10 Burpee\n"),
        ("for time, cap 10", "For time, cap 10:00\n  10 Burpee\n"),
        ("amrap 12", "AMRAP 12:00\n  10 Burpee\n"),
        ("emom 10", "EMOM 10:00\n  10 Burpee\n"),
        ("e2mom 20", "E2MOM 20:00\n  10 Burpee\n"),
        ("every 3:00 x5", "Every 3:00 x 5\n  10 Burpee\n"),
        ("tabata", "Tabata\n  10 Burpee\n"),
        ("tabata 6", "Tabata 6\n  10 Burpee\n"),
        ("3 rounds", "3 rounds\n  10 Burpee\n"),
        ("3 rft", "3 rounds for time\n  10 Burpee\n"),
        ("max load", "Max load\n  10 Burpee\n"),
    ],
)
def test_format_lines_are_canonicalised(written, canonical):
    assert fmt(f"{written}\n  10 Burpee\n") == canonical


def test_indentation_is_two_spaces():
    assert fmt("3 rounds\n      10 Burpee\n") == "3 rounds\n  10 Burpee\n"


def test_units_are_separated_from_their_number():
    assert fmt("For time\n  400m Run\n") == "For time\n  400 m Run\n"


def test_a_percent_stays_glued_to_its_number():
    assert fmt("Max load\n  Back squat 5x5 @ 75%\n") == "Max load\n  Back squat 5x5 @ 75%\n"


def test_a_set_scheme_keeps_its_notation():
    assert fmt("Max load\n  Back squat 5X5\n") == "Max load\n  Back squat 5x5\n"
    assert fmt("Max load\n  Deadlift 5-5-3-3-1-1\n") == "Max load\n  Deadlift 5-5-3-3-1-1\n"


def test_rest_is_written_as_a_clock():
    assert fmt("3 rounds\n  10 Burpee\n  Rest 120 s\n") == "3 rounds\n  10 Burpee\n  Rest 2:00\n"


def test_a_short_rest_keeps_its_seconds():
    assert fmt("3 rounds\n  10 Burpee\n  Rest 30 s\n") == "3 rounds\n  10 Burpee\n  Rest 30 s\n"


def test_death_by_is_expanded_into_a_block():
    assert fmt("Death by Burpee\n") == "Death by\n  Burpee\n"


def test_rule_2_is_folded_into_a_single_format_line():
    assert fmt("For time, cap 10:00\n21-15-9\n  Thruster 43/30 kg\n  Pull-up\n") == (
        "21-15-9 for time, cap 10:00\n  Thruster 43/30 kg\n  Pull-up\n"
    )


def test_unindented_slots_are_indented_under_their_emom():
    assert fmt("EMOM 12\nOdd: 12/10 cal Row\nEven: 10 Burpee\n") == ("EMOM 12:00\n  Odd: 12/10 cal Row\n  Even: 10 Burpee\n")


def test_an_open_ladder_keeps_its_ellipsis():
    assert fmt("3-6-9 … for time\n  Burpee\n") == "3-6-9 ... for time\n  Burpee\n"


def test_level_blocks_are_separated_by_a_blank_line():
    assert fmt("For time\n  10 Pull-up\nScaled:\n  Pull-up -> Ring row\n") == ("For time\n  10 Pull-up\n\nScaled:\n  Pull-up -> Ring row\n")


def test_a_session_keeps_its_headings_and_meta():
    source = "# Day\ndate: 2026-09-23\n## Warm-up\n3 rounds\n  10 Air squat\n## Metcon\namrap 10\n  10 Burpee\n"
    assert fmt(source) == ("# Day\ndate: 2026-09-23\n\n## Warm-up\n3 rounds\n  10 Air squat\n\n## Metcon\nAMRAP 10:00\n  10 Burpee\n")


def test_documents_are_separated_by_a_blank_line():
    assert fmt("# A\nfor time\n  10 Burpee\n# B\namrap 5\n  10 Burpee\n") == (
        "# A\nFor time\n  10 Burpee\n\n# B\nAMRAP 5:00\n  10 Burpee\n"
    )


def test_a_free_text_modifier_is_requoted():
    assert fmt('AMRAP 10\n  10 Burpee ("chest to the floor")\n') == 'AMRAP 10:00\n  10 Burpee ("chest to the floor")\n'


def test_a_known_modifier_is_written_bare():
    assert fmt("AMRAP 10\n  10 Burpee (unbroken)\n") == "AMRAP 10:00\n  10 Burpee (unbroken)\n"


def test_bare_bw_stays_bare_and_a_multiple_keeps_its_at():
    assert fmt("For time\n  10 Bench press bw\n  10 Deadlift @ 1.5 bw\n") == ("For time\n  10 Bench press bw\n  10 Deadlift @ 1.5 bw\n")


def test_a_standalone_comment_line_is_kept():
    assert fmt("For time\n  // pace yourself\n  10 Burpee\n") == "For time\n  // pace yourself\n  10 Burpee\n"


def test_the_output_always_ends_with_a_single_newline():
    assert fmt("For time\n  10 Burpee\n\n\n").endswith("Burpee\n")
    assert not fmt("For time\n  10 Burpee\n").endswith("\n\n")


# --------------------------------------------------------------------------- round trips


@pytest.mark.parametrize(
    "source",
    [
        "For time\n  10 Burpee\n",
        "21-15-9 for time, cap 10:00\n  Thruster 95/65 lb\n  Pull-up\n",
        "3 rounds for time\n  400 m Run\n  21 Kettlebell swing 1.5/1 pood\n",
        "AMRAP 20:00\n  5 Pull-up\n  10 Push-up\n  15 Air squat\n",
        "EMOM 12:00\n  Odd: 12/10 cal Row\n  Even: 10 Burpee\n",
        "EMOM 15:00\n  Min 1: 10 Burpee\n  Min 2: 15 Air squat\n",
        "E3MOM 15:00\n  5 Power clean 61/43 kg\n",
        "Every 3:00 x 5\n  15/12 cal Row\n",
        "Tabata 6\n  max cal Row\n",
        "Death by\n  Burpee\n",
        "Max load\n  Back squat 5x5 @ 75%\n",
        "Max load\n  Deadlift 5-5-3-3-1-1 @ RPE 8\n",
        "3 rounds\n  AMRAP 4:00\n    10 Burpee\n  Rest 1:00\n",
        "For time\n  Buy-in: 1 mi Run\n  100 Pull-up\n  Cash-out: 1 mi Run\n",
        "AMRAP 20:00, teams of 2\n  20 Wall ball 20/14 lb\n",
        "units: lb\nFor time\n  21 Thruster 95\n",
        "# Day\ndate: 2026-09-23\n\n## Metcon\nAMRAP 10:00\n  10 Burpee\n",
        "10-9-8-7-6-5-4-3-2-1 for time\n  Deadlift @ 1.5 bw\n  Bench press bw\n",
        'AMRAP 10:00\n  10 Burpee ("lateral over the dumbbell")\n  10 Dumbbell snatch 22.5/15 kg (alternating)\n',
        "3-6-9 ... for time, cap 20:00\n  Burpee\n",
    ],
)
def test_canonical_sources_are_fixed_points(source):
    assert fmt(source) == source


@pytest.mark.parametrize(
    "source",
    [
        "for time, cap 10\n21-15-9\n  thruster 95/65 lb\n  pull-up\n",
        "emom 12\nOdd: 12/10 cal Row\nEven: 10 Burpee\n",
        "Death by Burpee\n",
        "amrap 5\n  10 burpee\n\namrap 5\n  10 air squat\n",
        "For time\n  10 Pull-up\nScaled:\n  Pull-up -> Ring row\n",
        "3 rounds\n      10 Burpee\n      Rest 60 s\n",
    ],
)
def test_formatting_is_idempotent_and_preserves_meaning(source):
    assert_round_trip(source)


def test_the_whole_standard_library_is_a_fixed_point(library_files):
    # `wodc fmt --check` must pass on every shipped workout.
    not_canonical = []
    for path in library_files:
        original = path.read_text(encoding="utf-8")
        if fmt(original) != original:
            not_canonical.append(path.name)
    assert not_canonical == []


def test_formatting_the_library_twice_changes_nothing(library_files):
    for path in library_files:
        once = fmt(path.read_text(encoding="utf-8"))
        assert fmt(once) == once, path.name


def test_formatting_the_library_preserves_every_compiled_document(library_files):
    for path in library_files:
        original = path.read_text(encoding="utf-8")
        assert meaning(fmt(original)) == meaning(original), path.name


def test_the_conformance_suite_is_meaning_preserving(conformance_dir):
    for wod in sorted(conformance_dir.glob("*.wod")):
        if (conformance_dir / f"{wod.stem}.diag").exists():
            continue  # the diagnostic cases are deliberately invalid
        original = wod.read_text(encoding="utf-8")
        once = fmt(original)
        assert fmt(once) == once, wod.name
        assert meaning(once) == meaning(original), wod.name


def test_a_single_line_foundations_block_survives_formatting():
    source = "For time\n  10 Pull-up\n\nFoundations:\n  Pull-up -> Ring row\n"

    once = fmt(source)

    assert compile_wod(once).ok, compile_wod(once).report()


def test_level_quantities_survive_formatting():
    from wodcraft.emit.source import format_source
    from wodcraft.syntax.parser import parse_source

    text = "For time\n  20 Pull-up\n  10 Burpee\n\nScaled:\n  Pull-up -> 2x Ring row\n  Burpee -> 15 Air squat\n"
    assert format_source(parse_source(text)[0]) == text
