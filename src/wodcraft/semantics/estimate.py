"""Duration estimates and the plausibility warnings that depend on them (SPEC §15)."""

from __future__ import annotations

from wodcraft.catalog import Catalog
from wodcraft.diagnostics import DiagnosticBag, Span

FATIGUE = 1.6  # transitions, breathing, set breaks and the reps that fall apart late
SPREAD = 0.3  # ± around the central estimate: catalog paces describe an average Rx athlete
# Catalog paces describe an average Rx athlete, so the Rx load costs exactly its pace: the factor
# is 1 there, drops a little when lighter, and climbs steeply when the bar gets heavy.
LOAD_SENSITIVITY = 1.8
MAX_LOAD_FACTOR = 3.5
MIN_LOAD_FACTOR = 0.8
CAP_TOLERANCE = 2.5  # a hard cap is a deliberate cut-off; warn only when the volume is wildly past it
REFERENCE_KG = {"barbell": 50.0, "dumbbell": 22.5, "kettlebell": 24.0, "medicine_ball": 9.0, "sandbag": 45.0}
DEFAULT_REP_PACE = 3.0
DEFAULT_SET_REST = 120.0  # strength work: rest between sets unless the source says otherwise
ATTEMPT_SECONDS = 30.0  # a heavy attempt: chalk, set-up, the lift and the plates — not the rep pace
BUILD_UP_EFFORTS = 5  # "Max load" without attempts: a typical build-up to the heaviest load
FIXED = ("amrap", "emom", "every", "tabata")  # the clock, not the volume, sets their duration


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
    ratio = kg / reference
    if ratio <= 1:
        return max(MIN_LOAD_FACTOR, 0.8 + 0.2 * ratio)
    return min(MAX_LOAD_FACTOR, 1.0 + LOAD_SENSITIVITY * (ratio - 1))


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
    per_rep = (pace or DEFAULT_REP_PACE) * load_factor(item, entry) + declared_hold(item)
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


def declared_hold(item: dict) -> float:
    """A "(hold 10 s)" modifier holds every rep: its duration adds to each rep."""
    for modifier in item.get("modifiers", []):
        words = modifier.split(" ", 1)
        if words[0] != "hold" or len(words) == 1:
            continue
        from wodcraft.syntax.units import parse_clock

        text = words[1].strip()
        try:
            if ":" in text:
                return parse_clock(text)
            number, _, unit = text.partition(" ")
            return float(number) * (60.0 if unit.strip() == "min" else 1.0)
        except ValueError:
            return 0.0
    return 0.0


def block_seconds(block: dict, catalog: Catalog) -> float:
    kind = block.get("type")
    if kind == "rest":
        return float(block.get("seconds", 0))
    if kind == "movement":
        return item_seconds(block, catalog)
    if kind == "tabata":
        movements = [i for i in block.get("items", []) if i.get("type") != "rest"] or [None]
        return float(block.get("rounds", 8)) * 30.0 * len(movements)
    if kind in ("amrap", "emom") and block.get("duration_s"):
        return float(block["duration_s"])
    if kind == "every" and block.get("interval_s") and block.get("rounds"):
        return float(block["interval_s"]) * float(block["rounds"])

    items = block.get("items", [])
    if kind == "max_load" and builds_up(block):
        return _max_load_seconds(block, catalog)
    if block.get("there_and_back"):
        items = items + items[-2::-1]  # the list, then back without its last line (SPEC §5)
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
                per_rep_cost += (pace * load_factor(item, entry) + declared_hold(item)) * item.get("factor", 1)
            else:
                fixed += block_seconds(item, catalog)
        return sum(reps) * per_rep_cost + fixed * len(reps)
    total = body * rounds - trailing_rest  # the last round's trailing rest is not performed
    return max(0.0, total)


def builds_up(block: dict) -> bool:
    """A Max load whose lifts carry no sets is a build-up: efforts towards the heaviest load (1.2)."""
    movements = [i for i in block.get("items", []) if i.get("type") == "movement"]
    return bool(movements) and not any(i.get("sets") for i in movements)


def _efforts(block: dict) -> tuple[int, float]:
    """The efforts of a build-up and the rest between two of them: the attempts written on the line
    (or a typical build-up), and the rest written last in the block (or the usual rest between sets).
    Like the trailing rest of rounds (SPEC §8), it comes between the efforts, not after the last."""
    items = block.get("items", [])
    efforts = int(block.get("attempts") or BUILD_UP_EFFORTS)
    trailing = items[-1].get("seconds") if items and items[-1].get("type") == "rest" else None
    return efforts, DEFAULT_SET_REST if trailing is None else float(trailing)


