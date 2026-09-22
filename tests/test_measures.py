"""Normalisation of loads, heights and distances (SPEC §13)."""

from __future__ import annotations

import pytest

from conftest import first_item
from wodcraft.catalog import Equivalences
from wodcraft.semantics import measures
from wodcraft.syntax.ast import Dual
from wodcraft.syntax.units import CM_PER_IN, KG_PER_LB, KG_PER_POOD, M_PER

# --------------------------------------------------------------------------- amounts


def test_a_single_value_stays_a_number():
    assert measures.amount(Dual.single(21)) == 21


def test_a_dual_value_becomes_men_women():
    assert measures.amount(Dual(95, 65, True)) == {"men": 95, "women": 65}


def test_a_dual_written_with_equal_values_is_still_a_dual():
    assert measures.amount(Dual(12, 12, True)) == {"men": 12, "women": 12}


def test_whole_floats_are_stored_as_integers():
    value = measures.amount(Dual.single(43.0))
    assert value == 43
    assert isinstance(value, int)


def test_fractional_values_keep_three_decimals():
    assert measures.amount(Dual.single(22.5)) == 22.5


def test_pick_selects_a_category():
    assert measures.pick({"men": 95, "women": 65}, "women") == 65
    assert measures.pick(43, "women") == 43


def test_map_amount_applies_to_both_categories():
    assert measures.map_amount({"men": 2, "women": 1}, lambda v: v * 16) == {"men": 32, "women": 16}
    assert measures.map_amount(2, lambda v: v * 16) == 32


# --------------------------------------------------------------------------- loads


def test_lb_uses_the_equivalence_table(equivalences):
    # SPEC §13: 95 lb ↔ 43 kg, not 43.09 kg
    load = measures.load_to_json(Dual(95, 65, True), "lb", equivalences)
    assert load == {"kg": {"men": 43, "women": 30}, "lb": {"men": 95, "women": 65}, "unit": "lb", "written": {"men": 95, "women": 65}}


def test_kg_uses_the_equivalence_table_in_the_other_direction(equivalences):
    load = measures.load_to_json(Dual.single(43), "kg", equivalences)
    assert load == {"kg": 43, "lb": 95, "unit": "kg", "written": 43}


def test_a_load_outside_the_table_falls_back_to_arithmetic(equivalences):
    # 31 kg is not a table entry: 31 / 0.45359237 = 68.34 lb, rounded to 68
    load = measures.load_to_json(Dual.single(31), "kg", equivalences)
    assert load["lb"] == 68
    assert load["written"] == 31


def test_a_pound_value_outside_the_table_rounds_to_half_a_kilo(equivalences):
    # 101 lb = 45.813 kg -> 46 kg (nearest 0.5)
    load = measures.load_to_json(Dual.single(101), "lb", equivalences)
    assert load["kg"] == 46


def test_pood_converts_at_sixteen_kilos(equivalences):
    load = measures.load_to_json(Dual(1.5, 1, True), "pood", equivalences)
    assert load == {
        "kg": {"men": 24, "women": 16},
        "lb": {"men": 53, "women": 36},
        "unit": "pood",
        "written": {"men": 1.5, "women": 1},
    }


def test_pood_keeps_the_written_value_for_the_whiteboard(equivalences):
    item = first_item("For time\n  21 Kettlebell swing 2/1.5 pood\n")
    assert item["load"]["written"] == {"men": 2, "women": 1.5}
    assert item["load"]["kg"] == {"men": 32, "women": 24}


def test_without_a_table_the_conversion_is_pure_arithmetic():
    empty = Equivalences((), ())
    load = measures.load_to_json(Dual.single(43), "kg", empty)
    assert load["lb"] == round(43 / KG_PER_LB)


def test_the_physical_constants_match_the_spec():
    assert KG_PER_POOD == 16.0
    assert M_PER["mi"] == 1609.344
    assert M_PER["km"] == 1000.0
    assert CM_PER_IN == 2.54


# --------------------------------------------------------------------------- heights


def test_inches_use_the_equivalence_table(equivalences):
    height = measures.height_to_json(Dual(24, 20, True), "in", equivalences)
    assert height == {"cm": {"men": 60, "women": 50}, "in": {"men": 24, "women": 20}, "unit": "in", "written": {"men": 24, "women": 20}}


def test_centimetres_convert_back_to_inches(equivalences):
    height = measures.height_to_json(Dual.single(60), "cm", equivalences)
    assert height == {"cm": 60, "in": 24, "unit": "cm", "written": 60}


def test_a_height_outside_the_table_falls_back_to_arithmetic(equivalences):
    height = measures.height_to_json(Dual.single(61), "cm", equivalences)
    assert height["in"] == round(61 / CM_PER_IN)


# --------------------------------------------------------------------------- distances


@pytest.mark.parametrize(
    ("value", "unit", "metres"),
    [(400, "m", 400), (5, "km", 5000), (1, "mi", 1609.344), (2, "mi", 3218.688)],
)
def test_distances_are_normalised_to_metres(value, unit, metres):
    quantity = measures.distance_to_json(Dual.single(value), unit)
    assert quantity == {"m": metres, "unit": unit, "written": value}


def test_a_dual_distance_keeps_both_categories():
    quantity = measures.distance_to_json(Dual(400, 300, True), "m")
    assert quantity["m"] == {"men": 400, "women": 300}


def test_one_mile_compiles_to_1609_344_metres():
    item = first_item("For time\n  1 mi Run\n")
    assert item["quantity"] == {"m": 1609.344, "unit": "mi", "written": 1, "kind": "distance"}
