"""Whiteboard, Markdown and timeline renderings of a compiled document."""

from __future__ import annotations

import pytest

from conftest import compile_wod
from wodcraft.emit import board, markdown
from wodcraft.emit.timeline import render_timeline, timeline
from wodcraft.profile import Profile
from wodcraft.semantics.resolve import resolve


def document(source: str, estimate: bool = False) -> dict:
    result = compile_wod(source, estimate=estimate)
    assert result.ok, result.report()
    return result.document


# --------------------------------------------------------------------------- board


def test_a_workout_is_rendered_as_a_whiteboard():
    source = "# Fran\n21-15-9 for time, cap 10:00\n  Thruster 95/65 lb\n  Pull-up\n"

    rendered = board.render(document(source))

    assert rendered.splitlines() == [
        "FRAN",
        "21-15-9 for time · cap 10:00",
        "  Thruster .......................... 95/65 lb",
        "  Pull-up",
        "Score: time (capped: reps)",
    ]


def test_the_title_is_upper_cased():
    assert board.render(document("# Cindy\nAMRAP 20:00\n  5 Pull-up\n")).startswith("CINDY\n")


def test_a_movement_without_a_right_hand_side_has_no_dots():
    rendered = board.render(document("For time\n  100 Burpee\n"))
    assert "100 Burpee" in rendered
    assert "." not in rendered.split("\n")[1]


def test_loads_are_shown_as_written():
    rendered = board.render(document("For time\n  21 Kettlebell swing 1.5/1 pood\n"))
    assert "1.5/1 pood" in rendered


def test_heights_are_shown_as_written():
    assert "24/20 in" in board.render(document("AMRAP 10:00\n  10 Box jump 24/20 in\n"))


def test_a_percentage_is_shown_when_there_is_no_load():
    assert "75%" in board.render(document("Max load\n  Back squat 5x5 @ 75%\n"))


def test_an_rpe_is_shown():
    assert "RPE 8" in board.render(document("Max load\n  Deadlift 5x3 @ RPE 8\n"))


def test_modifiers_are_shown_in_parentheses():
    assert "(unbroken)" in board.render(document("AMRAP 10:00\n  10 Thruster 43 kg (unbroken)\n"))


def test_sets_are_shown_next_to_the_movement():
    assert "5x5" in board.render(document("Max load\n  Back squat 5x5 @ 75%\n"))


def test_a_set_ladder_is_shown_with_dashes():
    assert "5-5-3-3-1-1" in board.render(document("Max load\n  Deadlift 5-5-3-3-1-1 @ RPE 8\n"))


@pytest.mark.parametrize(
    ("source", "head"),
    [
        ("For time\n  10 Burpee\n", "For time"),
        ("AMRAP 12:00\n  10 Burpee\n", "AMRAP 12:00"),
        ("EMOM 10:00\n  10 Burpee\n", "EMOM 10:00"),
        ("E2MOM 20:00\n  10 Burpee\n", "E2MOM 20:00"),
        ("Every 3:00 x 5\n  10 Burpee\n", "Every 3:00 x 5"),
        ("Tabata\n  max Air squat\n", "Tabata"),
        ("Tabata 6\n  max Air squat\n", "Tabata 6"),
        ("Death by\n  Burpee\n", "Death by"),
        ("Max load\n  Back squat 5x5\n", "Max load"),
        ("3 rounds\n  10 Burpee\n", "3 rounds"),
        ("21-15-9\n  Burpee\n", "21-15-9"),
        ("3 rounds for time\n  10 Burpee\n", "3 rounds for time"),
    ],
)
def test_every_format_has_a_whiteboard_head(source, head):
    assert board.render(document(source)).splitlines()[0] == head


def test_labels_are_rendered_with_their_colon():
    rendered = board.render(document("For time\n  Buy-in: 1 mi Run\n  100 Pull-up\n  Cash-out: 1 mi Run\n"))
    assert "  Buy-in:" in rendered
    assert "  Cash-out:" in rendered


def test_slots_are_rendered_with_their_name():
    rendered = board.render(document("EMOM 12:00\n  Odd: 10 Burpee\n  Even: 10 Air squat\n"))
    assert "  Odd:" in rendered and "  Even:" in rendered


def test_min_slots_are_rendered_with_their_number():
    assert "  Min 2:" in board.render(document("EMOM 10:00\n  Min 1: 10 Burpee\n  Min 2: 10 Air squat\n"))


