"""iCalendar export (RFC 5545)."""

from __future__ import annotations

import pytest

from conftest import compile_wod
from wodcraft.emit.ics import CRLF, IcsError, _escape, _fold, to_ics

SESSION = "# Tuesday\ndate: 2026-09-23\ntime: 18:00\n## Metcon\nAMRAP 10:00\n  10 Burpee\n"


def document(source: str = SESSION, estimate: bool = True) -> dict:
    result = compile_wod(source, estimate=estimate)
    assert result.ok, result.report()
    return result.document


def unfold(text: str) -> list[str]:
    """Undo RFC 5545 folding so the logical lines can be inspected."""
    lines: list[str] = []
    for raw in text.split(CRLF):
        if raw.startswith(" ") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return [line for line in lines if line]


# --------------------------------------------------------------------------- structure


def test_the_calendar_wraps_one_event():
    logical = unfold(to_ics(document()))
    assert logical[0] == "BEGIN:VCALENDAR"
    assert logical[1] == "VERSION:2.0"
    assert "CALSCALE:GREGORIAN" in logical
    assert logical.count("BEGIN:VEVENT") == 1
    assert logical[-1] == "END:VCALENDAR"


def test_the_prodid_names_wodcraft():
    assert any(line.startswith("PRODID:-//WODCraft//") for line in unfold(to_ics(document())))


def test_every_line_ends_with_crlf():
    text = to_ics(document())
    assert text.endswith(CRLF)
    assert "\n" not in text.replace(CRLF, "")


def test_dtstart_comes_from_the_date_and_time():
    assert "DTSTART:20260923T180000" in unfold(to_ics(document()))


def test_a_session_without_a_time_starts_at_six_in_the_evening():
    source = "# Day\ndate: 2026-09-23\n## Metcon\nAMRAP 10:00\n  10 Burpee\n"
    assert "DTSTART:20260923T180000" in unfold(to_ics(document(source)))


def test_dtend_is_at_least_thirty_minutes_after_dtstart():
    source = "# Day\ndate: 2026-09-23\ntime: 07:00\n## Metcon\nAMRAP 5:00\n  10 Burpee\n"
    logical = unfold(to_ics(document(source)))
    assert "DTSTART:20260923T070000" in logical
    assert "DTEND:20260923T073000" in logical


def test_dtend_follows_the_estimated_duration():
    source = "# Day\ndate: 2026-09-23\ntime: 07:00\n## Metcon\nAMRAP 45:00\n  10 Burpee\n"
    assert "DTEND:20260923T074500" in unfold(to_ics(document(source)))


def test_the_uid_is_stable_across_exports():
    first = [line for line in unfold(to_ics(document())) if line.startswith("UID:")]
    second = [line for line in unfold(to_ics(document())) if line.startswith("UID:")]
    assert first == second
    assert first[0].endswith("@wodcraft")


def test_the_summary_is_the_document_title():
    assert "SUMMARY:Tuesday" in unfold(to_ics(document()))


def test_the_description_holds_the_whiteboard():
    (description,) = [line for line in unfold(to_ics(document())) if line.startswith("DESCRIPTION:")]
    assert "AMRAP 10:00" in description
    assert "\\n" in description  # newlines are escaped, not literal


# --------------------------------------------------------------------------- escaping


@pytest.mark.parametrize(
    ("raw", "escaped"),
    [
        ("a,b", "a\\,b"),
        ("a;b", "a\\;b"),
        ("a\\b", "a\\\\b"),
        ("a\nb", "a\\nb"),
        ("Tue, a; b", "Tue\\, a\\; b"),
    ],
)
def test_commas_semicolons_backslashes_and_newlines_are_escaped(raw, escaped):
    assert _escape(raw) == escaped


def test_a_title_with_a_comma_and_a_semicolon_is_escaped_in_the_summary():
    source = "# Tue, heavy; long\ndate: 2026-09-23\n## Metcon\nAMRAP 10:00\n  10 Burpee\n"
    assert "SUMMARY:Tue\\, heavy\\; long" in unfold(to_ics(document(source)))


def test_a_backslash_is_doubled_before_anything_else():
    assert _escape("a\\,b") == "a\\\\\\,b"


# --------------------------------------------------------------------------- folding


def test_a_short_line_is_not_folded():
    assert _fold("SUMMARY:Fran") == "SUMMARY:Fran"


def test_a_line_of_exactly_seventy_five_octets_is_not_folded():
    line = "X" * 75
    assert _fold(line) == line


def test_a_long_line_is_folded_and_every_continuation_starts_with_a_space():
    folded = _fold("X" * 300)

    parts = folded.split(CRLF)
    assert len(parts) > 1
    assert all(len(part.encode()) <= 75 for part in parts)
    assert all(part.startswith(" ") for part in parts[1:])
    assert parts[0][0] != " "


def test_folding_is_reversible():
    original = "DESCRIPTION:" + "abc " * 60
    parts = _fold(original).split(CRLF)
    assert "".join([parts[0], *[part[1:] for part in parts[1:]]]) == original


def test_folding_never_splits_a_multibyte_character():
    folded = _fold("SUMMARY:" + "é" * 100)
    for part in folded.split(CRLF):
        part.encode()  # would raise on a broken surrogate
        assert len(part.encode()) <= 75


def test_the_exported_calendar_keeps_every_line_within_seventy_five_octets():
    for line in to_ics(document()).split(CRLF):
        assert len(line.encode()) <= 75, line


# --------------------------------------------------------------------------- errors


def test_a_document_without_a_date_cannot_be_exported():
    workout = document("# Fran\nFor time\n  100 Burpee\n")

    with pytest.raises(IcsError) as excinfo:
        to_ics(workout)

    assert "add 'date: YYYY-MM-DD'" in str(excinfo.value)


def test_an_invalid_date_is_reported_clearly():
    workout = document("# Day\ndate: 2026-13-45\n## Metcon\nAMRAP 10:00\n  10 Burpee\n")

    with pytest.raises(IcsError) as excinfo:
        to_ics(workout)

    assert "invalid date or time" in str(excinfo.value)


def test_ics_error_is_a_value_error():
    assert issubclass(IcsError, ValueError)
