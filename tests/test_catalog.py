"""The movement catalog and the equivalence table (SPEC §11, §13)."""

from __future__ import annotations

import pytest

from wodcraft.catalog import Catalog, Equivalences, load_catalog, load_equivalences, normalize

# --------------------------------------------------------------------------- name normalisation


@pytest.mark.parametrize(
    ("written", "normalised"),
    [
        ("Pull-up", "pull up"),
        ("PULL UP", "pull up"),
        ("Pull-ups", "pull up"),
        ("  Air   squat ", "air squat"),
        ("Toes-to-bar", "toes to bar"),
        ("Burpees", "burpee"),
        ("Press", "press"),  # a trailing "ss" is not a plural
        ("Dips", "dip"),
        ("Ski", "ski"),  # too short to lose its last letter
        ("L’assis", "l'assi"),
    ],
)
def test_normalize(written, normalised):
    assert normalize(written) == normalised


# --------------------------------------------------------------------------- lookups


def test_the_catalog_is_not_empty(catalog):
    assert len(catalog) > 100


def test_a_movement_is_found_by_its_canonical_name(catalog):
    movement = catalog.get("Thruster")
    assert movement is not None
    assert (movement.id, movement.name, movement.family) == ("thruster", "Thruster", "W")


def test_a_movement_is_found_by_its_identifier(catalog):
    assert catalog.get("pull up").id == "pull_up"


@pytest.mark.parametrize("alias", ["pullup", "pull-up", "PULL-UPS", "traction"])
def test_a_movement_is_found_by_its_aliases(catalog, alias):
    assert catalog.get(alias).id == "pull_up"


def test_an_unknown_name_returns_none(catalog):
    assert catalog.get("Frobnicate") is None


def test_suggestions_are_close_canonical_names(catalog):
    assert "Thruster" in catalog.suggest("Thrustor")


def test_suggestions_are_deduplicated(catalog):
    suggestions = catalog.suggest("pullup")
    assert len(suggestions) == len(set(suggestions))


def test_a_hopeless_name_gets_no_suggestion(catalog):
    assert catalog.suggest("zzzzzzzzzz") == []


# --------------------------------------------------------------------------- entries


def test_every_entry_declares_a_name_a_family_and_a_quantity(catalog):
    for movement in catalog.movements.values():
        assert movement.name, movement.id
        assert movement.family in ("M", "G", "W"), movement.id
        assert movement.quantities, movement.id
        assert set(movement.quantities) <= {"reps", "distance", "calories", "time"}, movement.id


def test_every_entry_declares_an_accepted_parameter_kind(catalog):
    for movement in catalog.movements.values():
        assert set(movement.params) <= {"load", "height"}, movement.id


def alias_clashes(catalog) -> list[tuple[str, str, str]]:
    seen: dict[str, str] = {}
    clashes = []
    for movement in catalog.movements.values():
        for alias in (movement.name, movement.id.replace("_", " "), *movement.aliases, *movement.fr):
            key = normalize(alias)
            if key in seen and seen[key] != movement.id:
                clashes.append((key, seen[key], movement.id))
            seen.setdefault(key, movement.id)
    return clashes


def test_no_alias_is_shared_by_two_movements(catalog):
    # SPEC §11: "No alias (English or French) may be shared by two movements, nor equal
    # another movement's canonical name, after lowercasing and removing a trailing 's'."
    assert alias_clashes(catalog) == []


def test_no_canonical_name_is_shadowed_by_an_alias(catalog):
    # Guard: an alias that is also another movement's name silently steals that name.
    assert sorted({clash[0] for clash in alias_clashes(catalog)}) == []


def test_a_canonical_name_resolves_to_its_own_movement(catalog):
    assert catalog.get("Bar-facing burpee").id == "bar_facing_burpee"
    assert catalog.get("Burpee over the bar").id == "burpee_over_the_bar"


def test_rest_is_not_a_movement(catalog):
    # SPEC §11: "Rest is NOT a movement: it is a language construct".
    assert catalog.get("Rest") is None


def test_pace_for_maps_quantity_kinds_to_catalog_keys(catalog):
    run = catalog.get("Run")
    assert run.pace_for("distance") == run.pace.get("m")
    assert catalog.get("Row").pace_for("calories") == catalog.get("Row").pace.get("cal")
    assert catalog.get("Burpee").pace_for("reps") == catalog.get("Burpee").pace.get("rep")


def test_pace_for_an_unknown_kind_is_none(catalog):
    assert catalog.get("Burpee").pace_for("nonsense") is None


def test_an_rx_reference_carries_its_unit(catalog):
    thruster = catalog.get("Thruster")
    assert thruster.rx["unit"] == "kg"
    assert thruster.rx["men"] > thruster.rx["women"]


def test_a_none_parameter_becomes_an_empty_tuple(catalog):
    assert catalog.get("Burpee").params == ()


def test_the_catalog_is_cached():
    assert load_catalog() is load_catalog()


def test_a_custom_catalog_can_be_loaded(tmp_path):
    path = tmp_path / "mini.toml"
    path.write_text(
        '[movements.jump]\nname = "Jump"\nfamily = "G"\nquantities = ["reps"]\nparam = "none"\naliases = ["hop"]\n',
        encoding="utf-8",
    )

    mini = load_catalog(str(path))

    assert len(mini) == 1
    assert mini.get("hop").id == "jump"
    assert isinstance(mini, Catalog)


# --------------------------------------------------------------------------- equivalences


def test_the_equivalence_table_is_loaded(equivalences):
    assert equivalences.load
    assert equivalences.height


def test_the_spec_examples_are_in_the_table(equivalences):
    # SPEC §13 names 95 lb ↔ 43 kg and 24 in ↔ 60 cm.
    assert equivalences.lb_to_kg(95) == 43
    assert equivalences.kg_to_lb(43) == 95
    assert equivalences.in_to_cm(24) == 60
    assert equivalences.cm_to_in(60) == 24


def test_a_value_outside_the_table_returns_none(equivalences):
    assert equivalences.lb_to_kg(96) is None
    assert equivalences.kg_to_lb(44) is None
    assert equivalences.in_to_cm(23) is None
    assert equivalences.cm_to_in(61) is None


def test_the_load_table_is_a_bijection(equivalences):
    kilos = [kg for kg, _ in equivalences.load]
    pounds = [lb for _, lb in equivalences.load]
    assert len(kilos) == len(set(kilos))
    assert len(pounds) == len(set(pounds))


def test_the_height_table_is_a_bijection(equivalences):
    centimetres = [cm for cm, _ in equivalences.height]
    inches = [i for _, i in equivalences.height]
    assert len(centimetres) == len(set(centimetres))
    assert len(inches) == len(set(inches))


def test_the_table_stays_close_to_the_arithmetic_conversion(equivalences):
    from wodcraft.syntax.units import KG_PER_LB

    for kg, lb in equivalences.load:
        assert abs(kg - lb * KG_PER_LB) < 1.6, (kg, lb)


def test_a_missing_table_file_yields_an_empty_one(tmp_path):
    empty = load_equivalences(str(tmp_path / "absent.toml"))
    assert empty == Equivalences((), ())
    assert empty.kg_to_lb(43) is None


def test_the_equivalence_table_is_cached():
    assert load_equivalences() is load_equivalences()
