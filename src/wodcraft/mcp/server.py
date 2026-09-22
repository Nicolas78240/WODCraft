"""The WODCraft MCP server.

Exposes the WODCraft 1.0 compiler over the Model Context Protocol: an assistant drafts a
workout, `check_wod` tells it exactly what is wrong, and it corrects until the source compiles.

Run it over stdio (the default) or over streamable HTTP::

    python -m wodcraft.mcp.server
    python -m wodcraft.mcp.server --http --port 8000

Everything is called in-process: no temporary file, no subprocess.
"""

from __future__ import annotations

import argparse
import difflib
import json
from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError
from pydantic import Field

from wodcraft import SPEC_VERSION, __version__
from wodcraft.api import Result, compile_source
from wodcraft.catalog import load_catalog
from wodcraft.emit import board
from wodcraft.emit.source import format_source
from wodcraft.emit.timeline import render_timeline, timeline
from wodcraft.mcp.guide import SYNTAX_GUIDE
from wodcraft.mcp.models import (
    CheckResult,
    CompileResult,
    DiagnosticOut,
    FormatResult,
    LibraryEntry,
    LibraryList,
    LibraryWorkout,
    MovementOut,
    MovementSearchResult,
    ShowResult,
    TimelineResult,
    TimelineSegment,
)
from wodcraft.mcp.paths import library_file, library_paths, spec_file
from wodcraft.profile import Profile
from wodcraft.semantics.resolve import resolve
from wodcraft.syntax.parser import parse_source

FAMILY_NAMES = {"M": "monostructural", "G": "gymnastics", "W": "weightlifting"}

INSTRUCTIONS = """\
WODCraft writes functional-fitness workouts (CrossFit-style WODs) as plain text that compiles.

Read `wodcraft://guide/syntax` before writing any WODCraft source — the syntax is small, exact,
and nothing outside it is accepted. Then: draft, call `check_wod`, fix every diagnostic (each
carries a line, a column and usually a suggestion), and only return source that checks clean.

`search_movements` resolves a movement name against the catalog: a name outside it is an error.
`library_list` / `library_get` give the standard benchmarks (Girls, Heroes, Open).
"""

server: MCPServer = MCPServer(
    name="wodcraft",
    title="WODCraft",
    version=__version__,
    instructions=INSTRUCTIONS,
    website_url="https://github.com/Nicolas78240/WODCraft",
)


# --------------------------------------------------------------------------- helpers

Source = Annotated[str, Field(description="WODCraft 1.0 source (the content of a .wod file)")]


def _diagnostics(result: Result) -> list[DiagnosticOut]:
    return [DiagnosticOut(**d.to_dict()) for d in result.diagnostics]


def _counts(diagnostics: list[DiagnosticOut]) -> dict[str, int]:
    return {
        "errors": sum(1 for d in diagnostics if d.severity == "error"),
        "warnings": sum(1 for d in diagnostics if d.severity == "warning"),
    }


def _compile(source: str) -> tuple[Result, list[DiagnosticOut], dict[str, int]]:
    if not isinstance(source, str) or not source.strip():
        raise ToolError("The source is empty. Pass the text of a .wod file.")
    result = compile_source(source, "<mcp>")
    diagnostics = _diagnostics(result)
    return result, diagnostics, _counts(diagnostics)


def _profile(category: str | None, level: str | None, units: str | None) -> Profile | None:
    if not any((category, level, units)):
        return None
    profile = Profile()
    if category:
        profile.category = category.lower()
    if level:
        profile.level = level.lower()
    if units:
        profile.units = units.lower()
    return profile


def _title(source: str, fallback: str) -> str:
    for line in source.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _tags(document: dict[str, Any] | None) -> list[str]:
    return list(((document or {}).get("meta") or {}).get("tags") or [])


# --------------------------------------------------------------------------- tools


@server.tool(
    title="Check a WODCraft source",
    description="Compile a WODCraft source and report every diagnostic (code, severity, line, "
    "column, message, suggestion). Call this on every draft before returning it.",
)
def check_wod(source: Source) -> CheckResult:
    """Check a .wod source and return its diagnostics.

    Errors make the source invalid; warnings and infos do not. Each diagnostic points at a
    line and a column of the source you passed, and usually carries a suggestion.

    ```wod
    # Fran
    21-15-9 for time, cap 10:00
      Thruster 43/30 kg
      Pull-up
    ```
    """
    result, diagnostics, counts = _compile(source)
    if result.ok:
        extra = f" ({counts['warnings']} warning{'s' if counts['warnings'] > 1 else ''})" if counts["warnings"] else ""
        summary = f"Valid WODCraft {SPEC_VERSION}{extra}."
    else:
        summary = f"{counts['errors']} error{'s' if counts['errors'] > 1 else ''}; the source does not compile."
    return CheckResult(ok=result.ok, diagnostics=diagnostics, summary=summary, **counts)


