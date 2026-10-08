"""WODCraft 1.2: attempts, the total, and a cap for the whole workout (SPEC §5, §6.1, §12)."""

from __future__ import annotations

from conftest import coded_lines, compile_wod
from test_emit_source import assert_round_trip
from wodcraft.emit import board, markdown
from wodcraft.emit.timeline import render_timeline, render_timer, timeline, timer_cap, timer_caps

TOTAL = """# CrossFit Total
score: load, total
cap: 30:00
Max load, 3 attempts
  1 Back squat
  Rest 2:00
Rest 3:00
Max load, 3 attempts
  1 Shoulder press
  Rest 2:00
Rest 3:00
Max load, 3 attempts
  1 Deadlift
  Rest 2:00
"""

PER_LIFT = TOTAL.replace("cap: 30:00\n", "").replace("3 attempts", "3 attempts, cap 8:00")


def document(source: str, estimate: bool = True) -> dict:
    result = compile_wod(source, estimate=estimate)
    assert result.ok, result.report()
    assert result.document is not None
    return result.document


# --------------------------------------------------------------------------- attempts


def test_attempts_go_on_the_max_load_block():
    blocks = document(TOTAL)["blocks"]
    assert [(b["type"], b.get("attempts")) for b in blocks] == [
        ("max_load", 3),
        ("rest", None),
        ("max_load", 3),
        ("rest", None),
        ("max_load", 3),
    ]


def test_essais_is_the_french_for_attempts_and_one_attempt_is_singular():
    blocks = document("Max load, 3 essais\n  1 Deadlift\n")["blocks"]
    assert blocks[0]["attempts"] == 3
    assert document("Max load, 1 attempt\n  1 Deadlift\n")["blocks"][0]["attempts"] == 1


def test_attempts_elsewhere_than_max_load_is_e014_and_zero_is_e035():
    assert coded_lines(compile_wod("For time, 3 attempts\n  10 Burpee\n")) == [("E014", 1)]
    assert coded_lines(compile_wod("Max load, 0 attempts\n  1 Deadlift\n")) == [("E035", 1)]
    assert coded_lines(compile_wod("Max load, 2.5 attempts\n  1 Deadlift\n"))[0] == ("E035", 1)


def test_the_formatter_writes_attempts_and_the_score_back_in_english():
    once = assert_round_trip("score: charge, total\nMax load, 3 essais, cap 8:00\n  1 Deadlift\nMax load, 1 essai\n  1 Back squat\n")
    assert once == "score: load, total\nMax load, 3 attempts, cap 8:00\n  1 Deadlift\nMax load, 1 attempt\n  1 Back squat\n"
    assert assert_round_trip("score: charge\nMax load\n  1 Deadlift\n").startswith("score: load\n")


# --------------------------------------------------------------------------- the total


def test_a_total_over_several_lifts_is_a_multi_score_that_adds_up():
    assert document(TOTAL)["score"] == {
        "type": "multi",
        "aggregate": "sum",
        "unit": "load",
        "parts": [{"type": "load", "block": 0}, {"type": "load", "block": 2}, {"type": "load", "block": 4}],
    }


def test_a_total_over_one_block_adds_up_its_efforts():
    lynne = document("score: reps, total\n5 rounds\n  max Bench press bw\n  max Pull-up\n")
    assert lynne["score"] == {"type": "reps", "aggregate": "sum"}


def test_without_total_a_declared_score_is_still_the_first_block_s():
    score = document("score: load\nMax load\n  1 Back squat\nMax load\n  1 Deadlift\n")["score"]
    assert score == {"type": "load"}


def test_score_modifiers_are_checked():
    assert coded_lines(compile_wod("score: load, best\nMax load\n  1 Deadlift\n")) == [("E013", 1)]
    assert coded_lines(compile_wod("score: none, total\nFor time\n  10 Burpee\n")) == [("E013", 1)]
    assert coded_lines(compile_wod("score: load, total\nMax load\n  1 Deadlift\nAMRAP 6:00\n  10 Burpee\n")) == [("E036", 4)]


# --------------------------------------------------------------------------- caps


def test_a_workout_cap_over_several_blocks_belongs_to_the_workout():
    total = document(TOTAL)
    assert total["cap_s"] == 1800
    assert all("cap_s" not in block for block in total["blocks"])


def test_a_workout_cap_over_one_block_is_still_that_block_s():
    burpees = document("cap: 12:00\nFor time\n  100 Burpee\n")
    assert burpees["blocks"][0]["cap_s"] == 720
    assert "cap_s" not in burpees
    assert burpees["wodcraft"] == "1.0"


