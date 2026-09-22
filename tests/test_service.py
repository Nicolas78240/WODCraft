"""The HTTP service around the compiler (wodcraft[service])."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="the service extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from wodcraft import SPEC_VERSION  # noqa: E402
from wodcraft.service import API_KEY_ENV, MAX_SOURCE_BYTES, app  # noqa: E402

FRAN = "21-15-9 for time, cap 10:00\n  Thruster 95/65 lb\n  Pull-up\n"


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    return TestClient(app)


def test_health_says_which_spec_it_implements(client):
    assert client.get("/health").json()["wodcraft"] == SPEC_VERSION


def test_compile_returns_the_document(client):
    body = client.post("/compile", json={"source": FRAN}).json()
    assert body["ok"] is True
    assert body["documents"][0]["score"] == {"type": "time", "capped": "reps"}


def test_compile_reports_diagnostics_instead_of_failing(client):
    body = client.post("/compile", json={"source": "AMRAP 12\n  10 Trusters 43 kg\n"}).json()
    assert body["ok"] is False
    assert [d["code"] for d in body["diagnostics"]] == ["E016", "E020"]
    assert "Thruster" in body["diagnostics"][1]["suggestion"]


def test_check_counts_errors_and_warnings(client):
    body = client.post("/check", json={"source": "For time\n  1 m Run\n"}).json()
    assert (body["ok"], body["errors"], body["warnings"]) == (True, 0, 1)


def test_format_returns_the_canonical_form(client):
    body = client.post("/format", json={"source": "AMRAP 12\n10 Burpee\n"}).json()
    assert body["formatted"] == "AMRAP 12:00\n  10 Burpee\n"
    assert body["changed"] is True


def test_format_leaves_a_broken_source_alone(client):
    body = client.post("/format", json={"source": "AMRAP\n  10 Burpee\n"}).json()
    assert body["ok"] is False
    assert body["changed"] is False


def test_show_resolves_for_an_athlete(client):
    body = client.post("/show", json={"source": FRAN, "category": "women", "units": "kg"}).json()
    assert "30 kg" in body["board"]


def test_show_speaks_french(client):
    body = client.post("/show", json={"source": FRAN, "language": "fr"}).json()
    assert "Traction" in body["board"]


def test_show_on_a_broken_source_has_no_board(client):
    body = client.post("/show", json={"source": "AMRAP\n"}).json()
    assert body["ok"] is False and body["board"] is None


def test_the_catalog_is_served(client):
    body = client.get("/catalog").json()
    assert len(body["movements"]) > 200
    assert any(movement["id"] == "thruster" for movement in body["movements"])


def test_the_library_is_served(client):
    assert {"path": "girls/fran", "title": "Fran"} in client.get("/library").json()["workouts"]


def test_the_library_can_be_filtered(client):
    assert client.get("/library", params={"query": "fran"}).json()["workouts"] == [{"path": "girls/fran", "title": "Fran"}]


def test_one_library_workout_carries_source_and_compiled(client):
    body = client.get("/library/girls/fran").json()
    assert body["source"].startswith("# Fran")
    assert body["compiled"]["blocks"][0]["reps"] == [21, 15, 9]


def test_an_unknown_workout_is_a_404(client):
    assert client.get("/library/girls/nope").status_code == 404


def test_the_spec_is_served(client):
    assert client.get("/spec").json()["text"].startswith("# WODCraft Language Specification")


def test_a_source_that_is_too_large_is_refused(client):
    assert client.post("/compile", json={"source": "x" * (MAX_SOURCE_BYTES + 1)}).status_code == 413


def test_the_api_key_gate_is_off_by_default(client):
    assert client.get("/catalog").status_code == 200


def test_the_api_key_is_required_when_configured(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "secret")
    guarded = TestClient(app)
    assert guarded.get("/catalog").status_code == 401
    assert guarded.get("/catalog", headers={"X-API-Key": "secret"}).status_code == 200
    assert guarded.post("/compile", json={"source": FRAN}, headers={"X-API-Key": "secret"}).status_code == 200


def test_health_stays_open_even_behind_a_key(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "secret")
    assert TestClient(app).get("/health").status_code == 200
