"""Timeline of a workout: what the clock does, segment by segment."""

from __future__ import annotations

from wodcraft.catalog import load_catalog
from wodcraft.emit.board import _head, _movement
from wodcraft.semantics.estimate import builds_up, effort_seconds, item_seconds
from wodcraft.syntax.units import format_clock


def timeline(document: dict) -> list[dict]:
    if document.get("kind") == "session":
        segments: list[dict] = []
        at = 0.0
        for section in document.get("sections", []):
            for segment in timeline(section["workout"]):
                segment = dict(segment, at_s=at + segment["at_s"], section=section["title"])
                segments.append(segment)
            at = segments[-1]["at_s"] + segments[-1]["duration_s"] if segments else at
        return segments
    at = 0.0
    segments = []
    for block in document.get("blocks", []):
        for segment in _block(block, document):
            segments.append(dict(segment, at_s=at))
            at += segment["duration_s"]
    return segments


def _block(block: dict, document: dict) -> list[dict]:
    kind = block.get("type")
    if kind == "rest":
        return [{"duration_s": block.get("seconds", 0), "label": "Rest", "kind": "rest"}]
    if kind == "movement":
        seconds = item_seconds(block, load_catalog())
        return [{"duration_s": seconds, "label": _movement(block, 40), "kind": "work", "open_ended": not seconds}]
    label = _head(block) or kind
    if kind in ("emom", "every"):
        interval = block.get("interval_s") or 60
        total = block.get("duration_s") or interval * (block.get("rounds") or 0)
        count = int(total // interval) if interval else 0
        slots = [i for i in block.get("items", []) if i.get("type") == "slot"]
        out = []
        for index in range(count):
            content = _slot_label(slots, index) if slots else _items_label(block.get("items", []))
            out.append({"duration_s": interval, "label": f"{label} · {index + 1}/{count}: {content}", "kind": "interval"})
        return out
    if kind == "tabata":
        rounds = int(block.get("rounds") or 8)
        movements = [i for i in block.get("items", []) if i.get("type") != "rest"]
        out = []
        for item in movements or [None]:
            name = _items_label([item]) if item else ""
            for index in range(rounds):
                out.append({"duration_s": 30.0, "label": f"{label} · {index + 1}/{rounds}: {name}", "kind": "interval"})
        return out
    if kind == "amrap" and block.get("duration_s"):
        return [{"duration_s": block["duration_s"], "label": f"{label}: {_items_label(block.get('items', []))}", "kind": "work"}]
    items = block.get("items", [])
    content = _items_label(items)
    if kind == "max_load" and block.get("attempts") and items and items[-1].get("type") == "rest":
        content += " between attempts"  # the rest comes between the attempts (SPEC §8)
    if kind == "max_load" and builds_up(block):
        # a lift has its own length: the whole workout's estimate would count every lift once per lift
        duration = block.get("cap_s") or round(effort_seconds(block, load_catalog()))
    else:
        duration = block.get("cap_s") or (document.get("estimate") or {}).get("max_s") or 0
    return [
        {
            "duration_s": duration,
            "label": f"{label}: {content}",
            "kind": "work",
            "open_ended": not block.get("cap_s"),
        }
    ]


def _slot_label(slots: list[dict], index: int) -> str:
    for slot in slots:
        which = slot.get("slot")
        if which == "odd" and index % 2 == 0:
            return _items_label(slot.get("items", []))
        if which == "even" and index % 2 == 1:
            return _items_label(slot.get("items", []))
        if isinstance(which, int):
            cycle = max(int(s["slot"]) for s in slots if isinstance(s.get("slot"), int))
            if index % cycle == which - 1:
                return _items_label(slot.get("items", []))
    return ""


def _items_label(items: list[dict]) -> str:
    labels = []
    for item in items:
        if item.get("type") == "movement":
            labels.append(_movement(item, 0, dots=False))
        elif item.get("type") == "rest":
            labels.append(f"Rest {format_clock(item['seconds'])}")
        else:
            head = _head(item)
            inner = _items_label(item.get("items", []))
            labels.append(f"{head} {inner}".strip())
    return " + ".join(label for label in labels if label)


def timer_cap(document: dict) -> float | None:
    """The cap of the whole workout (`cap:` over several blocks, 1.2): when the clock stops.
    A cap on a block is already the length of that block's segment. A session has no cap of its
    own: the caps of its sections are in `timer_caps`."""
    if document.get("kind") == "session":
        return None
    return document.get("cap_s") or None


def timer_caps(document: dict) -> list[float]:
    """Every moment a workout cap stops the clock, in clock order: the workout's cap, or in a
    session the cap of each section at its place in the session (the section's start plus its cap)."""
    if document.get("kind") != "session":
        cap = timer_cap(document)
        return [cap] if cap else []
    caps: list[float] = []
    at = 0.0
    for section in document.get("sections", []):
        workout = section["workout"]
        cap = timer_cap(workout)
        if cap:
            caps.append(at + cap)
        segments = timeline(workout)
        if segments:
            at += segments[-1]["at_s"] + segments[-1]["duration_s"]
    return sorted(caps)


def render_timer(document: dict) -> str:
    """What `wodc timer` prints: the timeline, with the workout caps when there are some."""
    return render_timeline(timeline(document), caps=timer_caps(document))


def render_timeline(segments: list[dict], cap_s: float | None = None, *, caps: list[float] | None = None) -> str:
    lines = []
    # a workout cap is a moment, not a stretch: at that time the clock stops, whatever is left —
    # it takes its place in time, before the first segment that would start at or after it
    pending = sorted([*(caps or []), *([cap_s] if cap_s else [])])
    for segment in segments:
        while pending and segment["at_s"] >= pending[0]:
            lines.append(_cap_line(pending.pop(0)))
        start = format_clock(segment["at_s"])
        duration = format_clock(segment["duration_s"]) if segment["duration_s"] else "—"
        mark = "~" if segment.get("open_ended") else " "
        lines.append(f"{start:>8}  {duration:>6}{mark} {segment['label']}")
    lines += [_cap_line(cap) for cap in pending]
    total = sum(s["duration_s"] for s in segments)
    lines.append(f"{'':>8}  {format_clock(total):>6}  total")
    return "\n".join(lines)


def _cap_line(cap_s: float) -> str:
    return f"{format_clock(cap_s):>8}  {'':>6}  cap: the clock stops"
