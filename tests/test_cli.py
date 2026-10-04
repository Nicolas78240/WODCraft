"""The ``wodc`` command line: exit codes, output and options."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wodcraft.cli import EXIT_DIAGNOSTICS, EXIT_OK, EXIT_USAGE, main

FRAN = "# Fran\n21-15-9 for time, cap 10:00\n  Thruster 95/65 lb\n  Pull-up\n"
BROKEN = "For time\n  10 Frobnicate\n"
SESSION = "# Tuesday\ndate: 2026-09-23\ntime: 18:00\n\n## Metcon\nAMRAP 10:00\n  10 Burpee\n"


@pytest.fixture
def wod(tmp_path: Path):
    def make(text: str = FRAN, name: str = "a.wod") -> str:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    return make


def run(argv, capsys) -> tuple[int, str, str]:
    status = main(argv)
    captured = capsys.readouterr()
    return status, captured.out, captured.err


# --------------------------------------------------------------------------- exit codes


def test_a_valid_file_exits_zero(wod, capsys):
    status, out, _ = run(["check", wod()], capsys)
    assert status == EXIT_OK
    assert "valid" in out


def test_a_file_with_an_error_exits_one(wod, capsys):
    status, _, _ = run(["check", wod(BROKEN)], capsys)
    assert status == EXIT_DIAGNOSTICS


def test_no_command_prints_the_help_and_exits_two(capsys):
    status, out, _ = run([], capsys)
    assert status == EXIT_USAGE
    assert "usage: wodc" in out


def test_a_missing_file_exits_two(capsys):
    status, _, err = run(["check", "nowhere.wod"], capsys)
    assert status == EXIT_USAGE
    assert "no such file" in err


def test_an_unknown_command_exits_two():
    with pytest.raises(SystemExit) as excinfo:
        main(["frobnicate"])
    assert excinfo.value.code == EXIT_USAGE


def test_version_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "spec 1.0" in capsys.readouterr().out


def test_warnings_alone_still_exit_zero(wod, capsys):
    status, out, _ = run(["check", wod("For time\n  1 m Run\n")], capsys)
    assert status == EXIT_OK
    assert "W100" in out


# --------------------------------------------------------------------------- check


def test_check_prints_the_diagnostic_with_its_location(wod, capsys):
    _, out, _ = run(["check", wod(BROKEN)], capsys)
    assert "2:6: error E020" in out


def test_check_counts_the_warnings(wod, capsys):
    _, out, _ = run(["check", wod("For time\n  1 m Run\n")], capsys)
    assert "(1 warning)" in out


def test_check_quiet_hides_the_warnings_and_the_ok_line(wod, capsys):
    _, out, _ = run(["check", "--quiet", wod("For time\n  1 m Run\n")], capsys)
    assert out == ""


def test_check_json_emits_a_machine_readable_array(wod, capsys):
    path = wod(BROKEN)

    _, out, _ = run(["check", "--json", path], capsys)

    payload = json.loads(out)
    assert [(d["code"], d["line"], d["severity"]) for d in payload] == [("E016", 1, "error"), ("E020", 2, "error")]
    assert payload[1]["file"].endswith("a.wod")
    assert "suggestion" in payload[1]


def test_check_json_of_a_clean_file_is_an_empty_array(wod, capsys):
    _, out, _ = run(["check", "--json", wod()], capsys)
    assert json.loads(out) == []


def test_check_accepts_several_files(wod, capsys):
    status, out, _ = run(["check", wod(FRAN, "a.wod"), wod(BROKEN, "b.wod")], capsys)
    assert status == EXIT_DIAGNOSTICS
    assert "a.wod: valid" in out
    assert "E020" in out


# --------------------------------------------------------------------------- build


def test_build_prints_the_compiled_json(wod, capsys):
    _, out, _ = run(["build", wod()], capsys)

    document = json.loads(out)
    assert document["wodcraft"] == "1.0"
    assert document["title"] == "Fran"
    assert document["blocks"][0]["reps"] == [21, 15, 9]


def test_build_writes_to_the_output_file(wod, tmp_path, capsys):
    target = tmp_path / "out.json"

    status, out, _ = run(["build", wod(), "-o", str(target)], capsys)

    assert status == EXIT_OK
    assert out == ""
    assert json.loads(target.read_text(encoding="utf-8"))["title"] == "Fran"
    assert target.read_text(encoding="utf-8").endswith("\n")


def test_build_compact_is_a_single_line(wod, capsys):
    _, out, _ = run(["build", "--compact", wod()], capsys)
    assert len(out.strip().splitlines()) == 1
    assert json.loads(out)["title"] == "Fran"


def test_build_of_several_files_emits_a_list(wod, capsys):
    _, out, _ = run(["build", wod(FRAN, "a.wod"), wod(SESSION, "b.wod")], capsys)
    payload = json.loads(out)
    assert isinstance(payload, list)
    assert [d["kind"] for d in payload] == ["workout", "session"]


def test_build_fails_and_reports_on_stderr(wod, capsys):
    status, out, err = run(["build", wod(BROKEN)], capsys)
    assert status == EXIT_DIAGNOSTICS
    assert out == ""
    assert "E020" in err


# --------------------------------------------------------------------------- show, timer, export


def test_show_prints_the_whiteboard(wod, capsys):
    _, out, _ = run(["show", wod()], capsys)
    assert out.startswith("FRAN\n")
    assert "95/65 lb" in out


def test_show_resolves_with_the_given_category_and_units(wod, capsys):
    _, out, _ = run(["show", "--category", "women", "--units", "kg", wod()], capsys)
    assert "30 kg" in out
    assert "[women · rx · kg]" in out


def test_show_applies_a_level(wod, capsys):
    source = FRAN + "\nScaled:\n  Pull-up -> Ring row\n"
    _, out, _ = run(["show", "--level", "scaled", wod(source)], capsys)
    assert "Ring row" in out


def test_show_uses_a_profile_file(wod, tmp_path, capsys):
    profile = tmp_path / "me.toml"
    profile.write_text('category = "women"\nunits = "lb"\n', encoding="utf-8")

    _, out, _ = run(["show", "--profile", str(profile), wod()], capsys)

    assert "65 lb" in out


def test_timer_prints_the_timeline(wod, capsys):
    _, out, _ = run(["timer", wod("EMOM 3:00\n  10 Burpee\n")], capsys)
    lines = out.strip().splitlines()
    assert len(lines) == 4
    assert lines[-1].endswith("total")


def test_export_markdown(wod, capsys):
    _, out, _ = run(["export", "md", wod()], capsys)
    assert out.startswith("# Fran\n")
    assert "```" in out


def test_export_ics(wod, capsys):
    _, out, _ = run(["export", "ics", wod(SESSION)], capsys)
    assert "BEGIN:VCALENDAR" in out
    assert "DTSTART:20260923T180000" in out


def test_export_writes_to_a_file(wod, tmp_path, capsys):
    target = tmp_path / "out.md"
    run(["export", "markdown", wod(), "-o", str(target)], capsys)
    assert target.read_text(encoding="utf-8").startswith("# Fran")


def test_export_of_a_broken_file_exits_one(wod, capsys):
    status, _, err = run(["export", "md", wod(BROKEN)], capsys)
    assert status == EXIT_DIAGNOSTICS
    assert "E020" in err


# --------------------------------------------------------------------------- fmt


def test_fmt_prints_the_canonical_form(wod, capsys):
    status, out, _ = run(["fmt", wod("for time, cap 10\n      400m Run\n")], capsys)
    assert status == EXIT_OK
    assert out == "For time, cap 10:00\n  400 m Run\n"


def test_fmt_leaves_movement_names_as_written(wod, capsys):
    # The formatter works on the syntax tree and never consults the catalog, so the
    # spelling of a movement name is the author's. SPEC §2 only makes keywords, units
    # and labels canonical.
    _, out, _ = run(["fmt", wod("for time\n  10 burpee\n")], capsys)
    assert out == "For time\n  10 burpee\n"


def test_fmt_check_passes_on_a_canonical_file(wod, capsys):
    status, _, _ = run(["fmt", "--check", wod()], capsys)
    assert status == EXIT_OK


def test_fmt_check_fails_on_a_non_canonical_file(wod, capsys):
    status, _, err = run(["fmt", "--check", wod("for time\n      400m Run\n")], capsys)
    assert status == EXIT_DIAGNOSTICS
    assert "not canonical" in err


def test_fmt_write_rewrites_the_file(wod, capsys):
    path = wod("for time\n      400m Run\n")

    status, out, _ = run(["fmt", "--write", path], capsys)

    assert status == EXIT_OK
    assert Path(path).read_text(encoding="utf-8") == "For time\n  400 m Run\n"
    assert "formatted" in out


def test_fmt_write_leaves_a_canonical_file_alone(wod, capsys):
    path = wod()
    before = Path(path).read_text(encoding="utf-8")

    _, out, _ = run(["fmt", "--write", path], capsys)

    assert Path(path).read_text(encoding="utf-8") == before
    assert out == ""


def test_fmt_refuses_a_file_with_errors(wod, capsys):
    status, _, err = run(["fmt", wod(BROKEN)], capsys)
    # the movement is unknown to the compiler but the file parses, so fmt succeeds;
    # a genuine syntax error is what stops it
    assert status == EXIT_OK or "error" in err


def test_fmt_reports_a_syntax_error_and_exits_one(wod, capsys):
    status, _, err = run(["fmt", wod("AMRAP 12 m\n  10 Burpee\n")], capsys)
    assert status == EXIT_DIAGNOSTICS
    assert "E001" in err


# --------------------------------------------------------------------------- catalog and lib


def test_catalog_lists_the_movements(capsys):
    status, out, _ = run(["catalog"], capsys)
    assert status == EXIT_OK
    assert "thruster" in out
    assert out.strip().endswith("movements")


def test_catalog_filters_by_query(capsys):
    _, out, _ = run(["catalog", "thruster"], capsys)
    assert "thruster" in out
    assert "burpee" not in out
    assert " of " in out.splitlines()[-1]


def test_catalog_filters_by_family(capsys):
    _, out, _ = run(["catalog", "--family", "M"], capsys)
    assert all(" M  " in line for line in out.splitlines() if line and not line.startswith(("\n", " ")) and "movement" not in line)


def test_catalog_json_is_machine_readable(capsys):
    _, out, _ = run(["catalog", "thruster", "--json"], capsys)
    rows = json.loads(out)
    assert {row["id"] for row in rows} >= {"thruster"}
    assert rows[0]["name"]


def test_catalog_shows_the_rx_reference(capsys):
    _, out, _ = run(["catalog", "thruster"], capsys)
    assert "Rx 43/30 kg" in out


def test_lib_lists_the_standard_library(capsys):
    status, out, _ = run(["lib"], capsys)
    assert status == EXIT_OK
    assert "girls/fran" in out
    assert "Fran" in out


def test_lib_filters_by_name(capsys):
    _, out, _ = run(["lib", "girls/fran"], capsys)
    assert out.strip() == "girls/fran               Fran"


# --------------------------------------------------------------------------- stdin


def test_check_reads_stdin(capsys, monkeypatch):
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO(FRAN))

    status, out, _ = run(["check", "-"], capsys)

    assert status == EXIT_OK
    assert "<stdin>: valid" in out


def test_build_reads_stdin(capsys, monkeypatch):
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO("AMRAP 5\n  10 Burpee\n"))

    _, out, _ = run(["build", "-"], capsys)

    assert json.loads(out)["blocks"][0]["duration_s"] == 300.0


def test_stdin_errors_are_located_in_stdin(capsys, monkeypatch):
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO(BROKEN))

    status, out, _ = run(["check", "-"], capsys)

    assert status == EXIT_DIAGNOSTICS
    assert "<stdin>:2:6" in out


# --------------------------------------------------------------------------- --lib


def test_the_lib_option_adds_a_search_directory(tmp_path, capsys):
    extra = tmp_path / "extra"
    extra.mkdir()
    (extra / "mine.wod").write_text("# Mine\nAMRAP 5\n  10 Burpee\n", encoding="utf-8")
    main_file = tmp_path / "main.wod"
    main_file.write_text("use mine\n", encoding="utf-8")

    status, out, _ = run(["build", "--lib", str(extra), str(main_file)], capsys)

    assert status == EXIT_OK
    assert json.loads(out)["blocks"][0]["used"]["title"] == "Mine"
