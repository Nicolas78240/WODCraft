#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
import os


def detect_mode_from_text(text: str) -> str:
    t = text
    if any(kw in t for kw in ("programming",)):
        return "vnext"
    if any(kw in t for kw in ("module ", "session ", "vars {", "imports ", "components {", "realized {", "achievements {")):
        return "vnext"
    if any(kw in t for kw in ("WOD ", "BLOCK ", "AMRAP", "EMOM", "RFT", "FT")):
        return "legacy"
    return "legacy"


def cmd_lint(args):
    p = Path(args.file)
    text = p.read_text()
    mode = args.mode or detect_mode_from_text(text)
    # language-first only
    # Prefer programming lint if block present; else validate
    from wodcraft.lang.core import ProgrammingLinter, parse_vnext
    if "programming" in text:
        ast = parse_vnext(text)
        reports = []
        for blk in ast.get("programming", []):
            data = blk.get("data", {})
            issues = ProgrammingLinter().lint(data)
            reports.append({"programming": data.get("macrocycle", {}).get("name"), "issues": issues})
        print(json.dumps({"reports": reports}, indent=2))
        return 2 if any(any(i.get("level") == "error" for i in r.get("issues", [])) for r in reports) else 0
    else:
        # Lint modules: find common structural issues
        try:
            ast = parse_vnext(text)
        except Exception as e:
            print(f"✗ Invalid syntax: {e}")
            return 1
        issues = []
        modules = ast.get("modules", [])
        for m in modules:
            mid = m.get("id", "<module>")
            body = m.get("body")
            comps = []
            # Flatten containers
            def collect(node):
                if isinstance(node, dict):
                    t = node.get("type")
                    if t in ("WARMUP","WOD","SKILL","STRENGTH"):
                        comps.append(node)
                    elif t in ("MODULE_BODY","BODY"):
                        for ch in node.get("children", []):
                            collect(ch)
                    else:
                        # attempt to collect nested dicts
                        for v in node.values():
                            collect(v)
                elif isinstance(node, list):
                    for v in node: collect(v)
            collect(body)
            if not comps:
                issues.append(("warning","M101", f"Module '{mid}' has no components"))
            for c in comps:
                ct = c.get("type")
                if ct == "WOD":
                    mv = c.get("movements") or []
                    if not mv:
                        issues.append(("warning","M102", f"WOD in '{mid}' has no movements"))
                elif ct == "WARMUP":
                    bl = c.get("blocks") or []
                    if not bl:
                        issues.append(("warning","M103", f"Warmup in '{mid}' has no blocks"))
                elif ct in ("SKILL","STRENGTH"):
                    wk = c.get("work") or {}
                    lines = wk.get("lines") or []
                    if not lines:
                        issues.append(("warning","M104", f"{ct.title()} in '{mid}' has no work lines"))
        if issues:
            for lvl, code, msg in issues:
                print(f"{lvl.upper()} {code} {args.file}: {msg}")
        else:
            print("✓ Valid WODCraft syntax")
        # Treat warnings as success
        return 0


def cmd_parse(args):
    text = Path(args.file).read_text()
    mode = args.mode or detect_mode_from_text(text)
    if mode == "legacy":
        # Legacy not supported in clean mode — fallback to language parser
        from wodcraft.lang.core import parse_vnext
        ast = parse_vnext(text)
    else:
        from wodcraft.lang.core import parse_vnext
        ast = parse_vnext(text)
    print(json.dumps(ast, indent=2))
    return 0


def _to_seconds(tok: str) -> int:
    s = str(tok).strip()
    if ":" in s:
        try:
            m, sec = s.split(":", 1)
            return int(m) * 60 + int(sec)
        except Exception:
            return 0
    if s.endswith("min"):
        try:
            return int(s[:-3]) * 60
        except Exception:
            return 0
    if s.endswith("m"):
        try:
            return int(s[:-1]) * 60
        except Exception:
            return 0
    if s.endswith("h"):
        try:
            return int(s[:-1]) * 3600
        except Exception:
            return 0
    if s.endswith("s"):
        try:
            return int(s[:-1])
        except Exception:
            return 0
    try:
        return int(s)
    except Exception:
        return 0


def _flatten_form(node):
    if isinstance(node, (str, int, float)):
        yield str(node)
    elif isinstance(node, dict):
        # Try explicit keys first
        if "type" in node and isinstance(node["type"], str) and node["type"] not in ("WOD", "WOD_FORM"):
            yield str(node["type"])
        for v in node.values():
            if isinstance(v, (list, dict, str, int, float)):
                yield from _flatten_form(v)
    elif isinstance(node, list):
        for v in node:
            yield from _flatten_form(v)


