import pytest

try:
    import wodc_merged as wm
except Exception as e:  # pragma: no cover
    pytest.skip(f"wodc_merged unavailable: {e}", allow_module_level=True)


def test_parse_minimal():
    text = 'WOD "Test"\nBLOCK FT {\n  10 wall_balls;\n}\n'
    ast = wm.parse_wod_text(text)
    assert isinstance(ast, dict)
    assert ast.get("meta", {}).get("title") == "Test"
    assert ast.get("program"), "program should not be empty"


def test_parse_invalid_raises():
    # Missing time for EMOM should raise a parse error
    text = 'WOD "X"\nBLOCK EMOM { }\n'
    with pytest.raises(Exception):
        wm.parse_wod_text(text)

