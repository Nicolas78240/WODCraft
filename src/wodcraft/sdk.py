#!/usr/bin/env python3
"""
WODCraft SDK — Developer-friendly functions to use the WODCraft language
without exposing internal names. Import from here for stable integration.

Examples:
  from wodcraft import sdk
  ok, err = sdk.validate(text)
  ast = sdk.parse(text)
  compiled = sdk.compile_session(text, modules_path="modules")
  ics = sdk.export_ics(compiled)
  agg = sdk.results(text, modules_path="modules")
  tl = sdk.run(text, modules_path="modules")
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .lang.core import (
    parse_vnext,
    FileSystemResolver,
    SessionCompiler,
    TeamRealizedAggregator,
)


def parse(text: str) -> Dict[str, Any]:
    """Parse WODCraft source to an AST dict."""
    return parse_vnext(text)


def validate(text: str) -> Tuple[bool, Optional[str]]:
    """Validate WODCraft source. Returns (ok, error_message)."""
    try:
        parse_vnext(text)
        return True, None
    except Exception as e:
        return False, str(e)


def compile_session(text: str, modules_path: str | Path = "modules") -> Dict[str, Any]:
    """Compile the first session in the given source. Raises if no session found."""
    ast = parse_vnext(text)
    sessions = ast.get("sessions") or []
    if not sessions:
        raise ValueError("No session found in source")
    session_ast = sessions[0]
    resolver = FileSystemResolver(Path(modules_path))
    compiler = SessionCompiler(resolver)
    return compiler.compile_session(session_ast)


def export_ics(compiled_session: Dict[str, Any]) -> str:
    """Export an already compiled session to ICS string."""
    dummy = SessionCompiler(FileSystemResolver(Path(".")))
    return dummy.export_ics(compiled_session)


def results(text: str, modules_path: str | Path = "modules") -> Dict[str, Any]:
    """Compile the session and aggregate team realized results if present."""
    compiled = compile_session(text, modules_path)
    session_obj = compiled.get("session", {})
    res = session_obj.get("results")
    if res:
        return res
    # Aggregate on the fly
    ast = parse_vnext(text)
    sessions = ast.get("sessions") or []
    if not sessions:
        return {}
    agg = TeamRealizedAggregator().aggregate(sessions[0], session_obj)
    return agg or {}


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


def _flatten(node):
    if isinstance(node, (str, int, float)):
        yield str(node)
    elif isinstance(node, dict):
        if "type" in node and isinstance(node["type"], str) and node["type"] not in ("WOD", "WOD_FORM"):
            yield str(node["type"])
        for v in node.values():
            if isinstance(v, (list, dict, str, int, float)):
                yield from _flatten(v)
    elif isinstance(node, list):
        for v in node:
            yield from _flatten(v)


def _infer_wod_form(form) -> tuple[str, Optional[int]]:
    toks = list(_flatten(form))
    ftype = None
    dur = None
    for kw in ("AMRAP", "EMOM", "ForTime", "RFT", "TABATA"):
        if any(kw.lower() == t.lower() for t in toks):
            ftype = kw
            break
    for t in toks:
        if any(ch.isdigit() for ch in t) and any(ch in t for ch in (":", "m", "min", "s", "h")):
            sec = _to_seconds(t)
            if sec:
                dur = sec
                break
    if (ftype == "ForTime" or (ftype is None and any("ForTime" in t for t in toks))) and dur is None:
        for i, t in enumerate(toks):
            if t.lower() == "cap" and i + 1 < len(toks):
                sec = _to_seconds(toks[i + 1])
                if sec:
                    dur = sec
                    break
    return (ftype or "WOD", dur)


def run(text: str, modules_path: str | Path = "modules") -> Dict[str, Any]:
    """Produce a simple timeline summary from the first session in source."""
    compiled = compile_session(text, modules_path)
    sess = compiled.get("session", {})
    comps = sess.get("components", {})
    t = 0
    total = 0
    unknown = False
    segments = []
    for kind in ["warmup", "skill", "strength", "wod"]:
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
            seg["duration_s"] = dur
            segments.append(seg)
            if dur is None:
                unknown = True
            else:
                t += dur
                total += dur
    return {
        "session_title": sess.get("title"),
        "total_duration_s": None if unknown else total,
        "segments": segments,
    }

