import pytest

try:
    import wodc_merged as wm
except Exception as e:  # pragma: no cover
    pytest.skip(f"wodc_merged unavailable: {e}", allow_module_level=True)


def collect_codes(issues):
    return {(i.get("level"), i.get("code")) for i in issues}


def test_emom_without_slots_triggers_E020():
    text = 'BLOCK EMOM 2:00 {\n  10 burpees;\n}\n'
    ast = wm.parse_wod_text(text)
    issues = wm.lint(ast)
    codes = collect_codes(issues)
    assert ("error", "E020") in codes


def test_rest_zero_triggers_E010():
    text = 'REST 0s\n'
    ast = wm.parse_wod_text(text)
    issues = wm.lint(ast)
    assert ("error", "E010") in collect_codes(issues)


def test_unknown_movement_triggers_W001():
    text = 'BLOCK FT {\n  10 foobar;\n}\n'
    ast = wm.parse_wod_text(text)
    issues = wm.lint(ast)
    assert ("warning", "W001") in collect_codes(issues)