def _infer_wod_form(form) -> tuple[str, int | None]:
    # Returns (form_type, duration_seconds or None)
    toks = list(_flatten_form(form))
    ftype = None
    dur = None
    # pick first known keyword
    for kw in ("AMRAP", "EMOM", "ForTime", "RFT", "TABATA"):
        if any(kw.lower() == t.lower() for t in toks):
            ftype = kw
            break
    # look for duration-like tokens
    for t in toks:
        if any(ch.isdigit() for ch in t) and any(ch in t for ch in (":", "m", "min", "s", "h")):
            sec = _to_seconds(t)
            if sec:
                dur = sec
                break
    # ForTime can specify cap after 'cap'
    if (ftype == "ForTime" or (ftype is None and any("ForTime" in t for t in toks))) and dur is None:
        # scan for token 'cap' then next duration token
        for i, t in enumerate(toks):
            if t.lower() == "cap" and i + 1 < len(toks):
                sec = _to_seconds(toks[i + 1])
                if sec:
                    dur = sec
                    break
    return (ftype or "WOD", dur)


def cmd_run(args):
    # Unified WODCraft run: compile session and emit a simple timeline
    from wodcraft.lang.core import parse_vnext, FileSystemResolver, SessionCompiler
    p = Path(args.file)
    text = p.read_text()
    ast = parse_vnext(text)
    if not ast.get("sessions"):
        print("✗ No session found in file")
        return 1
    resolver = FileSystemResolver(Path(args.modules_path))
    compiler = SessionCompiler(resolver)
    session_ast = ast["sessions"][0]
    compiled = compiler.compile_session(session_ast)
    sess = compiled.get("session", {})
    comps = sess.get("components", {})
    t = 0
    total = 0
    unknown = False
    segments = []
    order = ["warmup", "skill", "strength", "wod"]
    for kind in order:
        if kind in comps:
            comp = comps[kind].get("component", {})
            title = comp.get("title") or kind.title()
            seg = {"kind": kind, "title": title, "start_s": t}
            dur = None
            if kind == "wod":
                form = comp.get("form")
                ftype, fdur = _infer_wod_form(form)
                seg["form"] = ftype
                if fdur:
                    dur = fdur
            # Accumulate
            seg["duration_s"] = dur
            segments.append(seg)
            if dur is None:
                unknown = True
            else:
                t += dur
                total += dur
    timeline = {
        "session_title": sess.get("title"),
        "total_duration_s": None if unknown else total,
        "segments": segments,
    }
    if args.format == "json":
        print(json.dumps({"timeline": timeline}, indent=2))
    else:
        # text
        lines = [f"Session: {timeline['session_title']}"]
        for seg in segments:
            base = f"- {seg['kind'].title()}: {seg['title']}"
            if seg.get("form"):
                base += f" ({seg['form']})"
            if seg.get("duration_s"):
                base += f" — {seg['duration_s']}s"
            lines.append(base)
        if timeline["total_duration_s"] is not None:
            lines.append(f"Total: {timeline['total_duration_s']}s")
        print("\n".join(lines))
    return 0


def cmd_export(args):
    # legacy only, thin shim to JSON/HTML/ICS via existing module
    print("Legacy 'export' not supported in clean language-first mode.")
    return 1


def cmd_validate(args):
    text = Path(args.file).read_text()
    from wodcraft.lang.core import parse_vnext
    try:
        parse_vnext(text)
        print("✓ Valid WODCraft vNext syntax")
        return 0
    except Exception as e:
        print(f"✗ Invalid syntax: {e}")
        return 1


def cmd_session(args):
    from wodcraft.lang.core import parse_vnext, FileSystemResolver, SessionCompiler
    text = Path(args.file).read_text()
    ast = parse_vnext(text)
    if not ast.get("sessions"):
        print("✗ No session found in file")
        return 1
    resolver = FileSystemResolver(Path(args.modules_path))
    compiler = SessionCompiler(resolver)
    session_ast = ast["sessions"][0]
    compiled = compiler.compile_session(session_ast)
    if args.format == "json":
        print(compiler.export_json(compiled))
    elif args.format == "ics":
        print(compiler.export_ics(compiled))
    else:
        print(json.dumps(compiled, indent=2))
    return 0


def cmd_results(args):
    from wodcraft.lang.core import parse_vnext, FileSystemResolver, SessionCompiler, TeamRealizedAggregator
    text = Path(args.file).read_text()
    ast = parse_vnext(text)
    if not ast.get("sessions"):
        print("✗ No session found in file")
        return 1
    resolver = FileSystemResolver(Path(args.modules_path))
    compiler = SessionCompiler(resolver)
    session_ast = ast["sessions"][0]
    compiled = compiler.compile_session(session_ast)
    results = compiled.get("session", {}).get("results")
    if not results:
        results = TeamRealizedAggregator().aggregate(session_ast, compiled.get("session", {})) or {}
    print(json.dumps({"results": results}, indent=2))
    return 0


def cmd_catalog_build(args):
    # thin wrapper
    from scripts.build_catalog import main as build
    build()
    return 0