def _max_load_seconds(block: dict, catalog: Catalog) -> float:
    efforts, rest = _efforts(block)
    work = sum(max(item_seconds(i, catalog), ATTEMPT_SECONDS) for i in block.get("items", []) if i.get("type") == "movement")
    return efforts * work + rest * (efforts - 1)


def rest_seconds(block: dict) -> float:
    """Prescribed rest inside a block: it is wall-clock time, so fatigue does not stretch it."""
    kind = block.get("type")
    if kind == "rest":
        return float(block.get("seconds", 0))
    if kind == "max_load" and builds_up(block):
        efforts, between = _efforts(block)
        return between * (efforts - 1)
    if kind == "movement":
        sets = block.get("sets")
        if sets:
            rest = _declared_rest(block)
            rest = DEFAULT_SET_REST if rest is None else rest
            return rest * max(0, len(sets["reps"]) - 1)
        return 0.0
    items = block.get("items", [])
    if block.get("there_and_back"):
        items = items + items[-2::-1]
    inner = sum(rest_seconds(i) for i in items)
    rounds = float(block.get("rounds") or 1)
    reps = block.get("reps")
    if reps:
        return inner * len(reps)
    trailing = items[-1].get("seconds", 0) if items and items[-1].get("type") == "rest" else 0
    return max(0.0, inner * rounds - trailing)


def effort_seconds(block: dict, catalog: Catalog) -> float:
    """The central estimate of one block: its work stretched by fatigue, its prescribed rest as is."""
    seconds = block_seconds(block, catalog)
    rest = rest_seconds(block)
    return max(0.0, seconds - rest) * FATIGUE + rest


def estimate_workout(workout: dict, catalog: Catalog, diags: DiagnosticBag, file: str | None) -> dict | None:
    blocks = workout.get("blocks", [])
    if not blocks:
        return None
    total = 0.0
    fixed = False
    for block in blocks:
        kind = block.get("type")
        seconds = block_seconds(block, catalog)
        if block.get("reps_open") and block.get("cap_s"):
            # an open ladder runs until the cap: the clock, not the volume, sets the duration
            fixed = True
            total += float(block["cap_s"])
            continue
        if kind in FIXED or (kind == "rest"):
            fixed = True
            total += seconds
        else:
            total += effort_seconds(block, catalog)
        _interval_warning(block, catalog, diags, file)
    if total <= 0:
        return None
    low, high = (total, total) if fixed and len(blocks) == 1 else (total * (1 - SPREAD), total * (1 + SPREAD))
    cap = workout_cap(workout, catalog)
    # a cap is a cut-off, not a target: only warn when the work is far beyond it
    if cap and low > cap * CAP_TOLERANCE:
        source = blocks[0].get("source", {"line": 1, "col": 1})
        diags.add(
            "W103",
            f"Estimated duration ({_mmss(low)}–{_mmss(high)}) is longer than the cap ({_mmss(cap)}).",
            Span(source["line"], source["col"], file=file),
            "raise the cap or cut volume",
        )
    return {"min_s": round(low), "max_s": round(high), "capped_s": cap}


def workout_cap(workout: dict, catalog: Catalog) -> float | None:
    """The time cap of the whole workout: its own (1.2), or the caps of its blocks one after the other
    — with the rest between them — when several blocks carry one. A single capped block keeps its cap."""
    if workout.get("cap_s"):
        return float(workout["cap_s"])
    blocks = workout.get("blocks", [])
    if not blocks:
        return None
    if sum(1 for block in blocks if block.get("cap_s")) < 2:
        return blocks[0].get("cap_s") or workout.get("meta", {}).get("cap_s")
    total = 0.0
    for block in blocks:
        if block.get("cap_s"):
            total += float(block["cap_s"])
        elif block.get("type") == "rest":
            total += float(block.get("seconds", 0))
        elif block.get("type") in FIXED:
            total += block_seconds(block, catalog)
        else:
            return None  # a block without a cap: the workout as a whole is not capped
    return total


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
        work = sum(block_seconds(i, catalog) for i in items if i.get("type") != "rest")
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
