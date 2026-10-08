"""The conformance suite of SPEC §16.

``spec/conformance/`` holds pairs of files: ``NAME.wod`` with either ``NAME.json``
(the expected compiled output, ``estimate`` excluded) or ``NAME.diag`` (one
``CODE LINE`` per expected diagnostic). An implementation conforms when it produces,
for every case, the same JSON or the same set of diagnostic codes and lines.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wodcraft.api import compile_file

CONFORMANCE_DIR = Path(__file__).resolve().parent.parent / "spec" / "conformance"
CASES = sorted(CONFORMANCE_DIR.glob("*.wod"))
IDS = [case.stem for case in CASES]

# Cases whose expectation states the specification while the implementation still
# deviates. Each entry must be removed as soon as the implementation catches up.
KNOWN_DEVIATIONS: dict[str, str] = {}


def strip_estimate(obj):
    if isinstance(obj, dict):
        return {key: strip_estimate(value) for key, value in obj.items() if key != "estimate"}
    if isinstance(obj, list):
        return [strip_estimate(item) for item in obj]
    return obj


def expected_diagnostics(path: Path) -> list[tuple[str, int]]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        code, number = line.split()
        out.append((code, int(number)))
    return out


def actual(case: Path):
    result = compile_file(case)
    payload = result.documents if len(result.documents) > 1 else result.document
    return result, strip_estimate(payload)


# --------------------------------------------------------------------------- the suite


def test_the_suite_is_not_empty():
    assert len(CASES) >= 25


def test_every_case_has_exactly_one_expectation():
    missing, ambiguous = [], []
    for case in CASES:
        has_json = case.with_suffix(".json").exists()
        has_diag = case.with_suffix(".diag").exists()
        if has_json and has_diag:
            ambiguous.append(case.name)
        elif not (has_json or has_diag):
            missing.append(case.name)
    assert missing == []
    assert ambiguous == []


def test_every_expectation_has_a_case():
    orphans = [
        path.name
        for path in sorted(CONFORMANCE_DIR.iterdir())
        if path.suffix in (".json", ".diag") and not path.with_suffix(".wod").exists()
    ]
    assert orphans == []


def test_the_suite_covers_every_format():
    names = set(IDS)
    for expected in (
        "for_time_simple",
        "rounds_for_time",
        "rounds_untimed",
        "ladder_long",
        "amrap_simple",
        "emom_odd_even",
        "enmom",
        "every_intervals",
        "tabata",
        "death_by",
        "max_load_sets",
        "sets_ladder_rpe",
    ):
        assert expected in names, expected


def test_the_suite_covers_levels_sessions_and_teams():
    names = set(IDS)
    assert {"levels_scaled", "levels_three", "session_day", "team_amrap"} <= names


def test_the_suite_covers_the_main_diagnostics():
    codes = set()
    for case in CASES:
        diag = case.with_suffix(".diag")
        if diag.exists():
            codes.update(code for code, _ in expected_diagnostics(diag))
    for expected in (
        "E002",
        "E003",
        "E012",
        "E013",
        "E020",
        "E030",
        "E031",
        "E032",
        "E033",
        "E034",
        "E036",
        "E037",
        "E040",
        "E041",
        "E050",
    ):
        assert expected in codes, expected
    for expected in ("W100", "W101", "W102", "W103", "W104"):
        assert expected in codes, expected


# --------------------------------------------------------------------------- the cases


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_conformance(case: Path, request):
    if case.stem in KNOWN_DEVIATIONS:
        request.node.add_marker(pytest.mark.xfail(reason=KNOWN_DEVIATIONS[case.stem], strict=True))

    expected_json = case.with_suffix(".json")
    if expected_json.exists():
        result, compiled = actual(case)
        assert result.ok, result.report()
        assert result.diagnostics == [], [d.format() for d in result.diagnostics]
        assert compiled == json.loads(expected_json.read_text(encoding="utf-8"))
    else:
        result = compile_file(case)
        produced = [(d.code, d.span.line) for d in result.diagnostics]
        assert produced == expected_diagnostics(case.with_suffix(".diag"))


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.with_suffix(".diag").exists()], ids=[c.stem for c in CASES if c.with_suffix(".diag").exists()]
)
def test_an_error_case_does_not_compile(case: Path):
    expected = expected_diagnostics(case.with_suffix(".diag"))
    result = compile_file(case)
    if any(code.startswith("E") for code, _ in expected):
        assert result.ok is False
    else:
        assert result.ok is True  # a warnings-only case still compiles


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.with_suffix(".json").exists()], ids=[c.stem for c in CASES if c.with_suffix(".json").exists()]
)
def test_a_passing_case_is_json_round_trippable(case: Path):
    payload = json.loads(case.with_suffix(".json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload


def test_the_expectations_never_contain_an_estimate():
    for case in CASES:
        expected_json = case.with_suffix(".json")
        if expected_json.exists():
            assert '"estimate"' not in expected_json.read_text(encoding="utf-8"), case.name


def test_every_expected_document_validates_against_the_schema():
    jsonschema = pytest.importorskip("jsonschema")
    from wodcraft.resources import schema

    validator = jsonschema.Draft202012Validator(schema())
    for case in CASES:
        expected = case.with_suffix(".json")
        if not expected.exists():
            continue
        payload = json.loads(expected.read_text(encoding="utf-8"))
        for document in payload if isinstance(payload, list) else [payload]:
            errors = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in validator.iter_errors(document)]
            assert not errors, f"{case.stem}: {errors}"