@server.tool(
    title="Compile a WODCraft source",
    description="Compile a WODCraft source to its JSON document (the interchange format described "
    "by SPEC §13): blocks, score, levels, meta, estimate, with a source span on every item.",
)
def compile_wod(source: Source) -> CompileResult:
    """Compile a .wod source to the WODCraft JSON document.

    Returns no document when the source has errors — read `diagnostics` and fix them first.
    """
    result, diagnostics, counts = _compile(source)
    documents = result.documents if result.ok else []
    return CompileResult(
        ok=result.ok,
        diagnostics=diagnostics,
        document=documents[0] if documents else None,
        documents=documents,
        **counts,
    )


@server.tool(
    title="Show the whiteboard",
    description="Render a WODCraft source as it would be written on a gym whiteboard, optionally "
    "resolved for an athlete (category, level, units).",
)
def show_wod(
    source: Source,
    category: Annotated[Literal["men", "women"] | None, Field(description="Which side of a men/women value to keep")] = None,
    level: Annotated[
        Literal["rx", "intermediate", "scaled", "foundations"] | None,
        Field(description="Level block to apply; falls back to the closest level, then Rx"),
    ] = None,
    units: Annotated[Literal["kg", "lb"] | None, Field(description="Unit loads are displayed in")] = None,
) -> ShowResult:
    """Render the whiteboard view of a .wod source.

    With no parameter the raw Rx view is rendered, men/women values side by side. Pass any of
    `category`, `level` or `units` to resolve the workout for one athlete.
    """
    result, diagnostics, counts = _compile(source)
    if not result.ok:
        return ShowResult(ok=False, diagnostics=diagnostics, **counts)
    profile = _profile(category, level, units)
    boards = []
    for document in result.documents:
        boards.append(board.render(resolve(document, profile) if profile else document))
    resolved_for = {"category": profile.category, "level": profile.level, "units": profile.units} if profile else None
    return ShowResult(ok=True, diagnostics=diagnostics, board="\n".join(boards).rstrip() + "\n", resolved_for=resolved_for, **counts)


@server.tool(
    title="Format a WODCraft source",
    description="Rewrite a WODCraft source in canonical form (the `wodc fmt` output): keywords, units, spacing and indentation normalised.",
)
def format_wod(source: Source) -> FormatResult:
    """Return the canonical form of a .wod source.

    Formatting only needs the source to parse; it does not need it to be semantically valid.
    """
    if not isinstance(source, str) or not source.strip():
        raise ToolError("The source is empty. Pass the text of a .wod file.")
    source_file, bag = parse_source(source, "<mcp>")
    diagnostics = [DiagnosticOut(**d.to_dict()) for d in bag.sorted()]
    counts = _counts(diagnostics)
    if bag.has_errors:
        return FormatResult(ok=False, diagnostics=diagnostics, **counts)
    formatted = format_source(source_file)
    return FormatResult(ok=True, diagnostics=diagnostics, formatted=formatted, changed=formatted != source, **counts)


@server.tool(
    title="Timeline of a workout",
    description="The clock, segment by segment: what happens when, for EMOMs, intervals, AMRAPs "
    "and capped work. Useful to drive a timer or to sanity-check pacing.",
)
def timeline_wod(source: Source) -> TimelineResult:
    """Return the timeline segments of a .wod source.

    A segment with `open_ended: true` has no cap: its length is the compiler's estimate.
    """
    result, diagnostics, counts = _compile(source)
    if not result.ok:
        return TimelineResult(ok=False, diagnostics=diagnostics, **counts)
    segments: list[TimelineSegment] = []
    rendered: list[str] = []
    for document in result.documents:
        raw = timeline(document)
        segments += [TimelineSegment(**segment) for segment in raw]
        rendered.append(render_timeline(raw))
    return TimelineResult(
        ok=True,
        diagnostics=diagnostics,
        total_s=sum(s.duration_s for s in segments),
        segments=segments,
        rendered="\n".join(rendered),
        **counts,
    )