def test_a_workout_cap_and_block_caps_together_is_e037_on_the_cap_line():
    result = compile_wod("score: load, total\ncap: 30:00\nMax load, cap 8:00\n  1 Back squat\nMax load\n  1 Deadlift\n")
    assert coded_lines(result) == [("E037", 2)]
    assert result.diagnostics[0].suggestion == "keep either 'cap:' for the whole workout, or a cap on each block"
    assert coded_lines(compile_wod("cap: 10:00\nFor time, cap 12:00\n  100 Burpee\n")) == [("E037", 1)]


# --------------------------------------------------------------------------- versions


def test_a_document_is_stamped_1_2_only_when_it_uses_a_1_2_construct():
    assert document(TOTAL)["wodcraft"] == "1.2"
    assert document("Max load, 3 attempts\n  1 Deadlift\n")["wodcraft"] == "1.2"
    assert document("score: reps, total\n5 rounds\n  max Pull-up\n")["wodcraft"] == "1.2"
    assert document("cap: 20:00\nFor time\n  10 Burpee\nAMRAP 5:00\n  5 Burpee\n")["wodcraft"] == "1.2"
    assert document("Max load\n  1 Deadlift\n")["wodcraft"] == "1.0"
    assert document("For time\n  10 Ring row | Scap pull\n")["wodcraft"] == "1.1"


def test_a_session_takes_the_newest_version_of_its_sections():
    session = document(
        "# S\n## A\nFor time\n  10 Ring row | Scap pull\n## B\nMax load, 3 attempts\n  1 Deadlift\n## C\nFor time\n  5 Burpee\n"
    )
    assert [s["workout"]["wodcraft"] for s in session["sections"]] == ["1.1", "1.2", "1.0"]
    assert session["wodcraft"] == "1.2"


# --------------------------------------------------------------------------- estimates


def test_a_build_up_takes_minutes_not_seconds():
    estimate = document(TOTAL)["estimate"]
    assert estimate["capped_s"] == 1800
    assert 15 * 60 <= estimate["min_s"] <= 20 * 60
    assert 25 * 60 <= estimate["max_s"] <= 35 * 60


def test_the_caps_of_the_lifts_add_up_with_the_rest_between_them():
    assert document(PER_LIFT)["estimate"]["capped_s"] == 8 * 60 * 3 + 3 * 60 * 2


def test_a_single_capped_block_among_others_keeps_its_cap():
    estimate = document("For time, cap 10:00\n  50 Burpee\nBack squat 5x5 @ 75%\n")["estimate"]
    assert estimate["capped_s"] == 600


def test_three_attempts_with_a_rest_take_two_rests():
    from wodcraft.catalog import load_catalog
    from wodcraft.semantics.estimate import ATTEMPT_SECONDS, rest_seconds

    block = document("Max load, 3 attempts\n  1 Deadlift\n  Rest 2:00\n")["blocks"][0]
    assert rest_seconds(block) == 240
    from wodcraft.semantics.estimate import block_seconds

    assert block_seconds(block, load_catalog()) == 3 * ATTEMPT_SECONDS + 240


# --------------------------------------------------------------------------- views


def test_the_board_shows_the_cap_the_attempts_and_the_total():
    rendered = board.render(document(TOTAL))
    assert rendered.splitlines()[:5] == [
        "CROSSFIT TOTAL",
        "Cap: 30:00",
        "Max load · 3 attempts",
        "  1 Back squat",
        "  Rest 2:00 between attempts",
    ]
    assert "Score: total load (best attempt of each lift)" in rendered


def test_the_french_board_says_charge_max_essais_and_total_des_charges():
    rendered = board.render(document(TOTAL), lang="fr")
    assert rendered.splitlines()[:6] == [
        "CROSSFIT TOTAL",
        "Cap : 30:00",
        "Charge max · 3 essais",
        "  1 Squat arrière",
        "  Repos 2:00 entre les essais",
        "Repos 3:00",
    ]
    assert "Score : total des charges (meilleur essai de chaque barre)" in rendered
    assert "Durée : " in rendered


def test_the_french_board_translates_the_lines_under_the_workout():
    rendered = board.render(document("score: reps, total\nnote: rest as needed\n5 rounds\n  max Pull-up\n"), lang="fr")
    assert "Score : total des répétitions" in rendered
    assert "Note : rest as needed" in rendered


def test_markdown_shows_the_cap_and_the_total():
    rendered = markdown.to_markdown(document(TOTAL))
    assert "**Cap** — 30:00" in rendered
    assert "**Score** — total load (best attempt of each lift)" in rendered


