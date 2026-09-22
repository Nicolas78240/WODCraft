"""The JSON bundle an application embeds, and the copy committed in the Swift package."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wodcraft import SPEC_VERSION
from wodcraft.bundle import catalog_json, library_json, write_bundle

ROOT = Path(__file__).resolve().parents[1]
SWIFT_RESOURCES = ROOT / "swift/WODCraftKit/Sources/WODCraftKit/Resources"
SWIFT_CONFORMANCE = ROOT / "swift/WODCraftKit/Tests/WODCraftKitTests/Resources/conformance"


@pytest.fixture(scope="module")
def catalog() -> dict:
    return catalog_json()


def test_the_catalog_carries_every_movement(catalog):
    assert len(catalog["movements"]) > 200
    assert catalog["wodcraft"] == SPEC_VERSION


def test_a_catalog_entry_is_complete(catalog):
    (thruster,) = [m for m in catalog["movements"] if m["id"] == "thruster"]
    assert thruster["name"] == "Thruster"
    assert thruster["family"] == "W"
    assert thruster["params"] == ["load"]
    assert thruster["rx"]["men"] == 43
    assert thruster["fr_name"] == "Thruster"


def test_every_movement_has_a_french_display_name(catalog):
    assert all(movement["fr_name"] for movement in catalog["movements"])


def test_the_equivalences_are_carried(catalog):
    assert {"kg": 43, "lb": 95} in catalog["equivalences"]["load"]
    assert {"cm": 60, "in": 24} in catalog["equivalences"]["height"]


def test_the_library_carries_source_and_compiled():
    workouts, failures = library_json()
    assert failures == []
    (fran,) = [w for w in workouts["workouts"] if w["path"] == "girls/fran"]
    assert fran["title"] == "Fran"
    assert fran["source"].startswith("# Fran")
    assert fran["compiled"]["score"] == {"type": "time", "capped": "reps"}


def test_write_bundle_writes_the_four_files(tmp_path):
    report = write_bundle(tmp_path)
    names = {Path(path).name for path in report.files}
    assert names == {"catalog.json", "library.json", "workout.schema.json", "bundle.json"}
    assert report.workouts >= 30
    assert report.failures == []


def test_the_bundle_stays_small_enough_to_embed(tmp_path):
    report = write_bundle(tmp_path)
    assert sum(report.files.values()) < 300 * 1024  # it ships inside a mobile application


# --------------------------------------------------------------------------- the Swift package

# The Swift package embeds a copy of the bundle. These tests are what stops the two from drifting:
# run `make swift-resources` after changing the catalog, the library or the schema.


@pytest.mark.parametrize("name", ["catalog.json", "library.json", "workout.schema.json"])
def test_the_swift_resources_match_this_implementation(name, tmp_path):
    write_bundle(tmp_path)
    committed = json.loads((SWIFT_RESOURCES / name).read_text(encoding="utf-8"))
    fresh = json.loads((tmp_path / name).read_text(encoding="utf-8"))
    assert committed == fresh, f"{name} is stale: run `make swift-resources`"


def test_the_swift_package_carries_the_conformance_suite():
    committed = {path.name for path in SWIFT_CONFORMANCE.iterdir()}
    reference = {path.name for path in (ROOT / "spec/conformance").iterdir()}
    assert committed == reference, "the conformance copy is stale: run `make swift-resources`"
