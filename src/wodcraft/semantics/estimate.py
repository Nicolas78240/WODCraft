"""Duration estimates and the plausibility warnings that depend on them (SPEC §15)."""

from __future__ import annotations

from wodcraft.catalog import Catalog
from wodcraft.diagnostics import DiagnosticBag, Span

FATIGUE = 1.25  # transitions, breathing, set breaks
SPREAD = 0.4  # ± around the central estimate: catalog paces describe an average Rx athlete
LOAD_SENSITIVITY = 0.9  # a movement at its Rx load costs about twice its unloaded cadence
MAX_LOAD_FACTOR = 3.5
REFERENCE_KG = {"barbell": 50.0, "dumbbell": 22.5, "kettlebell": 24.0, "medicine_ball": 9.0, "sandbag": 45.0}
DEFAULT_REP_PACE = 3.0
DEFAULT_SET_REST = 120.0  # strength work: rest between sets unless the source says otherwise


def _pick(amount, category: str = "men") -> float:
    if isinstance(amount, dict):
        return float(amount.get(category, next(iter(amount.values()))))
    return float(amount)


def load_factor(item: dict, entry) -> float:
    """Heavier than the usual Rx load means slower reps, and far heavier means singles."""
    load = item.get("load")
    if not load or entry is None:
        return 1.0
    kg = _pick(load.get("kg", 0))
    reference = None
    if entry.rx and entry.rx.get("unit", "kg") == "kg":
        reference = float(entry.rx.get("men", 0)) or None
    reference = reference or REFERENCE_KG.get(entry.equipment)
    if not reference or not kg:
        return 1.0
    return min(MAX_LOAD_FACTOR, 1.0 + LOAD_SENSITIVITY * (kg / reference))


def item_seconds(item: dict, catalog: Catalog) -> float:
    """Work time for one movement item, ignoring rest between sets."""
    entry = catalog.movements.get(item.get("movement", ""))
    quantity = item.get("quantity") or {}
    kind = quantity.get("kind")
    if kind == "max":
        return 0.0
    if kind == "time":
        return _pick(quantity.get("s", 0))
    pace = None
    if entry is not None:
        pace = entry.pace_for(kind or "reps")
    if kind == "distance":
        return _pick(quantity.get("m", 0)) * (pace or 0.3)
    if kind == "calories":
        return _pick(quantity.get("cal", 0)) * (pace or 3.5)
    reps = _pick(quantity.get("reps", 0)) if kind == "reps" else 0.0
    per_rep = (pace or DEFAULT_REP_PACE) * load_factor(item, entry)
    sets = item.get("sets")
    if sets:
        reps = float(sum(sets["reps"]))
        rest = _declared_rest(item)
        rest = DEFAULT_SET_REST if rest is None else rest
        return reps * per_rep + rest * max(0, len(sets["reps"]) - 1)
    return reps * per_rep


def _declared_rest(item: dict) -> float | None:
    """A "(rest 2:00)" modifier overrides the default rest between sets."""
    for modifier in item.get("modifiers", []):
        if modifier.startswith("rest "):
            from wodcraft.syntax.units import parse_clock

            text = modifier.split(" ", 1)[1].strip()
            try:
                return parse_clock(text) if ":" in text else float(text.rstrip("s "))
            except ValueError:
                return None
    return None


def block_seconds(block: dict, catalog: Catalog) -> float:
    kind = block.get("type")
    if kind == "rest":
        return float(block.get("seconds", 0))
    if kind == "movement":
        return item_seconds(block, catalog)
    if kind in ("amrap", "emom", "tabata") and block.get("duration_s"):
        return float(block["duration_s"])
    if kind == "every" and block.get("interval_s") and block.get("rounds"):
        return float(block["interval_s"]) * float(block["rounds"])
    if kind == "tabata":
        return float(block.get("rounds", 8)) * 30.0

    items = block.get("items", [])
    # "Rest" as the last item of a repeated block happens between rounds only
    rounds = float(block.get("rounds") or 1)
    reps = block.get("reps")
    body = sum(block_seconds(i, catalog) for i in items)
    trailing_rest = items[-1].get("seconds", 0) if items and items[-1].get("type") == "rest" else 0

    if reps:
        # a rep ladder: movements without their own quantity take each ladder value
        per_rep_cost = 0.0
        fixed = 0.0
        for item in items:
            if item.get("type") == "movement" and not item.get("quantity"):
                entry = catalog.movements.get(item.get("movement", ""))
                pace = (entry.pace_for("reps") if entry else None) or DEFAULT_REP_PACE
                per_rep_cost += pace * load_factor(item, entry)
            else:
                fixed += block_seconds(item, catalog)
        return sum(reps) * per_rep_cost + fixed * len(reps)
    total = body * rounds - trailing_rest  # the last round's trailing rest is not performed
    return max(0.0, total)


def estimate_workout(workout: dict, catalog: Catalog, diags: DiagnosticBag, file: str | None) -> dict | None:
    blocks = workout.get("blocks", [])
    if not blocks:
        return None
    total = 0.0
    fixed = False
    for block in blocks:
        kind = block.get("type")
        seconds = block_seconds(block, catalog)
        if kind in ("amrap", "emom", "every", "tabata") or (kind == "rest"):
            fixed = True
            total += seconds
        else:
            total += seconds * FATIGUE
        _interval_warning(block, catalog, diags, file)
    if total <= 0:
        return None
    low, high = (total, total) if fixed and len(blocks) == 1 else (total * (1 - SPREAD), total * (1 + SPREAD))
    cap = blocks[0].get("cap_s") or workout.get("meta", {}).get("cap_s")
    if cap and low > cap:
        source = blocks[0].get("source", {"line": 1, "col": 1})
        diags.add(
            "W103",
            f"Estimated duration ({_mmss(low)}–{_mmss(high)}) is longer than the cap ({_mmss(cap)}).",
            Span(source["line"], source["col"], file=file),
            "raise the cap or cut volume",
        )
    return {"min_s": round(low), "max_s": round(high), "capped_s": cap}


def _interval_warning(block: dict, catalog: Catalog, diags: DiagnosticBag, file: str | None) -> None:
    kind = block.get("type")
    if kind not in ("emom", "every"):
        for child in block.get("items", []):
            _interval_warning(child, catalog, diags, file)
        return
    interval = float(block.get("interval_s") or 60)
    slots = [i for i in block.get("items", []) if i.get("type") == "slot"]
    groups = [i.get("items", []) for i in slots] if slots else [[i for i in block.get("items", []) if i.get("type") != "slot"]]
    for items in groups:
        work = sum(block_seconds(i, catalog) for i in items)
        if work > interval * 0.9:
            source = (items[0] if items else block).get("source", {"line": 1, "col": 1})
            diags.add(
                "W102",
                f"About {round(work)} s of work in a {round(interval)} s interval.",
                Span(source["line"], source["col"], file=file),
                "lower the reps or lengthen the interval",
            )
    for child in block.get("items", []):
        _interval_warning(child, catalog, diags, file)


def _mmss(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"
