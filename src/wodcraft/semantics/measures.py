"""Normalization of written values into the compiled JSON representation (SPEC §13)."""

from __future__ import annotations

from wodcraft.catalog import Equivalences
from wodcraft.syntax.ast import Dual
from wodcraft.syntax.units import CM_PER_IN, KG_PER_LB, KG_PER_POOD, M_PER

Amount = float | dict[str, float]
Measure = dict[str, "Amount | str"]  # normalized units plus the unit written in the source


def amount(value: Dual) -> Amount:
    """A single number, or {"men": …, "women": …} when the value was written as a dual."""
    if value.is_dual:
        return {"men": _round(value.men), "women": _round(value.women)}
    return _round(value.men)


def map_amount(value: Amount, fn) -> Amount:
    if isinstance(value, dict):
        return {k: _round(fn(v)) for k, v in value.items()}
    return _round(fn(value))


def pick(value: Amount, category: str) -> float:
    return value[category] if isinstance(value, dict) else value


def _round(value: float) -> float:
    rounded = round(float(value), 3)
    return int(rounded) if float(rounded).is_integer() else rounded


def load_to_json(value: Dual, unit: str, eq: Equivalences) -> Measure:
    """Loads are exposed in kg and lb, using the equivalence table first."""
    written = amount(value)
    if unit == "pood":
        kg = map_amount(written, lambda v: v * KG_PER_POOD)
        return {"kg": kg, "lb": map_amount(kg, lambda v: _kg_to_lb(v, eq)), "unit": "pood", "written": written}
    if unit == "lb":
        kg = map_amount(written, lambda v: _lb_to_kg(v, eq))
        return {"kg": kg, "lb": written, "unit": "lb", "written": written}
    kg = written
    return {"kg": kg, "lb": map_amount(kg, lambda v: _kg_to_lb(v, eq)), "unit": "kg", "written": written}


def height_to_json(value: Dual, unit: str, eq: Equivalences) -> Measure:
    written = amount(value)
    if unit == "in":
        cm = map_amount(written, lambda v: eq.in_to_cm(v) or round(v * CM_PER_IN))
        return {"cm": cm, "in": written, "unit": "in", "written": written}
    cm = written
    return {"cm": cm, "in": map_amount(cm, lambda v: eq.cm_to_in(v) or round(v / CM_PER_IN)), "unit": "cm", "written": written}


def distance_to_json(value: Dual, unit: str) -> Measure:
    factor = M_PER[unit]
    return {"m": map_amount(amount(value), lambda v: v * factor), "unit": unit, "written": amount(value)}


def _kg_to_lb(kg: float, eq: Equivalences) -> float:
    exact = eq.kg_to_lb(kg)
    return exact if exact is not None else round(kg / KG_PER_LB)


def _lb_to_kg(lb: float, eq: Equivalences) -> float:
    exact = eq.lb_to_kg(lb)
    return exact if exact is not None else round(lb * KG_PER_LB * 2) / 2
