"""Tests for the WODCraft MCP server.

Three things are checked here:

1. every tool, called directly as a Python function, on a valid and on a broken source;
2. every DSL example the server ships — the syntax guide, the tool docstrings, the
   `design_wod` prompt and ``docs/mcp.md`` — compiles with no error;
3. the loop an assistant actually runs: draft, check, correct, check again.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

import pytest

pytest.importorskip("mcp.server.mcpserver", reason="the MCP server needs the mcp SDK (pip install 'mcp>=2.2,<3')")

from mcp.server.mcpserver.exceptions import ResourceError, ToolError  # noqa: E402

from wodcraft.mcp import guide, models, paths, server  # noqa: E402

FRAN = """\
# Fran
21-15-9 for time, cap 10:00
  Thruster 43/30 kg
  Pull-up
"""

BROKEN = """\
# Broken
AMRAP 12
  10 Trusters
  15 Box jump 24 kg
"""


# --------------------------------------------------------------------------- tools


def test_check_wod_accepts_a_valid_source():
    result = server.check_wod(FRAN)
    assert isinstance(result, models.CheckResult)
    assert result.ok is True
    assert result.errors == 0
    assert [d for d in result.diagnostics if d.severity == "error"] == []
    assert "Valid" in result.summary


def test_check_wod_locates_every_error():
    result = server.check_wod(BROKEN)
    assert result.ok is False
    assert result.errors == len([d for d in result.diagnostics if d.severity == "error"]) >= 2
    codes = {d.code for d in result.diagnostics}
    assert "E020" in codes  # unknown movement
    assert "E032" in codes  # a box jump takes a height, not a load
    unknown = next(d for d in result.diagnostics if d.code == "E020")
    assert unknown.line == 3 and unknown.col > 0
    assert unknown.suggestion and "Thruster" in unknown.suggestion


def test_check_wod_rejects_an_empty_source():
    with pytest.raises(ToolError):
        server.check_wod("   \n")


def test_compile_wod_returns_the_document():
    result = server.compile_wod(FRAN)
    assert result.ok is True
    document = result.document
    assert document is not None
    assert document["wodcraft"] == "1.0"
    assert document["kind"] == "workout"
    assert document["title"] == "Fran"
    assert document["score"]["type"] == "time"
    movements = [item["movement"] for item in document["blocks"][0]["items"]]
    assert movements == ["thruster", "pull_up"]
    assert json.dumps(document)  # the document is plain JSON


def test_compile_wod_returns_no_document_when_the_source_is_broken():
    result = server.compile_wod(BROKEN)
    assert result.ok is False
    assert result.document is None
    assert result.documents == []


def test_show_wod_renders_the_whiteboard():
    raw = server.show_wod(FRAN)
    assert raw.ok is True
    assert raw.resolved_for is None
    assert "FRAN" in raw.board
    assert "43/30 kg" in raw.board


def test_show_wod_resolves_for_an_athlete():
    result = server.show_wod(FRAN, category="women", units="lb", level="scaled")
    assert result.ok is True
    assert result.resolved_for == {"category": "women", "level": "scaled", "units": "lb"}
    assert "43/30" not in result.board  # the dual is flattened
    assert "lb" in result.board


def test_show_wod_reports_diagnostics_instead_of_a_board():
    result = server.show_wod(BROKEN)
    assert result.ok is False
    assert result.board == ""
    assert result.diagnostics


def test_format_wod_canonicalises():
    result = server.format_wod("# Fran\n21-15-9 FOR TIME, CAP 10:00\n  Thruster 43/30kg\n  Pull-up\n")
    assert result.ok is True
    assert result.changed is True
    assert result.formatted == FRAN
    # formatting is idempotent
    assert server.format_wod(result.formatted).changed is False


def test_timeline_wod_lays_out_the_clock():
    result = server.timeline_wod("# Alternating\nEMOM 4\n  Odd: 10 Burpee\n  Even: 12/10 cal Row\n")
    assert result.ok is True
    assert len(result.segments) == 4
    assert result.total_s == 240
    assert [s.at_s for s in result.segments] == [0, 60, 120, 180]
    assert "Burpee" in result.segments[0].label
    assert "Row" in result.segments[1].label
    assert result.rendered.strip()


def test_timeline_wod_marks_open_ended_work():
    result = server.timeline_wod("# Open\nFor time\n  100 Burpee\n")
    assert result.ok is True
    assert result.segments[0].open_ended is True


def test_timeline_wod_carries_the_workout_cap():
    result = server.timeline_wod("# Two parts\ncap: 20:00\nFor time\n  50 Burpee\nAMRAP 6:00\n  10 Air squat\n")
    assert result.ok is True
    assert result.cap_s == 1200
    assert "   20:00          cap: the clock stops" in result.rendered
    assert server.timeline_wod("# Open\nFor time\n  100 Burpee\n").cap_s is None


def test_search_movements_ranks_exact_matches_first():
    result = server.search_movements("thruster")
    assert result.movements[0].id == "thruster"
    assert result.movements[0].param == ["load"]
    assert result.movements[0].family == "W"
    assert result.catalog_size > 100


def test_search_movements_accepts_french_aliases():
    result = server.search_movements("traction")
    assert result.movements[0].id == "pull_up"
    assert "traction" in result.movements[0].fr


def test_search_movements_filters_by_family_and_limit():
    result = server.search_movements(family="M", limit=3)
    assert result.count == 3
    assert result.truncated is True
    assert all(m.family == "M" for m in result.movements)
    assert result.total > 3


def test_search_movements_finds_nothing_gracefully():
    result = server.search_movements("zzzznotamovement")
    assert result.count == 0 and result.total == 0 and result.movements == []


def test_library_list_and_get():
    listing = server.library_list("girls")
    assert listing.count >= 20
    paths_seen = [w.path for w in listing.workouts]
    assert "girls/fran" in paths_seen
    assert all(p.startswith("girls/") for p in paths_seen)

    workout = server.library_get("girls/fran")
    assert workout.path == "girls/fran"
    assert workout.title == "Fran"
    assert workout.use_line == "use girls/fran"
    assert workout.ok is True
    assert "Thruster" in workout.source
    assert "girls" in workout.tags


def test_library_get_suggests_on_a_typo():
    with pytest.raises(ToolError) as excinfo:
        server.library_get("girls/fram")
    assert "girls/fran" in str(excinfo.value)


def test_library_get_refuses_to_escape_the_library():
    for attempt in ("../../etc/passwd", "/etc/passwd", "girls/../../../setup.py", ""):
        with pytest.raises(ToolError):
            server.library_get(attempt)


def test_every_library_workout_compiles():
    broken = {}
    for path in paths.library_paths():
        result = server.library_get(path)
        if not result.ok:
            broken[path] = [d.model_dump() for d in result.diagnostics if d.severity == "error"]
    assert broken == {}


# --------------------------------------------------------------------------- registration
#
# The MCP handlers are coroutines; the tests drive them with asyncio.run so that the suite
# needs no async pytest plugin.


def _run(coroutine):
    return asyncio.run(coroutine)


def _read(uri: str) -> str:
    contents = list(_run(server.server.read_resource(uri)))
    assert len(contents) == 1
    return contents[0].content


def test_the_server_registers_every_tool():
    tools = {tool.name: tool for tool in _run(server.server.list_tools())}
    assert set(tools) == {
        "check_wod",
        "compile_wod",
        "show_wod",
        "format_wod",
        "timeline_wod",
        "search_movements",
        "library_list",
        "library_get",
    }
    for tool in tools.values():
        assert tool.description, f"{tool.name} has no description"
        assert tool.input_schema["type"] == "object"
        assert tool.output_schema, f"{tool.name} returns unstructured output"
    assert tools["check_wod"].input_schema["required"] == ["source"]
    assert set(tools["show_wod"].input_schema["properties"]) == {"source", "category", "level", "units"}
    assert set(tools["search_movements"].input_schema["properties"]) == {"query", "family", "limit"}


def test_the_server_registers_every_resource():
    uris = {str(resource.uri) for resource in _run(server.server.list_resources())}
    assert {"wodcraft://spec", "wodcraft://catalog", "wodcraft://guide/syntax"} <= uris
    templates = {template.uri_template for template in _run(server.server.list_resource_templates())}
    assert "wodcraft://library/{+path}" in templates


def test_reading_the_resources():
    assert _read("wodcraft://guide/syntax") == guide.SYNTAX_GUIDE

    catalog = json.loads(_read("wodcraft://catalog"))
    assert catalog["count"] == len(catalog["movements"]) > 100
    assert {m["id"] for m in catalog["movements"]} >= {"thruster", "pull_up", "run"}

    index = json.loads(_read("wodcraft://library"))
    assert "girls/fran" in index["workouts"]

    assert _read("wodcraft://library/girls/fran").startswith("# Fran")


def test_reading_the_spec():
    if paths.spec_file() is None:
        pytest.skip("spec/SPEC.md is not on disk next to this installation")
    assert "WODCraft Language Specification" in _read("wodcraft://spec")


def test_reading_an_unknown_library_workout_fails_cleanly():
    with pytest.raises(ResourceError):
        _run(server.server.read_resource("wodcraft://library/girls/nope"))


def test_the_design_wod_prompt():
    prompts = {prompt.name: prompt for prompt in _run(server.server.list_prompts())}
    assert set(prompts) == {"design_wod"}
    arguments = {argument.name: argument.required for argument in prompts["design_wod"].arguments or []}
    assert arguments == {"goal": True, "duration": False, "equipment": False, "level": False}

    rendered = _run(server.server.get_prompt("design_wod", {"goal": "pull strength", "duration": "12 min"}))
    assert len(rendered.messages) == 1
    text = rendered.messages[0].content.text
    assert "pull strength" in text and "12 min" in text
    assert "check_wod" in text
    assert guide.SYNTAX_GUIDE in text  # the prompt carries the exact syntax


def test_calling_a_tool_through_the_protocol_returns_structured_output():
    result = _run(server.server.call_tool("check_wod", {"source": FRAN}))
    structured = result.structured_content
    assert structured is not None
    assert structured["ok"] is True
    assert structured["diagnostics"] == []


def test_the_command_line_parser():
    parser = server.build_parser()
    default = parser.parse_args([])
    assert default.http is False
    http = parser.parse_args(["--http", "--port", "9001", "--path", "/wodcraft", "--stateless"])
    assert (http.http, http.port, http.path, http.stateless) == (True, 9001, "/wodcraft", True)


# --------------------------------------------------------------------------- examples


def _examples(label: str, text: str) -> list[tuple[str, str]]:
    return [(f"{label}#{i}", block) for i, block in enumerate(guide.wod_examples(text), 1)]


def _all_examples() -> list[tuple[str, str]]:
    cases = _examples("guide", guide.SYNTAX_GUIDE)
    cases += _examples("server.py", inspect.getsource(server))
    cases += _examples("models.py", inspect.getsource(models))
    docs = Path(__file__).resolve().parents[4] / "docs" / "mcp.md"
    if docs.is_file():
        cases += _examples("docs/mcp.md", docs.read_text(encoding="utf-8"))
    return cases


ALL_EXAMPLES = _all_examples()


def test_there_are_examples_to_check():
    labels = {label.split("#")[0] for label, _ in ALL_EXAMPLES}
    assert len(ALL_EXAMPLES) >= 15
    assert "guide" in labels and "server.py" in labels


@pytest.mark.parametrize("label,source", ALL_EXAMPLES, ids=[label for label, _ in ALL_EXAMPLES])
def test_every_shipped_example_compiles(label: str, source: str):
    result = server.check_wod(source)
    assert result.ok, f"{label} does not compile:\n{source}\n" + "\n".join(
        f"  {d.code} {d.line}:{d.col} {d.message}" for d in result.diagnostics
    )


def test_the_guide_covers_the_syntax():
    for topic in ("AMRAP", "EMOM", "Scaled:", "Buy-in:", "use ", "cap ", "Teams of", "max "):
        assert topic in guide.SYNTAX_GUIDE, f"the guide never mentions {topic!r}"


# --------------------------------------------------------------------------- the loop


def test_draft_check_correct_cycle():
    """The loop an assistant runs: a plausible first draft, then the compiler's corrections."""
    draft = """\
# Engine builder
AMRAP 15
  200m Row
  15 Trusters 43/30
  10 Box jump 24/20 kg
"""
    first = server.check_wod(draft)
    assert first.ok is False
    codes = {d.code for d in first.diagnostics}
    assert "E020" in codes  # 'Trusters' is not a movement
    assert "E032" in codes  # a box jump takes a height, not a load

    # Each diagnostic says what to do, and where.
    unknown = next(d for d in first.diagnostics if d.code == "E020")
    assert unknown.line == 4
    assert "Thruster" in (unknown.suggestion or "")

    corrected = """\
# Engine builder
AMRAP 15:00
  200 m Row
  15 Thruster 43/30 kg
  10 Box jump 24/20 in
"""
    second = server.check_wod(corrected)
    assert second.ok is True, second.summary
    assert [d.code for d in second.diagnostics if d.severity == "error"] == []

    # ...and the corrected draft is usable end to end.
    document = server.compile_wod(corrected).document
    assert document is not None
    assert document["score"]["type"] == "rounds+reps"
    assert [item["movement"] for item in document["blocks"][0]["items"]] == ["row", "thruster", "box_jump"]
    assert server.format_wod(corrected).formatted == corrected
    assert "ENGINE BUILDER" in server.show_wod(corrected).board
    assert server.timeline_wod(corrected).total_s == 900


def test_a_correction_the_compiler_suggests_actually_fixes_the_source():
    """Follow the suggestion of every E020 blindly and the source must compile."""
    draft = "# Typos\nAMRAP 10\n  10 Trusters\n  10 Pul-ups\n"
    result = server.check_wod(draft)
    assert result.ok is False
    fixed = draft
    for diagnostic in result.diagnostics:
        if diagnostic.code != "E020":
            continue
        assert diagnostic.suggestion, f"{diagnostic.message} has no suggestion"
        wrong = fixed.splitlines()[diagnostic.line - 1][diagnostic.col - 1 : (diagnostic.end_col or 0) - 1]
        right = diagnostic.suggestion.split("'")[1]
        fixed = fixed.replace(wrong, right)
    assert server.check_wod(fixed).ok is True
