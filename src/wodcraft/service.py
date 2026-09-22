"""A small HTTP service around the compiler, for clients that cannot embed it.

An application that can embed the compiler should: `WODCraftKit` compiles offline on Apple platforms,
and `pip install wodcraft` covers everything Python. This service exists for the rest — a web page, a
script in another language, a CI step — and is deliberately small: one process, no database, no state.

    pip install "wodcraft[service]"
    wodcraft-service --port 8000          # or: uvicorn wodcraft.service:app

Endpoints: POST /compile, POST /check, POST /format, POST /show, GET /catalog, GET /library,
GET /library/{path}, GET /spec, GET /health.
"""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import Body, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from wodcraft import SPEC_VERSION, __version__, library
from wodcraft.api import compile_source, format_source
from wodcraft.bundle import catalog_json
from wodcraft.emit import board
from wodcraft.profile import Profile
from wodcraft.resources import spec_text
from wodcraft.semantics.resolve import resolve

MAX_SOURCE_BYTES = 256 * 1024  # a workout is a few hundred bytes; a session, a few thousand
API_KEY_ENV = "WODCRAFT_API_KEY"

app = FastAPI(
    title="WODCraft",
    version=__version__,
    summary=f"Compile WODCraft {SPEC_VERSION} sources into the documented JSON model.",
)


class Source(BaseModel):
    source: str = Field(description="The .wod text to compile.")
    file: str | None = Field(default=None, description="A name used in diagnostics.")


class ShowRequest(Source):
    category: str | None = Field(default=None, pattern="^(men|women)$")
    level: str | None = None
    units: str | None = Field(default=None, pattern="^(kg|lb)$")
    language: str = Field(default="en", pattern="^(en|fr)$")


def _authorize(key: str | None) -> None:
    """When WODCRAFT_API_KEY is set, every call carries it in X-API-Key."""
    expected = os.environ.get(API_KEY_ENV)
    if expected and key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


def _read(payload: Source) -> str:
    if len(payload.source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail=f"source larger than {MAX_SOURCE_BYTES // 1024} kB")
    return payload.source


def _diagnostics(result) -> list[dict[str, Any]]:
    return [d.to_dict() for d in result.diagnostics]


@app.post("/compile", summary="Compile a source into documents")
def compile_endpoint(
    payload: Annotated[Source, Body()],
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _authorize(x_api_key)
    result = compile_source(_read(payload), payload.file or "<request>")
    return {
        "ok": result.ok,
        "documents": result.documents if result.ok else [],
        "diagnostics": _diagnostics(result),
    }


@app.post("/check", summary="Diagnostics only")
def check_endpoint(
    payload: Annotated[Source, Body()],
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _authorize(x_api_key)
    result = compile_source(_read(payload), payload.file or "<request>")
    errors = [d for d in result.diagnostics if d.severity.value == "error"]
    return {
        "ok": result.ok,
        "errors": len(errors),
        "warnings": len(result.diagnostics) - len(errors),
        "diagnostics": _diagnostics(result),
    }


@app.post("/format", summary="Canonical source form")
def format_endpoint(
    payload: Annotated[Source, Body()],
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _authorize(x_api_key)
    source = _read(payload)
    formatted, diagnostics = format_source(source, payload.file or "<request>")
    return {
        "ok": not [d for d in diagnostics if d.severity.value == "error"],
        "formatted": formatted,
        "changed": formatted != source,
        "diagnostics": [d.to_dict() for d in diagnostics],
    }


@app.post("/show", summary="The whiteboard view, resolved for an athlete")
def show_endpoint(
    payload: Annotated[ShowRequest, Body()],
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _authorize(x_api_key)
    result = compile_source(_read(payload), payload.file or "<request>")
    if not result.ok:
        return {"ok": False, "board": None, "diagnostics": _diagnostics(result)}
    profile = Profile().with_overrides(payload.category, payload.level, payload.units)
    boards = [board.render(resolve(document, profile), lang=payload.language) for document in result.documents]
    return {"ok": True, "board": "\n\n".join(boards), "diagnostics": _diagnostics(result)}


@app.get("/catalog", summary="The movement catalog and the equivalence tables")
def catalog_endpoint(x_api_key: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    _authorize(x_api_key)
    return catalog_json()


@app.get("/library", summary="The standard workout library")
def library_endpoint(
    query: Annotated[str | None, Query(max_length=100)] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _authorize(x_api_key)
    return {"workouts": [{"path": entry.path, "title": entry.title} for entry in library.entries(query)]}


@app.get("/library/{path:path}", summary="One library workout, source and compiled")
def library_workout_endpoint(path: str, x_api_key: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    _authorize(x_api_key)
    entry = library.get(path)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"unknown workout {path!r}")
    result = compile_source(entry.source, entry.path)
    return {"path": entry.path, "title": entry.title, "source": entry.source, "compiled": result.document}


@app.get("/spec", summary="The specification this service implements")
def spec_endpoint(x_api_key: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    _authorize(x_api_key)
    return {"wodcraft": SPEC_VERSION, "text": spec_text()}


@app.get("/health", summary="Liveness")
def health_endpoint() -> dict[str, Any]:
    return {"status": "ok", "wodcraft": SPEC_VERSION, "version": __version__}


def main() -> int:  # pragma: no cover - the entry point
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(prog="wodcraft-service", description=__doc__.split("\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("wodcraft.service:app", host=args.host, port=args.port, reload=args.reload)
    return 0
