"""Athlete resolution: level, category, units, percentages (SPEC §14)."""

from __future__ import annotations

import pytest

from conftest import compile_wod
from wodcraft.profile import LEVEL_ORDER, Profile
from wodcraft.semantics.resolve import resolve

FRAN = "21-15-9 for time\n  Thruster 95/65 lb\n  Pull-up\n\nScaled:\n  Thruster 65/45 lb\n  Pull-up -> Jumping pull-up\n"


def compiled(source: str = FRAN) -> dict:
    result = compile_wod(source)
    assert result.ok, result.report()
    return result.document


def resolved_items(profile: Profile, source: str = FRAN) -> list[dict]:
    return resolve(compiled(source), profile)["blocks"][0]["items"]


# --------------------------------------------------------------------------- profile


def test_profile_defaults():
    profile = Profile()
    assert (profile.category, profile.level, profile.units) == ("men", "rx", "kg")
    assert profile.one_rm == {}
    assert profile.bodyweight_kg is None


def test_profile_loads_from_toml(tmp_path):
    path = tmp_path / "athlete.toml"
    path.write_text(
        'name = "Ada"\ncategory = "Women"\nlevel = "Scaled"\nunits = "LB"\nbodyweight_kg = 62.0\n\n[1rm]\nBack_squat = 95\n',
        encoding="utf-8",
    )

    profile = Profile.load(path)

    assert (profile.name, profile.category, profile.level, profile.units) == ("Ada", "women", "scaled", "lb")
    assert profile.bodyweight_kg == 62.0
    assert profile.one_rm == {"back_squat": 95.0}


def test_profile_accepts_the_one_rm_spelling(tmp_path):
    path = tmp_path / "a.toml"
    path.write_text("[one_rm]\ndeadlift = 180\n", encoding="utf-8")
    assert Profile.load(path).one_rm == {"deadlift": 180.0}


def test_profile_discover_walks_up_the_directories(tmp_path, monkeypatch):
    (tmp_path / "athlete.toml").write_text('category = "women"\n', encoding="utf-8")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))

    profile = Profile.discover(deep)

    assert profile is not None
    assert profile.category == "women"


def test_profile_discover_finds_the_dot_directory(tmp_path):
    (tmp_path / ".wodcraft").mkdir()
    (tmp_path / ".wodcraft" / "athlete.toml").write_text('units = "lb"\n', encoding="utf-8")
    assert Profile.discover(tmp_path).units == "lb"


def test_profile_discover_returns_none_when_there_is_nothing(workdir, monkeypatch):
    monkeypatch.setattr(Profile, "DEFAULT_FILES", ("athlete.toml",), raising=False)
    assert Profile.discover(workdir) is None


def test_level_order_runs_from_hardest_to_easiest():
    assert LEVEL_ORDER == ["rx", "intermediate", "scaled", "foundations"]


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("rx", ["rx", "intermediate", "scaled", "foundations"]),
        ("intermediate", ["intermediate", "scaled", "foundations", "rx"]),
        ("scaled", ["scaled", "foundations", "intermediate", "rx"]),
        ("foundations", ["foundations", "scaled", "intermediate", "rx"]),
    ],
)
def test_levels_to_try(level, expected):
    assert Profile(level=level).levels_to_try() == expected


def test_an_unknown_level_falls_straight_back_to_rx():
    assert Profile(level="elite").levels_to_try() == ["elite", "rx"]


# --------------------------------------------------------------------------- category


def test_resolving_for_a_man_picks_the_men_value():
    (thruster, _) = resolved_items(Profile("men", "rx", "kg"))
    assert thruster["load"] == {"value": 43, "unit": "kg", "kg": 43}


def test_resolving_for_a_woman_picks_the_women_value():
    (thruster, _) = resolved_items(Profile("women", "rx", "kg"))
    assert thruster["load"] == {"value": 30, "unit": "kg", "kg": 30}


