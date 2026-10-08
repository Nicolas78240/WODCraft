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


TOTAL_LABEL = {
    "time": "total time",
    "rounds+reps": "total rounds + reps",
    "rounds": "total rounds",
    "reps": "total reps",
    "load": "total load",
    "distance": "total distance",
    "calories": "total calories",
}

WORDS = {
    "fr": {
        "or": "ou",
        "there and back": "aller-retour",
        "Max load": "Charge max",
        "attempt": "essai",
        "attempts": "essais",
        "Rest": "Repos",
        "between attempts": "entre les essais",
        "best attempt": "meilleur essai",
        "best attempt of each lift": "meilleur essai de chaque barre",
        # the labels in front of the lines under the workout
        "Cap": "Cap",
        "Score": "Score",
        "Estimate": "Durée",
        "Session estimate": "Durée de la séance",
        "Vest": "Lest",
        "Note": "Note",
        "Stimulus": "Stimulus",
        "Levels": "Niveaux",
        "Adapted": "Adapté",
        "capped": "cap atteint",
        # what is scored
        "time": "temps",
        "rounds + reps": "tours + répétitions",
        "rounds": "tours",
        "reps": "répétitions",
        "load": "charge",
        "distance": "distance",
        "calories": "calories",
        "one score per part": "un score par partie",
        "total time": "total des temps",
        "total rounds + reps": "total des tours + répétitions",
        "total rounds": "total des tours",
        "total reps": "total des répétitions",
        "total load": "total des charges",
        "total distance": "distance totale",
        "total calories": "total des calories",
    }
}


def word(text: str, lang: str = "en") -> str:
    """The words of the board in another language ('or', 'there and back', 'Max load', 'Score'…)."""
    return WORDS.get(lang, {}).get(text, text)


def label(text: str, lang: str = "en") -> str:
    """'Score:' — or 'Score :' in French, which puts a space before the colon."""
    return word(text, lang) + (" :" if lang == "fr" else ":")


def score_text(workout: dict, lang: str = "en") -> str:
    """What the score counts: 'load', 'total load (best attempt of each lift)'…"""
    score = workout.get("score") or {}
    kind = score.get("type", "none")
    if score.get("aggregate") == "sum":
        unit = score.get("unit", kind)
        text = word(TOTAL_LABEL.get(unit, unit), lang)
    else:
        unit = kind
        text = word(SCORE_LABEL.get(kind, kind), lang)
    attempts = any(block.get("type") == "max_load" and block.get("attempts") for block in workout.get("blocks", []))
    if unit == "load" and attempts:  # 1.2: the best of the attempts counts, for each lift
        text += f" ({word('best attempt of each lift' if kind == 'multi' else 'best attempt', lang)})"
    return text


def render(document: dict, width: int = 46, lang: str = "en", show_profile: bool = True) -> str:
    if lang != "en":
        document = localize(document, lang)
    if document.get("kind") == "session":
        return _session(document, width, show_profile, lang)
    return _workout(document, width, show_profile=show_profile, lang=lang)


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
        for child in node.get("items", []) + node.get("or", []):
            walk(child)

    for section in out.get("sections", []):
        for block in section["workout"].get("blocks", []):
            walk(block)
    for block in out.get("blocks", []):
        walk(block)
    return out


def _session(session: dict, width: int, show_profile: bool = True, lang: str = "en") -> str:
    lines = [_title(session.get("title") or "Session")]
    head = " · ".join(x for x in (session.get("date"), session.get("time")) if x)
    if head:
        lines.append(head)
    for section in session.get("sections", []):
        lines.append("")
        lines.append(section["title"].upper())
        lines.append(_workout(section["workout"], width, skip_title=True, show_profile=show_profile, lang=lang))
    if session.get("estimate"):
        lines.append("")
        lines.append(f"{label('Session estimate', lang)} {_range(session['estimate'])}")
    return "\n".join(lines).rstrip() + "\n"


