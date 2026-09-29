"""Resolve a compiled workout for one athlete: level, category, units, percentages (SPEC §14)."""

from __future__ import annotations

import copy

from wodcraft.catalog import Equivalences, load_equivalences
from wodcraft.profile import Profile
from wodcraft.syntax.units import CM_PER_IN, KG_PER_LB

PLATE_STEP = {"kg": 2.5, "lb": 5.0}


def resolve(workout: dict, profile: Profile, equivalences: Equivalences | None = None) -> dict:
    eq = equivalences or load_equivalences()
    out = copy.deepcopy(workout)
    if out.get("kind") == "session":
        out["sections"] = [dict(s, workout=resolve(s["workout"], profile, eq)) for s in out.get("sections", [])]
        return out

    level = _applied_level(out, profile)
    operations = (out.get("levels") or {}).get(level, []) if level else []
    adapted = out.pop("adapted", None)
    stages = [operations, adapted or []]  # the level first, then the athlete's adaptation (§9.1)
    meta = out.setdefault("meta", {})
    for operation in operations + (adapted or []):
        if "meta" in operation:
            for key, value in operation["meta"].items():
                if value is None:
                    meta.pop(key, None)
                else:
                    meta[key] = value
    out["blocks"] = [_block(b, stages, profile, eq) for b in out.get("blocks", [])]
    if meta.get("vest"):
        meta["vest"] = _flatten_load(meta["vest"], profile, eq)
    out["resolved"] = {"category": profile.category, "level": level or "rx", "units": profile.units}
    if adapted is not None:
        out["resolved"]["adapted"] = True
    out.pop("levels", None)
    return out


def _applied_level(workout: dict, profile: Profile) -> str | None:
    available = workout.get("levels") or {}
    for level in profile.levels_to_try():
        if level == "rx":
            return None
        if level in available:
            return level
    return None


def _block(block: dict, stages: list[list[dict]], profile: Profile, eq: Equivalences) -> dict:
    if block.get("type") == "movement":
        return _movement(block, stages, profile, eq)
    if "items" in block:
        block["items"] = [_block(i, stages, profile, eq) for i in block["items"]]
    return block


def _movement(item: dict, stages: list[list[dict]], profile: Profile, eq: Equivalences) -> dict:
    for operations in stages:
        _apply(item, operations)
    _flatten(item, profile, eq)
    if "or" in item:  # every option of an alternative is resolved the same way
        item["or"] = [_movement(option, stages, profile, eq) for option in item["or"]]
    return item


def _apply(item: dict, operations: list[dict]) -> None:
    """The first operation that matches the movement adapts it."""
    for operation in operations:
        if operation.get("movement") != item.get("movement"):
            continue
        when = operation.get("when")
        if when and not _matches(item, when):
            continue
        if operation.get("replace_with"):
            item["movement"] = operation["replace_with"]
            item["name"] = operation.get("name", operation["replace_with"])
            item.pop("load", None)
            item.pop("height", None)
        for key in ("load", "height", "percent", "rpe", "bodyweight"):
            if key in operation:
                item[key] = copy.deepcopy(operation[key])
        if "quantity" in operation:
            item["quantity"] = copy.deepcopy(operation["quantity"])
        if "factor" in operation:
            _multiply(item, operation["factor"])
        break


def _flatten(item: dict, profile: Profile, eq: Equivalences) -> None:
    if "quantity" in item:
        item["quantity"] = _flatten_quantity(item["quantity"], profile)
    if "load" in item:
        item["load"] = _flatten_load(item["load"], profile, eq)
    if "height" in item:
        item["height"] = _flatten_height(item["height"], profile, eq)
    if "percent" in item:
        computed = _from_percent(item["percent"], profile)
        if computed is not None:
            item["load"] = computed
    if "bodyweight" in item and profile.bodyweight_kg:
        factor = _pick(item["bodyweight"], profile)
        item["load"] = _round_load({"kg": profile.bodyweight_kg * factor}, profile, eq)


def _multiply(item: dict, factor: float) -> None:
    """ "A -> 2x B": the quantity is multiplied; a movement that takes its reps from a ladder keeps
    the factor, and does factor × the ladder value."""
    quantity = item.get("quantity")
    if not quantity or quantity.get("kind") == "max":
        item["factor"] = _tidy(factor * item.get("factor", 1))
        return
    for key in ("reps", "cal", "s", "m", "written"):
        if key in quantity:
            value = quantity[key]
            quantity[key] = {k: _tidy(v * factor) for k, v in value.items()} if isinstance(value, dict) else _tidy(value * factor)


def _matches(item: dict, when: dict) -> bool:
    for key, expected in when.items():
        actual = item.get(key)
        if not isinstance(actual, dict) or not isinstance(expected, dict):
            return False
        if actual.get("written") != expected.get("written") or actual.get("unit") != expected.get("unit"):
            return False
    return True


def _pick(amount, profile: Profile) -> float:
    if isinstance(amount, dict):
        return float(amount.get(profile.category, next(iter(amount.values()))))
    return float(amount)


def _flatten_quantity(quantity: dict, profile: Profile) -> dict:
    out = dict(quantity)
    for key in ("reps", "cal", "s", "m", "written"):
        if key in out:
            out[key] = _pick(out[key], profile)
    return out


def _flatten_load(load: dict, profile: Profile, eq: Equivalences) -> dict:
    kg = _pick(load.get("kg", 0), profile)
    lb = _pick(load.get("lb", 0), profile) if "lb" in load else None
    value = kg if profile.units == "kg" else (lb if lb is not None else kg / KG_PER_LB)
    return {"value": _tidy(value), "unit": profile.units, "kg": _tidy(kg)}


def _flatten_height(height: dict, profile: Profile, eq: Equivalences) -> dict:
    cm = _pick(height.get("cm", 0), profile)
    inches = _pick(height.get("in", 0), profile) if "in" in height else cm / CM_PER_IN
    imperial = profile.units == "lb"
    return {"value": _tidy(inches if imperial else cm), "unit": "in" if imperial else "cm", "cm": _tidy(cm)}


def _from_percent(percent: dict, profile: Profile) -> dict | None:
    reference = profile.one_rm.get(percent.get("of", ""))
    if not reference:
        return None
    share = _pick(percent.get("value", 0), profile) / 100.0
    return _round_load({"kg": reference * share}, profile, None)


def _round_load(load: dict, profile: Profile, eq: Equivalences | None) -> dict:
    kg = load["kg"]
    if profile.units == "lb":
        pounds = kg / KG_PER_LB
        step = PLATE_STEP["lb"]
        rounded = round(pounds / step) * step
        return {"value": _tidy(rounded), "unit": "lb", "kg": _tidy(rounded * KG_PER_LB)}
    step = PLATE_STEP["kg"]
    rounded = round(kg / step) * step
    return {"value": _tidy(rounded), "unit": "kg", "kg": _tidy(rounded)}


def _tidy(value: float) -> float:
    value = round(float(value), 2)
    return int(value) if float(value).is_integer() else value
