"""iCalendar export (RFC 5545) for sessions that carry a date."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

from wodcraft import __version__
from wodcraft.emit.board import render

CRLF = "\r\n"


class IcsError(ValueError):
    """Raised when a document cannot be turned into a calendar event."""


def to_ics(document: dict) -> str:
    events = _events(document)
    if not events:
        raise IcsError("no date to export: add 'date: YYYY-MM-DD' (and optionally 'time: HH:MM')")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//WODCraft//{__version__}//EN",
        "CALSCALE:GREGORIAN",
        *events,
        "END:VCALENDAR",
    ]
    return CRLF.join(_fold(line) for line in lines) + CRLF


def _events(document: dict) -> list[str]:
    day = document.get("date")
    if not day:
        return []
    try:
        start = datetime.combine(date.fromisoformat(day), _time(document.get("time")))
    except ValueError as err:
        raise IcsError(f"invalid date or time: {err}") from err
    minutes = _minutes(document)
    end = start + timedelta(minutes=minutes)
    title = document.get("title") or "Workout"
    uid = hashlib.sha1(f"{day}{document.get('time', '')}{title}".encode()).hexdigest() + "@wodcraft"
    return [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%S')}",
        f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{_escape(title)}",
        f"DESCRIPTION:{_escape(render(document))}",
        "END:VEVENT",
    ]


def _time(value: str | None):
    from datetime import time

    if not value:
        return time(18, 0)
    hours, _, minutes = value.partition(":")
    return time(int(hours), int(minutes or 0))


def _minutes(document: dict) -> int:
    seconds = 0
    workouts = [s["workout"] for s in document.get("sections", [])] if document.get("kind") == "session" else [document]
    for workout in workouts:
        estimate = workout.get("estimate") or {}
        seconds += estimate.get("max_s") or 0
    return max(30, int(round(seconds / 60)))


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545 line folding at 75 octets."""
    if len(line.encode()) <= 75:
        return line
    out, current = [], ""
    for char in line:
        if len((current + char).encode()) > 73:
            out.append(current)
            current = " " + char
        else:
            current += char
    out.append(current)
    return CRLF.join(out)