def test_resolving_flattens_a_dual_quantity():
    source = "AMRAP 10:00\n  20/16 cal Row\n"
    (row,) = resolved_items(Profile("women"), source)
    assert row["quantity"]["cal"] == 16


def test_resolving_flattens_a_dual_height():
    source = "AMRAP 10:00\n  10 Box jump 24/20 in\n"
    (box,) = resolved_items(Profile("women", units="kg"), source)
    assert box["height"] == {"value": 50, "unit": "cm", "cm": 50}


# --------------------------------------------------------------------------- units


def test_imperial_units_report_the_pound_value():
    (thruster, _) = resolved_items(Profile("men", "rx", "lb"))
    assert thruster["load"] == {"value": 95, "unit": "lb", "kg": 43}


def test_imperial_units_report_heights_in_inches():
    source = "AMRAP 10:00\n  10 Box jump 24/20 in\n"
    (box,) = resolved_items(Profile("men", units="lb"), source)
    assert box["height"] == {"value": 24, "unit": "in", "cm": 60}


def test_the_resolved_stamp_records_the_profile():
    document = resolve(compiled(), Profile("women", "scaled", "lb"))
    assert document["resolved"] == {"category": "women", "level": "scaled", "units": "lb"}


# --------------------------------------------------------------------------- levels (§9, §14)


def test_a_scaled_athlete_gets_the_scaled_loads_and_substitutions():
    thruster, pull_up = resolved_items(Profile("men", "scaled", "kg"))
    assert thruster["load"]["value"] == 30
    assert (pull_up["movement"], pull_up["name"]) == ("jumping_pull_up", "Jumping pull-up")


def test_an_rx_athlete_keeps_the_rx_work():
    thruster, pull_up = resolved_items(Profile("men", "rx", "kg"))
    assert thruster["load"]["value"] == 43
    assert pull_up["movement"] == "pull_up"


def test_the_levels_key_is_consumed_by_resolution():
    document = resolve(compiled(), Profile("men", "scaled", "kg"))
    assert "levels" not in document


def test_a_missing_level_falls_back_to_the_closest_one():
    # Fran only ships "Scaled:", so a Foundations athlete lands on it.
    document = resolve(compiled(), Profile("men", "foundations", "kg"))
    assert document["resolved"]["level"] == "scaled"
    assert document["blocks"][0]["items"][0]["load"]["value"] == 30


def test_an_intermediate_athlete_prefers_an_intermediate_block():
    source = "AMRAP 12:00\n  10 Box jump 24/20 in\n\nIntermediate:\n  Box jump 20/16 in\n\nScaled:\n  Box jump -> Step-up 20/16 in\n"
    (box,) = resolved_items(Profile("men", "intermediate", "kg"), source)
    assert box["movement"] == "box_jump"
    assert box["height"]["value"] == 50


def test_a_level_absent_from_the_workout_ends_on_rx():
    source = "AMRAP 12:00\n  10 Box jump 24/20 in\n"
    document = resolve(compiled(source), Profile("men", "scaled", "kg"))
    assert document["resolved"]["level"] == "rx"


def test_a_replacement_drops_the_load_of_the_replaced_movement():
    source = "For time\n  10 Thruster 43/30 kg\n\nScaled:\n  Thruster -> Air squat\n"
    (movement,) = resolved_items(Profile("men", "scaled", "kg"), source)
    assert movement["movement"] == "air_squat"
    assert "load" not in movement


def test_a_level_can_drop_the_vest():
    source = "vest: 20/14 lb\nFor time\n  100 Burpee\n\nScaled:\n  vest: none\n"
    document = resolve(compiled(source), Profile("men", "scaled", "kg"))
    assert "vest" not in document["meta"]


def test_a_level_can_change_the_cap():
    source = "cap: 20:00\nFor time\n  100 Burpee\n\nScaled:\n  cap: 25:00\n"
    document = resolve(compiled(source), Profile("men", "scaled", "kg"))
    assert document["meta"]["cap_s"] == 1500.0