@server.tool(
    title="Search the movement catalog",
    description="Find movements by name, alias (English or French) or family. Only catalog "
    "movements may be written in a .wod file, so check a name here before using it.",
)
def search_movements(
    query: Annotated[str | None, Field(description="Name, identifier or alias fragment, e.g. 'snatch' or 'traction'")] = None,
    family: Annotated[
        Literal["M", "G", "W"] | None,
        Field(description="M monostructural, G gymnastics, W weightlifting"),
    ] = None,
    limit: Annotated[int, Field(ge=1, le=250, description="Maximum number of entries returned")] = 50,
) -> MovementSearchResult:
    """Search the movement catalog (SPEC §11).

    With no query and no family, returns the first `limit` movements of the catalog.
    `name` is what you write on a movement line; `id` is what the compiled JSON contains.
    """
    catalog = load_catalog()
    needle = (query or "").strip().lower()
    rows = [
        movement
        for movement in catalog.movements.values()
        if (not family or movement.family == family)
        and (
            not needle
            or needle in movement.name.lower()
            or needle in movement.id.replace("_", " ")
            or any(needle in alias.lower() for alias in (*movement.aliases, *movement.fr))
        )
    ]

    def rank(movement) -> tuple[int, str]:
        if not needle:
            return (0, movement.id)
        names = [movement.name.lower(), movement.id.replace("_", " "), *(a.lower() for a in (*movement.aliases, *movement.fr))]
        if any(name == needle for name in names):
            return (0, movement.id)
        if any(name.startswith(needle) for name in names):
            return (1, movement.id)
        return (2, movement.id)

    rows.sort(key=rank)
    kept = rows[:limit]
    return MovementSearchResult(
        count=len(kept),
        total=len(rows),
        catalog_size=len(catalog),
        truncated=len(kept) < len(rows),
        movements=[
            MovementOut(
                id=m.id,
                name=m.name,
                family=m.family,  # type: ignore[arg-type]
                family_name=FAMILY_NAMES.get(m.family, m.family),
                quantities=list(m.quantities),
                param=list(m.params),
                equipment=m.equipment,
                aliases=list(m.aliases),
                fr=list(m.fr),
                rx=dict(m.rx) if m.rx else None,
            )
            for m in kept
        ],
    )


@server.tool(
    title="List the standard library",
    description="The benchmark workouts shipped with WODCraft (girls/, heroes/, open/), by the path a `use` line takes.",
)
def library_list(
    query: Annotated[str | None, Field(description="Filter on the path or the title, e.g. 'girls' or 'fran'")] = None,
) -> LibraryList:
    """List the standard workout library.

    Pull one into a session with a `use` line:

    ```wod
    # Tuesday
    ## Metcon
    use girls/fran
    ```
    """
    needle = (query or "").strip().lower()
    entries: list[LibraryEntry] = []
    total = 0
    for path in library_paths():
        file = library_file(path)
        if file is None:  # pragma: no cover - library_paths only yields readable files
            continue
        source = file.read_text(encoding="utf-8")
        title = _title(source, path)
        if needle and needle not in path.lower() and needle not in title.lower():
            continue
        total += 1
        entries.append(LibraryEntry(path=path, title=title, tags=_tags(compile_source(source, str(file)).document)))
    return LibraryList(count=len(entries), total=total, workouts=entries)


@server.tool(
    title="Read a library workout",
    description="The WODCraft source of one standard-library workout, by its `use` path (e.g. girls/fran, heroes/murph, open/24_1).",
)
def library_get(
    path: Annotated[str, Field(description="Library path without the extension, e.g. 'girls/fran'")],
) -> LibraryWorkout:
    """Return the source of a standard-library workout.

    Use it as a model to write your own, or insert it verbatim with a `use` line.
    """
    file = library_file(path)
    if file is None:
        known = library_paths()
        needle = (path or "").strip("/ ").lower().removesuffix(".wod")
        near = [p for p in known if needle and needle in p][:5] or difflib.get_close_matches(needle, known, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(near)}?" if near else f" {len(known)} workouts available; call library_list."
        raise ToolError(f"No library workout at {path!r}.{hint}")
    use_path = path.strip().strip("/").removesuffix(".wod")
    source = file.read_text(encoding="utf-8")
    result = compile_source(source, str(file))
    diagnostics = _diagnostics(result)
    return LibraryWorkout(
        path=use_path,
        title=_title(source, use_path),
        tags=_tags(result.document),
        source=source,
        use_line=f"use {use_path}",
        ok=result.ok,
        diagnostics=diagnostics,
    )


# --------------------------------------------------------------------------- resources


@server.resource(
    "wodcraft://spec",
    name="WODCraft 1.0 specification",
    description="The full language specification (spec/SPEC.md): lexical structure, blocks, formats, movements, levels, diagnostics.",
    mime_type="text/markdown",
)
def spec_resource() -> str:
    """The WODCraft 1.0 specification, verbatim."""
    file = spec_file()
    if file is None:
        raise ResourceNotFoundError(
            "spec/SPEC.md is not on disk next to this installation. Set the WODCRAFT_SPEC "
            "environment variable to its path, or read wodcraft://guide/syntax instead."
        )
    return file.read_text(encoding="utf-8")