def _workout(workout: dict, width: int, skip_title: bool = False, show_profile: bool = True, lang: str = "en") -> str:
    lines: list[str] = []
    if not skip_title and workout.get("title"):
        lines.append(_title(workout["title"]))
    if workout.get("cap_s"):  # a cap on the whole workout has its own line (1.2)
        lines.append(f"{label('Cap', lang)} {format_clock(workout['cap_s'])}")
    meta = workout.get("meta") or {}
    body: list[str] = []
    for block in workout.get("blocks", []):
        body += _block(block, 0, width, lang)
    if workout.get("team") and body:
        body[0] = f"Teams of {workout['team']['size']} · {body[0]}"
    lines += body
    if meta.get("vest"):
        lines.append(f"{label('Vest', lang)} {_load(meta['vest'])}")
    score = workout.get("score") or {}
    if score.get("type") and score["type"] != "none":
        text = score_text(workout, lang)
        if score.get("capped"):
            capped = word(SCORE_LABEL.get(score["capped"], score["capped"]), lang)
            text += f" ({label('capped', lang)} {capped})"
        lines.append(f"{label('Score', lang)} {text}")
    estimate = workout.get("estimate")
    if estimate:
        lines.append(f"{label('Estimate', lang)} {_range(estimate)}")
    for note in meta.get("notes", []):
        lines.append(f"{label('Note', lang)} {note}")
    for stimulus in meta.get("stimulus", []):
        lines.append(f"{label('Stimulus', lang)} {stimulus}")
    levels = workout.get("levels")
    if levels:
        lines.append(f"{label('Levels', lang)} " + ", ".join(sorted(levels)))
    changes = [_adaptation(op, lang) for op in workout.get("adapted") or [] if op.get("movement")]
    if changes:
        lines.append(f"{label('Adapted', lang)} " + "; ".join(changes))
    resolved = workout.get("resolved") if show_profile else None
    if resolved:
        level = resolved["level"] + (" + adapted" if resolved.get("adapted") else "")
        lines.append(f"[{resolved['category']} · {level} · {resolved['units']}]")
    return "\n".join(lines)


def _adaptation(operation: dict, lang: str = "en") -> str:
    """One change of the athlete's 'Adapted:' block: 'Bar muscle-up -> 2x Chest-to-bar pull-up'."""
    from wodcraft.catalog import load_catalog

    catalog = load_catalog()

    def name(identifier: str) -> str:
        entry = catalog.movements.get(identifier)
        return entry.display_name(lang) if entry else identifier

    source = name(operation["movement"])
    target = name(operation.get("replace_with", operation["movement"]))
    amount = _quantity(operation.get("quantity")) or (f"{fmt_num(operation['factor'])}x" if operation.get("factor") else "")
    changed = " ".join(x for x in (amount, target) if x)
    return changed if changed == source else f"{source} -> {changed}"


def _title(title: str) -> str:
    return title.upper()


def _block(block: dict, depth: int, width: int, lang: str = "en") -> list[str]:
    kind = block.get("type")
    pad = "  " * depth
    if kind == "movement":
        return [pad + _movement(block, width - len(pad), lang=lang)]
    if kind == "rest":
        return [f"{pad}{word('Rest', lang)} {format_clock(block['seconds'])}"]
    head = _head(block, lang)
    items = block.get("items", [])
    if head and block.get("type") in ("slot", "buy_in", "cash_out") and len(items) == 1 and items[0].get("type") == "movement":
        return [f"{pad}{head} {_movement(items[0], width - len(pad) - len(head) - 1, lang=lang)}"]
    lines = [pad + head] if head else []
    for index, item in enumerate(items):
        inner = _block(item, depth + (1 if head else 0), width, lang)
        if kind == "max_load" and block.get("attempts") and item.get("type") == "rest" and index == len(items) - 1:
            inner = [f"{inner[0]} {word('between attempts', lang)}"]  # SPEC §8: between the attempts
        lines += inner
    return lines


def _head(block: dict, lang: str = "en") -> str:
    kind = block.get("type")
    parts: list[str] = []
    ladder = "-".join(str(r) for r in block.get("reps", []) or [])
    rounds = block.get("rounds")
    if kind == "for_time":
        core = ladder + (" …" if block.get("reps_open") else "") if ladder else (f"{rounds} rounds" if rounds else "")
        parts.append((core + " for time").strip() if core else "For time")
    elif kind == "amrap":
        parts.append(f"AMRAP {format_clock(block.get('duration_s', 0))}")
        if ladder:  # a ladder merged into its AMRAP (SPEC §13): the reps still belong on the board
            parts.append(ladder + (" …" if block.get("reps_open") else ""))
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
        parts.append(word("Max load", lang))
        attempts = block.get("attempts")
        if attempts:
            parts.append(f"{attempts} {word('attempt' if attempts == 1 else 'attempts', lang)}")
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
    if block.get("there_and_back"):
        parts.append(word("there and back", lang))
    if block.get("teams"):
        parts.insert(0, f"Teams of {block['teams']}")
    used = block.get("used")
    if used:
        parts.append(f"[{used['title'] or used['path']}]")
    return " · ".join(parts)


def _movement(item: dict, width: int, dots: bool = True, lang: str = "en") -> str:
    if item.get("or"):  # an alternative: every option in full, joined by "or"
        options = [_movement({k: v for k, v in item.items() if k != "or"}, 0, dots=False)]
        options += [_movement(option, 0, dots=False) for option in item["or"]]
        return f" {word('or', lang)} ".join(options)
    quantity = _quantity(item.get("quantity")) or (f"{fmt_num(item['factor'])}x" if item.get("factor") else "")
    left = " ".join(x for x in (quantity, item.get("name", item.get("movement", "?"))) if x)
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
