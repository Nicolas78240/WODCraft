"""Whiteboard rendering of a compiled (and optionally resolved) workout."""

from __future__ import annotations

from wodcraft.syntax.units import fmt_num, format_clock

SCORE_LABEL = {
    "time": "time",
    "rounds+reps": "rounds + reps",
    "rounds": "rounds",
    "reps": "reps",
    "load": "load",
    "distance": "distance",
    "calories": "calories",
    "none": "no score",
    "multi": "one score per part",
}


def render(document: dict, width: int = 46, lang: str = "en") -> str:
    if lang != "en":
        document = localize(document, lang)
    if document.get("kind") == "session":
        return _session(document, width)
    return _workout(document, width)


def localize(document: dict, lang: str) -> dict:
    """Rewrite movement names in another language, using the catalog aliases (today: 'fr')."""
    import copy

    from wodcraft.catalog import load_catalog

    catalog = load_catalog()
    out = copy.deepcopy(document)

    def walk(node: dict) -> None:
        if node.get("type") == "movement":
            entry = catalog.movements.get(node.get("movement", ""))
            if entry:
                node["name"] = entry.display_name(lang)
        for child in node.get("items", []):
            walk(child)

    for section in out.get("sections", []):
        for block in section["workout"].get("blocks", []):
            walk(block)
    for block in out.get("blocks", []):
        walk(block)
    return out


def _session(session: dict, width: int) -> str:
    lines = [_title(session.get("title") or "Session")]
    head = " · ".join(x for x in (session.get("date"), session.get("time")) if x)
    if head:
        lines.append(head)
    for section in session.get("sections", []):
        lines.append("")
        lines.append(section["title"].upper())
        lines.append(_workout(section["workout"], width, skip_title=True))
    if session.get("estimate"):
        lines.append("")
        lines.append(f"Session estimate: {_range(session['estimate'])}")
    return "\n".join(lines).rstrip() + "\n"


def _workout(workout: dict, width: int, skip_title: bool = False) -> str:
    lines: list[str] = []
    if not skip_title and workout.get("title"):
        lines.append(_title(workout["title"]))
    meta = workout.get("meta") or {}
    for block in workout.get("blocks", []):
        lines += _block(block, 0, width)
    if meta.get("vest"):
        lines.append(f"Vest: {_load(meta['vest'])}")
    score = workout.get("score") or {}
    if score.get("type") and score["type"] != "none":
        label = SCORE_LABEL.get(score["type"], score["type"])
        if score.get("capped"):
            label += f" (capped: {SCORE_LABEL.get(score['capped'], score['capped'])})"
        lines.append(f"Score: {label}")
    estimate = workout.get("estimate")
    if estimate:
        lines.append(f"Estimate: {_range(estimate)}")
    for note in meta.get("notes", []):
        lines.append(f"Note: {note}")
    for stimulus in meta.get("stimulus", []):
        lines.append(f"Stimulus: {stimulus}")
    levels = workout.get("levels")
    if levels:
        lines.append("Levels: " + ", ".join(sorted(levels)))
    resolved = workout.get("resolved")
    if resolved:
        lines.append(f"[{resolved['category']} · {resolved['level']} · {resolved['units']}]")
    return "\n".join(lines)


def _title(title: str) -> str:
    return title.upper()


def _block(block: dict, depth: int, width: int) -> list[str]:
    kind = block.get("type")
    pad = "  " * depth
    if kind == "movement":
        return [pad + _movement(block, width - len(pad))]
    if kind == "rest":
        return [f"{pad}Rest {format_clock(block['seconds'])}"]
    head = _head(block)
    items = block.get("items", [])
    if head and block.get("type") in ("slot", "buy_in", "cash_out") and len(items) == 1 and items[0].get("type") == "movement":
        return [f"{pad}{head} {_movement(items[0], width - len(pad) - len(head) - 1)}"]
    lines = [pad + head] if head else []
    for item in items:
        lines += _block(item, depth + (1 if head else 0), width)
    return lines