def test_the_timer_gives_each_lift_its_own_window():
    segments = timeline(document(PER_LIFT))
    assert [(s["at_s"], s["duration_s"]) for s in segments] == [(0, 480), (480, 180), (660, 480), (1140, 180), (1320, 480)]
    assert segments[0]["label"] == "Max load · 3 attempts · cap 8:00: 1 Back squat + Rest 2:00 between attempts"
    assert render_timeline(segments).splitlines()[-1].split() == ["30:00", "total"]


def test_the_timer_estimates_a_lift_without_a_cap_on_its_own():
    segments = timeline(document(TOTAL))
    lifts = [s for s in segments if s["kind"] == "work"]
    assert len({s["duration_s"] for s in lifts}) == 1
    assert all(s["open_ended"] for s in lifts)
    assert sum(s["duration_s"] for s in segments) < 30 * 60


def test_the_timer_shows_when_the_workout_cap_stops_the_clock():
    lines = render_timer(document(TOTAL)).splitlines()
    assert lines[-2:] == ["   30:00          cap: the clock stops", "           25:12  total"]
    assert timer_cap(document(TOTAL)) == 1800


def test_the_cap_line_takes_its_place_in_time():
    short = document("cap: 12:00\nEMOM 10\n  10 Burpee\nRest 2:00\nAMRAP 6:00\n  10 Wall ball 9/6 kg\n")
    lines = render_timer(short).splitlines()
    assert lines[-4:] == [
        "   10:00    2:00  Rest",
        "   12:00          cap: the clock stops",
        "   12:00    6:00  AMRAP 6:00: 10 Wall ball 9/6 kg",
        "           18:00  total",
    ]


def test_block_caps_add_no_cap_line():
    # a cap per block, or a cap on a single block, is already the length of its segment
    for source in (PER_LIFT, "cap: 12:00\nFor time\n  100 Burpee\n"):
        workout = document(source)
        assert timer_cap(workout) is None
        assert render_timer(workout) == render_timeline(timeline(workout))
        assert "cap: the clock stops" not in render_timer(workout)


def test_a_session_has_no_cap_of_its_own():
    session = document("# S\n## A\ncap: 20:00\nFor time\n  10 Burpee\nAMRAP 5:00\n  5 Burpee\n")
    assert timer_cap(session) is None
    assert timer_caps(session) == [1200]


SESSION = """# Session

## Warm-up
cap: 12:00
EMOM 10:00
  10 Burpee
Rest 2:00
AMRAP 6:00
  10 Wall ball 9/6 kg

## Strength
Back squat 5x5 100/70 kg

## Metcon
cap: 20:00
For time
  50 Wall ball 9/6 kg
Rest 2:00
AMRAP 6:00
  10 Burpee
"""


def test_the_session_timer_shows_each_section_cap_at_its_place_in_the_session():
    # the warm-up's cap in the first section, none in the strength, the metcon's 29:30 + 20:00
    session = document(SESSION)
    assert timer_caps(session) == [720, 2970]
    lines = render_timer(session).splitlines()
    assert lines[10:] == [
        "   10:00    2:00  Rest",
        "   12:00          cap: the clock stops",
        "   12:00    6:00  AMRAP 6:00: 10 Wall ball 9/6 kg",
        "   18:00   11:30  Back squat ............... 5x5 100/70 kg",
        "   29:30   14:44~ For time: 50 Wall ball 9/6 kg",
        "   44:14    2:00  Rest",
        "   46:14    6:00  AMRAP 6:00: 10 Burpee",
        "   49:30          cap: the clock stops",
        "           52:14  total",
    ]


def test_a_cap_in_a_later_section_counts_from_that_section_start():
    session = document("# S\n## A\nAMRAP 5:00\n  5 Burpee\n## B\ncap: 10:00\nEMOM 4:00\n  5 Burpee\nAMRAP 8:00\n  5 Burpee\n")
    assert timer_caps(session) == [900]
    assert render_timer(session).splitlines()[-4:] == [
        "    8:00    1:00  EMOM 4:00 · 4/4: 5 Burpee",
        "    9:00    8:00  AMRAP 8:00: 5 Burpee",
        "   15:00          cap: the clock stops",
        "           17:00  total",
    ]


def test_block_caps_in_a_session_add_no_cap_line():
    single = "# S\n## A\ncap: 12:00\nFor time\n  100 Burpee\n## B\nAMRAP 5:00\n  5 Burpee\n"
    per_block = "# S\n## A\nAMRAP 5:00\n  5 Burpee\n## B\n" + PER_LIFT.split("\n", 1)[1]
    for source in (single, per_block):
        session = document(source)
        assert timer_caps(session) == []
        assert render_timer(session) == render_timeline(timeline(session))