def test_a_team_size_is_shown_first():
    assert board.render(document("AMRAP 20:00, teams of 2\n  10 Burpee\n")).startswith("Teams of 2 · AMRAP 20:00")


def test_the_team_size_is_still_carried_by_the_document():
    assert document("AMRAP 20:00, teams of 2\n  10 Burpee\n")["team"] == {"size": 2}


def test_a_used_workout_is_credited():
    assert "[Fran]" in board.render(document("use girls/fran\n"))


def test_rest_is_rendered_as_a_clock():
    assert "Rest 1:00" in board.render(document("3 rounds\n  10 Burpee\n  Rest 1:00\n"))


def test_the_vest_notes_and_stimulus_are_listed():
    source = "vest: 20/14 lb\nnote: partition freely\nstimulus: long grind\nFor time\n  100 Burpee\n"
    rendered = board.render(document(source))
    assert "Vest: 20/14 lb" in rendered
    assert "Note: partition freely" in rendered
    assert "Stimulus: long grind" in rendered


def test_a_workout_without_a_score_says_nothing_about_it():
    assert "Score:" not in board.render(document("3 rounds\n  10 Burpee\n"))


def test_the_estimate_is_shown_when_present():
    rendered = board.render(document("For time\n  100 Burpee\n", estimate=True))
    assert "Estimate: " in rendered


def test_a_resolved_workout_shows_its_profile_stamp():
    resolved = resolve(document("For time\n  21 Thruster 43/30 kg\n"), Profile("women", "rx", "kg"))
    rendered = board.render(resolved)
    assert "[women · rx · kg]" in rendered
    assert "30 kg" in rendered


def test_a_session_lists_its_sections():
    source = "# Tuesday\ndate: 2026-09-23\ntime: 18:00\n## Warm-up\n3 rounds\n  10 Air squat\n## Metcon\nAMRAP 10:00\n  10 Burpee\n"

    rendered = board.render(document(source))

    lines = rendered.splitlines()
    assert lines[0] == "TUESDAY"
    assert lines[1] == "2026-09-23 · 18:00"
    assert "WARM-UP" in lines
    assert "METCON" in lines


# --------------------------------------------------------------------------- markdown


def test_markdown_wraps_the_board_in_a_fenced_block():
    rendered = markdown.to_markdown(document("# Fran\n21-15-9 for time\n  Thruster 95/65 lb\n  Pull-up\n"))
    assert rendered.startswith("# Fran\n\n```\n")
    assert "21-15-9 for time" in rendered
    assert "```\n" in rendered


def test_markdown_names_the_score():
    assert "**Score** — time" in markdown.to_markdown(document("For time\n  100 Burpee\n"))


def test_markdown_omits_a_none_score():
    assert "**Score**" not in markdown.to_markdown(document("3 rounds\n  10 Burpee\n"))


def test_markdown_quotes_the_stimulus_and_italicises_the_notes():
    source = "stimulus: long grind\nnote: pace it\nFor time\n  100 Burpee\n"
    rendered = markdown.to_markdown(document(source))
    assert "> long grind" in rendered
    assert "*pace it*" in rendered


def test_markdown_shows_the_estimate():
    assert "**Estimate** —" in markdown.to_markdown(document("For time\n  100 Burpee\n", estimate=True))


def test_markdown_gives_an_untitled_workout_a_default_heading():
    assert markdown.to_markdown(document("For time\n  10 Burpee\n")).startswith("# Workout\n")


def test_markdown_renders_a_session_with_h2_sections():
    source = "# Day\ndate: 2026-09-23\n## Warm-up\n3 rounds\n  10 Air squat\n## Metcon\nAMRAP 10:00\n  10 Burpee\n"

    rendered = markdown.to_markdown(document(source))

    assert rendered.startswith("# Day\n\n*2026-09-23*")
    assert "## Warm-up" in rendered
    assert "## Metcon" in rendered
    assert rendered.endswith("\n")


# --------------------------------------------------------------------------- timeline


def test_an_amrap_is_one_segment_of_its_full_duration():
    (segment,) = timeline(document("AMRAP 12:00\n  10 Burpee\n"))
    assert segment["at_s"] == 0
    assert segment["duration_s"] == 720.0
    assert segment["kind"] == "work"
    assert segment["label"].startswith("AMRAP 12:00: ")
    assert "10 Burpee" in segment["label"]


