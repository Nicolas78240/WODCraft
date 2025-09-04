import pytest

try:
    import wodc_merged as wm
except Exception as e:  # pragma: no cover
    pytest.skip(f"wodc_merged unavailable: {e}", allow_module_level=True)


def test_normalize_wod_text_idempotent():
    raw = 'BLOCK FT {\n  10 wall_balls;    \n\n\n  200m run;\n}\n\n'
    once = wm._normalize_wod_text(raw)
    twice = wm._normalize_wod_text(once)
    assert once == twice
    # No double blank lines, ends with single newline
    assert '\n\n\n' not in once
    assert once.endswith('\n')