REPO_URL = os.environ.get("WODCRAFT_DOCS_URL", "https://github.com/Nicolas78240/WODCraft")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="wodc",
        description=(
            "WODCraft CLI — parse, lint, run, and export WODCraft sessions.\n\n"
            "Common tasks:\n"
            "  - Validate syntax:      wodc validate file.wod\n"
            "  - Parse to JSON AST:    wodc parse file.wod\n"
            "  - Build catalog:        wodc catalog build\n"
            "  - Compile a session:    wodc session file.wod --modules-path modules --format json\n"
            "  - Timeline summary:     wodc run file.wod --modules-path modules --format text\n\n"
            f"Docs & issues: {REPO_URL}\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    # --version support
    try:
        from importlib.metadata import version as _pkg_version  # type: ignore
        ap.add_argument("--version", action="version", version=f"wodc {_pkg_version('wodcraft')}")
    except Exception:
        ap.add_argument("--version", action="version", version="wodc")
    sub = ap.add_subparsers(dest="cmd")

    p_parse = sub.add_parser(
        "parse",
        help="Parse a WODCraft file and print its JSON AST",
        description=(
            "Parse a WODCraft source file and emit a JSON AST.\n\n"
            "Examples:\n  wodc parse examples/language/team_realized_session.wod"
        ),
    )
    p_parse.add_argument("file", help="Path to .wod file")
    p_parse.add_argument("--mode", choices=["legacy", "vnext"], help=argparse.SUPPRESS)
    p_parse.set_defaults(func=cmd_parse)

    p_lint = sub.add_parser(
        "lint",
        help="Lint WODCraft (programming or module structure) and report issues",
        description=(
            "Lint the file. If a programming block is present, runs the programming linter;\n"
            "otherwise, performs structural checks on modules.\n\n"
            "Examples:\n  wodc lint examples/language/programming_plan.wod"
        ),
    )
    p_lint.add_argument("file", help="Path to .wod file")
    p_lint.add_argument("--mode", choices=["legacy", "vnext"], help=argparse.SUPPRESS)
    p_lint.set_defaults(func=cmd_lint)

    p_run = sub.add_parser(
        "run",
        help="Produce a simple timeline summary from a session",
        description=(
            "Compile the session and emit a simple, best-effort timeline summary\n"
            "for warmup/skill/strength/wod segments.\n\n"
            "Examples:\n  wodc run file.wod --modules-path modules --format text"
        ),
    )
    p_run.add_argument("file", help="Path to .wod file with a session block")
    p_run.add_argument("--modules-path", default="modules", help="Path to modules directory")
    p_run.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    p_run.set_defaults(func=cmd_run)

    p_export = sub.add_parser(
        "export",
        help="(Reserved) Additional export formats",
        description=(
            "Reserved for future export formats beyond session JSON/ICS.\n"
            "Use `wodc session ... --format json|ics` for session exports."
        ),
    )
    p_export.add_argument("file", help="Path to .wod file")
    p_export.add_argument("--to", choices=["json", "html", "ics"], required=True, help="Target format")
    p_export.set_defaults(func=cmd_export)

    p_validate = sub.add_parser(
        "validate",
        help="Validate WODCraft syntax",
        description=(
            "Validate the file against the WODCraft grammar.\n\n"
            "Examples:\n  wodc validate file.wod"
        ),
    )
    p_validate.add_argument("file", help="Path to .wod file")
    p_validate.set_defaults(func=cmd_validate)

    p_session = sub.add_parser(
        "session",
        help="Compile a session (resolve modules) and export JSON or ICS",
        description=(
            "Compile the first session in the file: resolves module imports, applies overrides,\n"
            "and exports a structured session JSON or an ICS calendar event.\n\n"
            "Examples:\n  wodc session file.wod --modules-path modules --format json"
        ),
    )
    p_session.add_argument("file", help="Path to .wod file with a session block")
    p_session.add_argument("--modules-path", default="modules", help="Path to modules directory")
    p_session.add_argument("--format", choices=["json", "ics"], default="json", help="Export format")
    p_session.set_defaults(func=cmd_session)

    p_results = sub.add_parser(
        "results",
        help="Aggregate team realized events into a score",
        description=(
            "Aggregate team realized events (if present) per session scoring policy.\n\n"
            "Examples:\n  wodc results file.wod --modules-path modules"
        ),
    )
    p_results.add_argument("file", help="Path to .wod file with a session block")
    p_results.add_argument("--modules-path", default="modules", help="Path to modules directory")
    p_results.set_defaults(func=cmd_results)

    p_cat = sub.add_parser(
        "catalog",
        help="Catalog utilities (build movements catalog)",
        description=(
            "Utilities around the movements catalog.\n\n"
            "Examples:\n  wodc catalog build"
        ),
    )
    p_cat_sub = p_cat.add_subparsers(dest="cat_cmd")
    p_cat_build = p_cat_sub.add_parser("build", help="Build movements catalog from sources")
    p_cat_build.set_defaults(func=cmd_catalog_build)

    args = ap.parse_args(argv)
    if not hasattr(args, "func"):
        ap.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