def test_an_emom_is_expanded_into_one_segment_per_minute():
    segments = timeline(document("EMOM 5:00\n  10 Burpee\n"))
    assert len(segments) == 5
    assert [s["at_s"] for s in segments] == [0.0, 60.0, 120.0, 180.0, 240.0]
    assert all(s["duration_s"] == 60 and s["kind"] == "interval" for s in segments)
    assert segments[0]["label"].startswith("EMOM 5:00 · 1/5: ")


def test_odd_and_even_slots_alternate_along_the_timeline():
    segments = timeline(document("EMOM 4:00\n  Odd: 10 Burpee\n  Even: 10 Air squat\n"))
    assert [s["label"].split(": ", 1)[1] for s in segments] == ["10 Burpee", "10 Air squat", "10 Burpee", "10 Air squat"]


def test_min_n_slots_cycle_on_the_highest_number():
    segments = timeline(document("EMOM 6:00\n  Min 1: 10 Burpee\n  Min 2: 10 Air squat\n  Min 3: 10 Sit-up\n"))
    labels = [s["label"].split(": ", 1)[1] for s in segments]
    assert labels == ["10 Burpee", "10 Air squat", "10 Sit-up"] * 2


def test_an_enmom_uses_its_own_interval():
    segments = timeline(document("E2MOM 10:00\n  10 Burpee\n"))
    assert len(segments) == 5
    assert segments[1]["at_s"] == 120.0


def test_every_uses_its_interval_and_count():
    segments = timeline(document("Every 3:00 x 4\n  10 Burpee\n"))
    assert len(segments) == 4
    assert [s["duration_s"] for s in segments] == [180.0] * 4


def test_an_untimed_wrapper_collapses_into_one_segment():
    # An untimed "N rounds" has no clock of its own, so the timeline shows its content
    # as a single open-ended segment rather than expanding each round.
    segments = timeline(document("3 rounds\n  AMRAP 2:00\n    10 Burpee\n  Rest 1:00\n", estimate=True))
    assert len(segments) == 1
    assert "AMRAP 2:00" in segments[0]["label"]
    assert "Rest 1:00" in segments[0]["label"]


def test_a_rest_block_renders_as_a_rest_segment():
    from wodcraft.emit.timeline import _block

    assert _block({"type": "rest", "seconds": 90.0}, {}) == [{"duration_s": 90.0, "label": "Rest", "kind": "rest"}]


def test_a_capped_for_time_lasts_its_cap():
    (segment,) = timeline(document("For time, cap 10:00\n  100 Burpee\n"))
    assert segment["duration_s"] == 600.0
    assert segment.get("open_ended") is False


def test_an_uncapped_for_time_is_open_ended_and_uses_the_estimate():
    (segment,) = timeline(document("For time\n  100 Burpee\n", estimate=True))
    assert segment["open_ended"] is True
    assert segment["duration_s"] > 0


def test_a_session_timeline_chains_its_sections():
    source = "# Day\n## A\nAMRAP 5:00\n  10 Burpee\n## B\nAMRAP 10:00\n  10 Air squat\n"

    segments = timeline(document(source))

    assert [s["section"] for s in segments] == ["A", "B"]
    assert [s["at_s"] for s in segments] == [0.0, 300.0]


def test_the_rendered_timeline_is_a_table_ending_with_a_total():
    rendered = render_timeline(timeline(document("EMOM 3:00\n  10 Burpee\n")))
    lines = rendered.splitlines()
    assert len(lines) == 4
    assert lines[0].startswith("    0:00")
    assert lines[-1].endswith("total")
    assert "3:00" in lines[-1]


def test_an_open_ended_segment_is_marked_with_a_tilde():
    rendered = render_timeline(timeline(document("For time\n  100 Burpee\n", estimate=True)))
    assert "~" in rendered


def test_a_zero_length_segment_is_shown_as_a_dash():
    rendered = render_timeline([{"at_s": 0, "duration_s": 0, "label": "x"}])
    assert "—" in rendered


def test_the_french_board_says_aller_retour_and_ou():
    from conftest import compile_wod
    from wodcraft.emit import board

    document = compile_wod("For time, there and back\n  10 Ring row | Scap pull\n  5 Burpee\n").document
    french = board.render(document, lang="fr")
    assert "For time · aller-retour" in french
    assert "10 Tirage aux anneaux ou 10 Traction scapulaire" in french
    assert "there and back" in board.render(document)
