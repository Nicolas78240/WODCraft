import pytest

try:
    import wodc_merged as wm
except Exception as e:  # pragma: no cover
    pytest.skip(f"wodc_merged unavailable: {e}", allow_module_level=True)


def test_emom_two_minutes_rotates_slots():
    text = 'BLOCK EMOM 2:00 {\n  1: 10 wall_balls;\n  2: 8 box_jumps;\n}\n'
    ast = wm.parse_wod_text(text)
    events = wm.build_timeline(ast)
    slots = [e for e in events if e.get("type") == "NEXT_SLOT"]
    assert len(slots) == 2
    assert slots[0]["slot"] == 1
    assert slots[1]["slot"] == 2


def test_amrap_end_time_matches_duration():
    text = 'BLOCK AMRAP 1:00 {\n  10 burpees;\n}\n'
    ast = wm.parse_wod_text(text)
    events = wm.build_timeline(ast)
    end = [e for e in events if e.get("type") == "END_BLOCK"][-1]
    assert end["t"] == 60

