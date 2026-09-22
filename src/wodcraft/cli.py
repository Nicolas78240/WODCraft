"""The ``wodc`` command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wodcraft import __version__, library
from wodcraft.api import LIBRARY_DIR, compile_file, parse_file
from wodcraft.catalog import load_catalog, normalize
from wodcraft.emit import board
from wodcraft.emit.source import format_source
from wodcraft.profile import Profile
from wodcraft.semantics.resolve import resolve

EXIT_OK, EXIT_DIAGNOSTICS, EXIT_USAGE = 0, 1, 2


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return args.func(args)
    except FileNotFoundError as err:
        print(f"wodc: {err.filename}: no such file", file=sys.stderr)
        return EXIT_USAGE
    except BrokenPipeError:  # pragma: no cover - piping into head/less
        return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wodc",
        description=f"Write, check and compile functional-fitness workouts (WODCraft {__version__}).",
        epilog="Specification: spec/SPEC.md · https://github.com/Nicolas78240/WODCraft",
    )
    parser.add_argument("--version", action="version", version=f"wodc {__version__} (spec 1.0)")
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="check files and report diagnostics")
    _add_input(check)
    check.add_argument("--json", action="store_true", help="machine-readable diagnostics")
    check.add_argument("--quiet", "-q", action="store_true", help="only report errors")
    check.add_argument("--strict", action="store_true", help="treat warnings as errors")
    check.set_defaults(func=cmd_check)

    build = subparsers.add_parser("build", help="compile to JSON")
    _add_input(build)
    build.add_argument("-o", "--output", help="write to this file instead of stdout")
    build.add_argument("--compact", action="store_true", help="single-line JSON")
    build.set_defaults(func=cmd_build)

    show = subparsers.add_parser("show", help="print the whiteboard view")
    _add_input(show)
    _add_profile(show)
    show.set_defaults(func=cmd_show)

    fmt = subparsers.add_parser("fmt", help="rewrite files in canonical form")
    _add_input(fmt)
    fmt.add_argument("--write", "-w", action="store_true", help="rewrite the files in place")
    fmt.add_argument("--check", action="store_true", help="exit 1 if a file is not canonical")
    fmt.set_defaults(func=cmd_fmt)

    timer = subparsers.add_parser("timer", help="print the timeline of a workout")
    _add_input(timer)
    _add_profile(timer)
    timer.set_defaults(func=cmd_timer)

    export = subparsers.add_parser("export", help="export to another format")
    export.add_argument("format", choices=["ics", "markdown", "md"])
    _add_input(export)
    _add_profile(export)
    export.add_argument("-o", "--output", help="write to this file instead of stdout")
    export.set_defaults(func=cmd_export)

    catalog = subparsers.add_parser("catalog", help="explore the movement catalog")
    catalog.add_argument("query", nargs="?", help="search term (name, alias, French name)")
    catalog.add_argument("--family", choices=["M", "G", "W"], help="filter by family")
    catalog.add_argument("--json", action="store_true")
    catalog.set_defaults(func=cmd_catalog)

    library = subparsers.add_parser("lib", help="list the standard workout library")
    library.add_argument("query", nargs="?", help="filter by name")
    library.set_defaults(func=cmd_lib)
    return parser


def _add_input(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("files", nargs="+", help="one or more .wod files ('-' for stdin)")
    sub.add_argument("--lib", action="append", default=[], metavar="DIR", help="extra directory for 'use'")


def _add_profile(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--me", action="store_true", help="resolve with the athlete profile (athlete.toml)")
    sub.add_argument("--profile", metavar="FILE", help="use this athlete profile")
    sub.add_argument("--category", choices=["men", "women"])
    sub.add_argument("--level", help="rx, intermediate, scaled, foundations")
    sub.add_argument("--units", choices=["kg", "lb"])
    sub.add_argument("--lang", choices=["en", "fr"], default="en", help="language of the movement names")


# --------------------------------------------------------------------------- commands


def cmd_check(args) -> int:
    status = EXIT_OK
    payload: list[dict] = []
    for result in _results(args):
        if args.json:
            payload += [dict(d.to_dict(), file=d.span.file or result.path) for d in result.diagnostics]
        else:
            for diagnostic in result.diagnostics:
                if args.quiet and diagnostic.severity.value != "error":
                    continue
                print(diagnostic.format(result.source_lines))
            warnings = len([d for d in result.diagnostics if d.severity.value != "error"])
            if result.ok and not args.quiet:
                if args.strict and warnings:
                    print(f"✗ {result.path}: {warnings} warning{'s' if warnings > 1 else ''} (--strict)")
                else:
                    print(f"✓ {result.path}: valid" + (f" ({warnings} warning{'s' if warnings > 1 else ''})" if warnings else ""))
        if not result.ok or (args.strict and result.diagnostics):
            status = EXIT_DIAGNOSTICS
    if args.json:
        print(json.dumps(payload, indent=2))
    return status


def cmd_build(args) -> int:
    documents: list[dict] = []
    status = EXIT_OK
    for result in _results(args):
        if not result.ok:
            print(result.report(), file=sys.stderr)
            status = EXIT_DIAGNOSTICS
            continue
        documents += result.documents
    if status != EXIT_OK:
        return status
    payload = documents[0] if len(documents) == 1 else documents
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2)
    _write(args.output, text)
    return status


def cmd_show(args) -> int:
    profile = _profile(args)
    status = EXIT_OK
    for result in _results(args):
        if not result.ok:
            print(result.report(), file=sys.stderr)
            status = EXIT_DIAGNOSTICS
            continue
        for document in result.documents:
            if profile is not None:
                document = resolve(document, profile)
            print(board.render(document, lang=getattr(args, "lang", "en")))
            print()
    return status


def cmd_fmt(args) -> int:
    status = EXIT_OK
    for path in _paths(args):
        source_file, diags = parse_file(path)
        if diags.has_errors:
            for diagnostic in diags.sorted():
                print(diagnostic.format(source_file.lines), file=sys.stderr)
            status = EXIT_DIAGNOSTICS
            continue
        formatted = format_source(source_file)
        original = Path(path).read_text(encoding="utf-8")
        if args.check:
            if formatted != original:
                print(f"{path}: not canonical", file=sys.stderr)
                status = EXIT_DIAGNOSTICS
        elif args.write:
            if formatted != original:
                Path(path).write_text(formatted, encoding="utf-8")
                print(f"{path}: formatted")
        else:
            sys.stdout.write(formatted)
    return status


def cmd_timer(args) -> int:
    from wodcraft.emit.timeline import render_timeline, timeline

    profile = _profile(args)
    status = EXIT_OK
    for result in _results(args):
        if not result.ok:
            print(result.report(), file=sys.stderr)
            status = EXIT_DIAGNOSTICS
            continue
        for document in result.documents:
            if profile is not None:
                document = resolve(document, profile)
            print(render_timeline(timeline(document)))
    return status


def cmd_export(args) -> int:
    from wodcraft.emit.ics import IcsError, to_ics
    from wodcraft.emit.markdown import to_markdown

    profile = _profile(args)
    chunks: list[str] = []
    status = EXIT_OK
    for result in _results(args):
        if not result.ok:
            print(result.report(), file=sys.stderr)
            status = EXIT_DIAGNOSTICS
            continue
        for document in result.documents:
            if profile is not None:
                document = resolve(document, profile)
            try:
                chunks.append(to_ics(document) if args.format == "ics" else to_markdown(document))
            except IcsError as err:
                print(f"{result.path}: {err}", file=sys.stderr)
                status = EXIT_DIAGNOSTICS
    if status == EXIT_OK:
        _write(args.output, "\n".join(chunks))
    return status


def cmd_catalog(args) -> int:
    catalog = load_catalog()
    query = normalize(args.query) if args.query else ""

    def matches(movement) -> bool:
        if not query:
            return True
        haystack = [normalize(movement.name), movement.id.replace("_", " "), *(normalize(a) for a in (*movement.aliases, *movement.fr))]
        return any(query in text for text in haystack)

    rows = [m for m in catalog.movements.values() if (not args.family or m.family == args.family) and matches(m)]
    rows.sort(key=lambda m: m.id)
    if args.json:
        print(json.dumps([vars(m) for m in rows], ensure_ascii=False, indent=2, default=list))
        return EXIT_OK
    for movement in rows:
        rx = ""
        if movement.rx:
            unit = movement.rx.get("unit", "kg")
            rx = f"  Rx {movement.rx.get('men')}/{movement.rx.get('women')} {unit}"
        print(f"{movement.id:34} {movement.family}  {', '.join(movement.quantities):24} {movement.name}{rx}")
    print(f"\n{len(rows)} movement{'s' if len(rows) > 1 else ''}" + (f" of {len(catalog)}" if query or args.family else ""))
    return EXIT_OK


def cmd_lib(args) -> int:
    for entry in library.entries(args.query):
        print(f"{entry.path:24} {entry.title}")
    return EXIT_OK


# --------------------------------------------------------------------------- helpers


def _paths(args) -> list[str]:
    """File paths, or names from the standard library ('girls/fran')."""
    out: list[str] = []
    for name in args.files:
        if name == "-" or Path(name).exists():
            out.append(name)
            continue
        candidate = LIBRARY_DIR / (name if name.endswith(".wod") else name + ".wod")
        out.append(str(candidate) if candidate.is_file() else name)
    return out


def _results(args):
    library_paths = [Path(p) for p in getattr(args, "lib", [])]
    for path in _paths(args):
        if path == "-":
            from wodcraft.api import compile_source

            yield compile_source(sys.stdin.read(), "<stdin>", library_paths=library_paths)
        else:
            yield compile_file(path, library_paths=library_paths)


def _profile(args) -> Profile | None:
    overrides = any(getattr(args, key, None) for key in ("category", "level", "units"))
    if not (args.me or args.profile or overrides):
        return None
    profile = Profile.load(args.profile) if args.profile else (Profile.discover() or Profile())
    return profile.with_overrides(args.category, args.level, args.units)


def _write(output: str | None, text: str) -> None:
    if output:
        Path(output).write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