def test_a_selector_targets_one_occurrence_of_a_movement():
    source = (
        "For time, cap 9:00\n  21-15-9\n    Deadlift 102/70 kg\n    Handstand push-up\n"
        "  21-15-9\n    Deadlift 143/93 kg\n    15 m Handstand walk\n\n"
        "Scaled:\n  Deadlift 143/93 kg -> Deadlift 102/70 kg\n"
    )
    document = resolve(compiled(source), Profile("men", "scaled", "kg"))
    ladders = document["blocks"][0]["items"]
    assert ladders[0]["items"][0]["load"]["value"] == 102
    assert ladders[1]["items"][0]["load"]["value"] == 102


# --------------------------------------------------------------------------- percentages


def test_a_percentage_becomes_a_load_rounded_to_the_plates():
    source = "Max load\n  Back squat 5x5 @ 75%\n"
    profile = Profile("men", "rx", "kg", one_rm={"back_squat": 142.0})

    (squat,) = resolved_items(profile, source)

    # 142 x 0.75 = 106.5 -> nearest 2.5 kg = 107.5
    assert squat["load"] == {"value": 107.5, "unit": "kg", "kg": 107.5}


def test_a_percentage_in_pounds_rounds_to_five_pound_plates():
    source = "Max load\n  Back squat 5x5 @ 75%\n"
    profile = Profile("men", "rx", "lb", one_rm={"back_squat": 142.0})

    (squat,) = resolved_items(profile, source)

    assert squat["load"]["unit"] == "lb"
    assert squat["load"]["value"] % 5 == 0
    assert squat["load"]["value"] == 235


def test_a_percentage_of_another_lift_uses_that_lift_s_one_rm():
    source = "Max load\n  Front squat 3x3 @ 70% Back squat\n"
    profile = Profile("men", "rx", "kg", one_rm={"back_squat": 100.0, "front_squat": 80.0})

    (squat,) = resolved_items(profile, source)

    assert squat["load"]["value"] == 70


def test_a_percentage_without_a_one_rm_stays_a_percentage():
    source = "Max load\n  Back squat 5x5 @ 75%\n"
    (squat,) = resolved_items(Profile("men", "rx", "kg"), source)
    assert "load" not in squat
    assert squat["percent"] == {"value": 75, "of": "back_squat"}


def test_a_bodyweight_multiple_becomes_a_load():
    source = "For time\n  10 Deadlift @ 1.5 bw\n"
    profile = Profile("men", "rx", "kg", bodyweight_kg=80.0)

    (deadlift,) = resolved_items(profile, source)

    assert deadlift["load"] == {"value": 120, "unit": "kg", "kg": 120}


def test_a_bodyweight_multiple_without_a_bodyweight_is_left_alone():
    source = "For time\n  10 Deadlift @ 1.5 bw\n"
    (deadlift,) = resolved_items(Profile("men", "rx", "kg"), source)
    assert "load" not in deadlift
    assert deadlift["bodyweight"] == 1.5


# --------------------------------------------------------------------------- sessions


def test_resolving_a_session_resolves_every_section():
    source = "# Day\n## Metcon\nFor time\n  21 Thruster 43/30 kg\n## Extra\nAMRAP 5:00\n  10 Wall ball 9/6 kg\n"
    document = resolve(compiled(source), Profile("women", "rx", "kg"))
    sections = document["sections"]
    assert sections[0]["workout"]["blocks"][0]["items"][0]["load"]["value"] == 30
    assert sections[1]["workout"]["blocks"][0]["items"][0]["load"]["value"] == 6


def test_resolution_does_not_mutate_the_compiled_document():
    document = compiled()
    resolve(document, Profile("women", "scaled", "lb"))
    assert document["blocks"][0]["items"][0]["load"]["kg"] == {"men": 43, "women": 30}
    assert "resolved" not in document