@server.resource(
    "wodcraft://guide/syntax",
    name="WODCraft syntax guide",
    description="Short, exact syntax guide for writing WODCraft 1.0. Read this before drafting.",
    mime_type="text/markdown",
)
def syntax_guide_resource() -> str:
    """The short syntax guide. Every example in it compiles."""
    return SYNTAX_GUIDE


@server.resource(
    "wodcraft://catalog",
    name="Movement catalog",
    description="Every movement WODCraft accepts: identifier, canonical name, family, accepted "
    "quantities and parameters, English and French aliases, reference Rx load.",
    mime_type="application/json",
)
def catalog_resource() -> str:
    """The movement catalog as JSON."""
    catalog = load_catalog()
    payload = {
        "wodcraft": SPEC_VERSION,
        "count": len(catalog),
        "families": FAMILY_NAMES,
        "movements": [
            {
                "id": m.id,
                "name": m.name,
                "family": m.family,
                "quantities": list(m.quantities),
                "param": list(m.params),
                "equipment": m.equipment,
                "aliases": list(m.aliases),
                "fr": list(m.fr),
                "rx": m.rx,
            }
            for m in sorted(catalog.movements.values(), key=lambda m: m.id)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


@server.resource(
    "wodcraft://library/{+path}",
    name="Standard library workout",
    description="The source of a standard-library workout, by its `use` path (girls/fran, "
    "heroes/murph, open/24_1). Read wodcraft://library to list them.",
    mime_type="text/plain",
)
def library_resource(path: str) -> str:
    """One library workout, verbatim."""
    file = library_file(path)
    if file is None:
        raise ResourceNotFoundError(f"No library workout at {path!r}. Read wodcraft://library for the list.")
    return file.read_text(encoding="utf-8")


@server.resource(
    "wodcraft://library",
    name="Standard library index",
    description="Every workout of the standard library, as `use` paths.",
    mime_type="application/json",
)
def library_index_resource() -> str:
    """The list of library paths as JSON."""
    return json.dumps({"count": len(library_paths()), "workouts": library_paths()}, indent=2)


# --------------------------------------------------------------------------- prompt


@server.prompt(
    title="Design a WOD",
    description="Write a WODCraft 1.0 workout for a goal, a duration, the available equipment "
    "and a level — and check it with the compiler before answering.",
)
def design_wod(
    goal: Annotated[str, Field(description="What the workout should train, e.g. 'engine', 'pull strength', 'legs'")],
    duration: Annotated[str, Field(description="Target length, e.g. '12 min', '20:00', '45 min session'")] = "15 min",
    equipment: Annotated[
        str, Field(description="Available equipment, e.g. 'barbell, rower, pull-up bar'")
    ] = "barbell, pull-up bar, box, rower",
    level: Annotated[str, Field(description="rx, intermediate, scaled or foundations")] = "rx",
) -> str:
    """Ask the assistant to design a workout in valid WODCraft 1.0."""
    return f"""\
Design one WODCraft 1.0 workout.

- Goal: {goal}
- Target duration: {duration}
- Available equipment: {equipment}
- Level written as Rx: {level}

How to proceed:

1. Pick a format that fits the duration and the goal (see the guide below).
2. Only use movements the equipment allows, and only names that exist in the catalog —
   call `search_movements` whenever you are not certain of a name.
3. Write the source, then call `check_wod` on it. Fix every error and every warning worth
   fixing, and call `check_wod` again. Repeat until it is clean.
4. Call `show_wod` to read the whiteboard view and sanity-check the result, and
   `timeline_wod` when the workout is interval-based.
5. Answer with the final `.wod` source in a ```wod block, then two or three lines explaining
   the stimulus and the intended pacing. Put anything the athlete must know in a `note:` or
   `stimulus:` meta line inside the source itself.

Add a `Scaled:` block listing only the differences from the Rx work, unless the workout is
already written at the easiest level.

The syntax, in full:

{SYNTAX_GUIDE}
"""


# --------------------------------------------------------------------------- entry point


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wodcraft-mcp",
        description=f"WODCraft {__version__} MCP server (spec {SPEC_VERSION}).",
    )
    parser.add_argument("--http", action="store_true", help="serve over streamable HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    parser.add_argument("--path", default="/mcp", help="HTTP endpoint path (default: /mcp)")
    parser.add_argument("--json-response", action="store_true", help="answer with plain JSON instead of SSE")
    parser.add_argument("--stateless", action="store_true", help="do not keep a session between HTTP requests")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.http:
        server.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path=args.path,
            json_response=args.json_response,
            stateless_http=args.stateless,
        )
    else:
        server.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