def _head(block: dict) -> str:
    kind = block.get("type")
    parts: list[str] = []
    ladder = "-".join(str(r) for r in block.get("reps", []) or [])
    rounds = block.get("rounds")
    if kind == "for_time":
        core = ladder or (f"{rounds} rounds" if rounds else "")
        parts.append((core + " for time").strip() if core else "For time")
    elif kind == "amrap":
        parts.append(f"AMRAP {format_clock(block.get('duration_s', 0))}")
    elif kind == "emom":
        interval = int((block.get("interval_s") or 60) // 60)
        parts.append(("EMOM" if interval <= 1 else f"E{interval}MOM") + f" {format_clock(block.get('duration_s', 0))}")
    elif kind == "every":
        parts.append(f"Every {format_clock(block.get('interval_s', 0))} x {rounds}")
    elif kind == "tabata":
        parts.append("Tabata" + ("" if (rounds or 8) == 8 else f" {rounds}"))
    elif kind == "death_by":
        parts.append("Death by")
    elif kind == "max_load":
        parts.append("Max load")
    elif kind == "rounds":
        parts.append(f"{rounds} rounds")
    elif kind == "ladder":
        parts.append(ladder + (" …" if block.get("reps_open") else ""))
    elif kind == "slot":
        slot = block.get("slot")
        return {"odd": "Odd:", "even": "Even:"}.get(str(slot), f"Min {slot}:")
    elif kind == "buy_in":
        return "Buy-in:"
    elif kind == "cash_out":
        return "Cash-out:"
    if block.get("cap_s"):
        parts.append(f"cap {format_clock(block['cap_s'])}")
    if block.get("teams"):
        parts.insert(0, f"Teams of {block['teams']}")
    used = block.get("used")
    if used:
        parts.append(f"[{used['title'] or used['path']}]")
    return " · ".join(parts)


def _movement(item: dict, width: int, dots: bool = True) -> str:
    left = " ".join(x for x in (_quantity(item.get("quantity")), item.get("name", item.get("movement", "?"))) if x)
    right_parts = []
    if item.get("sets"):
        right_parts.append(_sets(item["sets"]))
    if item.get("load"):
        right_parts.append(_load(item["load"]))
    elif item.get("percent"):
        right_parts.append(f"{fmt_num(_one(item['percent']['value']))}%")
    if item.get("height"):
        right_parts.append(_height(item["height"]))
    if item.get("rpe"):
        right_parts.append(f"RPE {fmt_num(_one(item['rpe']))}")
    if item.get("modifiers"):
        right_parts.append("(" + ", ".join(item["modifiers"]) + ")")
    right = " ".join(right_parts)
    if not right:
        return left
    if not dots or width <= 0:
        return f"{left} {right}"
    filler = max(1, width - len(left) - len(right) - 2)
    return f"{left} {'.' * filler} {right}"


def _one(amount) -> float:
    if isinstance(amount, dict):
        return float(next(iter(amount.values())))
    return float(amount)


def _pair(amount, unit: str) -> str:
    if isinstance(amount, dict) and "men" in amount:
        return f"{fmt_num(amount['men'])}/{fmt_num(amount['women'])} {unit}"
    return f"{fmt_num(_one(amount))} {unit}"


def _quantity(quantity: dict | None) -> str:
    if not quantity:
        return ""
    kind = quantity.get("kind")
    if kind == "max":
        return "max"
    if kind == "reps":
        value = quantity["reps"]
        return f"{fmt_num(value['men'])}/{fmt_num(value['women'])}" if isinstance(value, dict) and "men" in value else fmt_num(_one(value))
    if kind == "distance":
        return _pair(quantity.get("written", quantity.get("m")), quantity.get("unit", "m"))
    if kind == "calories":
        return _pair(quantity["cal"], "cal")
    if kind == "time":
        return format_clock(_one(quantity["s"]))
    return ""


def _load(load: dict) -> str:
    if "value" in load:  # resolved for an athlete
        return f"{fmt_num(load['value'])} {load['unit']}"
    unit = load.get("unit", "kg")
    return _pair(load.get("written", load.get(unit)), unit)


def _height(height: dict) -> str:
    if "value" in height:
        return f"{fmt_num(height['value'])} {height['unit']}"
    unit = height.get("unit", "cm")
    return _pair(height.get("written", height.get(unit)), unit)


def _sets(sets: dict) -> str:
    reps = sets.get("reps", [])
    if reps and len(set(reps)) == 1:
        return f"{len(reps)}x{reps[0]}"
    return "-".join(str(r) for r in reps)


def _range(estimate: dict) -> str:
    low, high = estimate.get("min_s", 0), estimate.get("max_s", 0)
    if abs(high - low) < 30:
        return format_clock(low)
    return f"{format_clock(low)}–{format_clock(high)}"
