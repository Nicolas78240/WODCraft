import pytest

try:
    import wodc_merged as wm
except Exception as e:  # pragma: no cover
    pytest.skip(f"wodc_merged unavailable: {e}", allow_module_level=True)


def _first_line(ast):
    for seg in ast.get("program", []):
        if seg.get("type") == "BLOCK":
            for st in seg.get("stmts", []):
                ln = st.get("line", st)
                if ln.get("type") == "LINE":
                    return ln
    return None


def test_dual_cal_resolves_by_gender():
    text = 'BLOCK FT {\n  15/12 cal row;\n}\n'
    ast = wm.parse_wod_text(text)
    issues = []
    wm._apply_catalog_and_resolve(ast, catalog=None, track="RX", gender="female", issues_out=issues)
    ln = _first_line(ast)
    assert ln and ln.get("qty", {}).get("kind") == "cal"
    assert float(ln["qty"]["value"]) == 12.0


def test_alias_note_and_w050_warning():
    text = 'BLOCK FT {\n  10 wb;\n}\n'
    ast = wm.parse_wod_text(text)
    notes = []
    wm._apply_catalog_and_resolve(ast, catalog=None, track="RX", gender="male", issues_out=notes)
    # Lint surfaces alias notes as W050 warnings
    issues = wm.lint(ast)
    assert any(i.get("code") == "W050" for i in issues)

