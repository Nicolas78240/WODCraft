#!/usr/bin/env python3
"""
WODCraft Language Core

A comprehensive implementation of the WODCraft Domain-Specific Language (DSL) for
describing CrossFit workouts, sessions, and programming blocks. This module provides:

Core Features:
- Extended EBNF grammar parsing with Lark
- Module system with versioning and resolution
- Session compilation with component imports and overrides
- Semantic validation for CrossFit-specific logic
- Enhanced error reporting with line/column context
- Intelligent LRU caching for improved performance
- Support for team/realized/achievements tracking

Architecture:
- parse_vnext(): Entry point for parsing WODCraft source code
- ToASTvNext: AST transformer with detailed structure conversion
- SessionCompiler: Compiles sessions by resolving module imports
- WODCraftError: Enhanced error reporting with source context
- ModuleResolver: Abstract interface for module resolution
- FileSystemResolver: File-based module resolution with caching

Type System:
- Load, Distance types with unit conversion
- TypeSpec definitions for validation
- Movement semantic validation
- CrossFit methodology compliance checking

Enhanced for Agent Development:
This monolithic architecture is optimized for AI agents, providing complete
context visibility while maintaining clean separation of concerns.
"""

import sys, json, argparse, re, os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from lark import Lark, Transformer, Token, Tree, LarkError
from lark.exceptions import UnexpectedCharacters, UnexpectedToken
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
import time
from collections import OrderedDict

# Extended EBNF Grammar for the WODCraft DSL
GRAMMAR_VNEXT = r"""
start: program

program: (module | session | programming_block)*

// Module System
module: "module" qualified_id version? "{" module_body "}"
qualified_id: IDENT ("." IDENT)*
version: "v" INT ("." INT)?

module_body: (annotation | vars_decl | body)*
annotation: "@" IDENT "(" [arg_list] ")"
arg_list: value ("," value)*

vars_decl: "vars" "{" var_decl* "}"
// Allow keywords like 'sets' and 'tempo' as variable names in vars
var_decl: (IDENT | SETS | TEMPO | REPS) ":" type_spec ["=" literal] [constraints]
constraints: "[" constraint ("," constraint)* "]"
constraint: "min" "=" literal
          | "max" "=" literal
          | "pattern" "=" STRING
          | "enum" "=" array

body: warmup | skill | strength | wod | score_decl | notes_decl

// Component Types
warmup: "warmup" STRING "{" block* "}"
block: "block" STRING ["repeat" INT] "{" movement_line* "}"

skill: "skill" STRING "{" work cues "}"
strength: "strength" STRING "{" work cues "}"
work: "work" "{" work_line* "}"
cues: "cues" "{" STRING* "}"
work_line: movement_line | scheme_line
scheme_line: SETS (INT|IDENT) REPS (INT|IDENT) ["@" (load_value|IDENT)] [TEMPO (tempo_value|IDENT)]

wod: "wod" wod_form "{" wod_item* "}"
wod_item: movement_line | wod_rest | wod_notes_decl
wod_rest: "REST" duration
wod_notes_decl: "notes" ":" value
wod_form: "AMRAP" duration
        | "ForTime" ["cap" duration]
        | "EMOM" duration
        | "RFT" INT
        | "TABATA"
        | IDENT

movement_line: (INT "x" reps_spec | INT XINT | reps_spec | MAXREP) movement_name progress_clause? [load_spec] [tempo_spec] [note]
progress_clause: "PROGRESS" "(" STRING ")"
reps_spec: INT | duration | DIST | CALDUAL
movement_name: IDENT ("_" IDENT)*
load_spec: "@" (load_dual | load_variant | load_value | IDENT)
load_dual: load_value "/" load_value
load_variant: IDENT "(" load_variant_entry ("," load_variant_entry)* ")"
load_variant_entry: IDENT ":" load_variant_amount
load_variant_amount: load_value | NUMBER | IDENT | STRING
load_value: NUMBER (UNIT_WEIGHT | UNIT_HEIGHT)
tempo_spec: TEMPO (tempo_value | IDENT)
tempo_value: STRING
note: STRING

notes_decl: "notes" ":" value

score_decl: "score" IDENT "{" field_decl ("," field_decl)* "}"
field_decl: IDENT ":" type_spec

// Session System
session: "session" STRING "{" components scoring [session_meta] [exports] [team_block] [realized_block] [achievements_block] "}"

components: "components" "{" component_import* "}"
component_import: comp_key import_stmt
comp_key: "warmup" | "skill" | "strength" | "wod"

import_stmt: "import" ref_id ["@" version] [override_clause]
ref_id: qualified_id
override_clause: "override" "{" assign* "}"
assign: (IDENT|TEMPO|SETS|REPS) "=" value

scoring: "scoring" "{" scoring_rule* "}"
scoring_rule: comp_key score_policy
score_policy: "none" | IDENT [format_spec]
format_spec: IDENT ("+" IDENT)*

session_meta: "meta" "{" meta_entry* "}"
meta_entry: IDENT "=" value

exports: "exports" "{" export_spec* "}"
export_spec: "json" | "html" | "ics"

// Team/Realized/Achievements extensions (PRD3-aligned; optional)
team_block: "team" object
realized_block: "realized" object
achievements_block: "achievements" object

// Coach Programming (PRD3) — optional top-level block
programming_block: "programming" object

// Type System
type_spec: "Time"
         | "Rounds"
         | "Reps"
         | "Load" "(" unit_set ")"
         | "Distance" "(" unit_set ")"
         | "Calories"
         | "Tempo"
         | "Int" | "Float" | "Bool" | "String"
         | enum_type

enum_type: "Enum" "(" array ")"
unit_set: (IDENT | PCT1RM) ("|" (IDENT | PCT1RM))*

// Values and Literals
value: literal | array | object
array: "[" [value ("," value)*] "]"
object: "{" [key_value ("," key_value)*] "}"
key_value: IDENT ":" value

literal: NUMBER | STRING | bool_val | duration | load_value | percentage
bool_val: "true" | "false"
duration: INT ":" INT | INT "m" | INT "s" | INT "min" | INT "h"
percentage: NUMBER "%"
datetime: STRING
PCT1RM: "%1RM"
SETS: "sets"
REPS: "reps"
TEMPO: "tempo"
XINT.2: /x\d+/
MAXREP: /(?i:maxrep)/
DIST: /\d+(?:\.\d+)?(?:m|km)\b/

// Legacy WOD support (from original grammar)
legacy_wod: wod_meta* segment*
?wod_meta: title | team | cap_line | score_line | tracks_decl
title: "WOD" STRING
team: "TEAM" INT
cap_line: "CAP" time
score_line: "SCORE" SCORE_RAW
SCORE_RAW: /[^\n]+/
tracks_decl: "TRACKS" "[" track_id ("," track_id)* "]"
track_id: "RX" | "SCALED" | "BEGINNER" | IDENT

?segment: score_line | buyin | cashout | rest | legacy_block | track_block
buyin: "BUYIN" "{" stmt+ "}"
cashout: "CASHOUT" "{" stmt+ "}"
rest: "REST" time
legacy_block: "BLOCK" block_head block_opt* "{" stmt+ "}" tiebreak?
block_opt: workmode | partition | cap_local

block_head: amrap_head | emom_head | ft_head | rft_head | chipper_head | tabata_head | interval_head
amrap_head: "AMRAP" time
emom_head: "EMOM" time
ft_head: "FT"
rft_head: "RFT" INT
chipper_head: "CHIPPER"
tabata_head: "TABATA" time ":" time "x" INT
interval_head: "INTERVAL" INT "x" "(" time "on" "/" time "off" ")"

workmode: "WORK" "split:any" -> work_split_any
        | "WORK" "split:even" -> work_split_even
        | "WORK" "ygig" -> work_ygig
        | "WORK" "relay" -> work_relay
        | "WORK" "waterfall" "offset:" time -> work_waterfall
        | "WORK" "synchro" "all" -> work_synchro_all
        | "WORK" "synchro" "lines:" "[" INT ("," INT)* "]" -> work_synchro_lines

partition: "PARTITION" "any" -> part_any
         | "PARTITION" "even" -> part_even
         | "PARTITION" "scheme" rep_scheme -> part_scheme

cap_local: "CAP" time
tiebreak: "TIEBREAK" "after" INT "thrusters" -> tb_thrusters
        | "TIEBREAK" "after" INT "reps" -> tb_reps
        | "TIEBREAK" "after" INT "cal" -> tb_cal
        | "TIEBREAK" "after" "movement" IDENT -> tb_movement

?stmt: emom_stmt | line
emom_stmt: INT ":" line

line: quantity? movement load? suffix* (";"|NEWLINE)

quantity: REPDUAL -> dual_reps
        | CALDUAL -> dual_cal
        | DISTDUAL -> dual_distance
        | INT -> reps
        | NUMBER "cal" -> cal_qty
        | DIST -> distance_qty
        | shorthand_macro
        | TIMEQ -> hold_time

shorthand_macro: SHORTHAND_PATTERN movement_list_with_loads
movement_list_with_loads: movement load? ("+" movement load?)*

movement: IDENT ("_" IDENT)*
load: "@" (LOADVAL|LOADDUAL|PERCENT_LOAD)

suffix: "SYNC" -> suff_sync
      | "@shared" -> suff_shared
      | "@each" -> suff_each

rep_scheme: INT ("-" INT)*

time: INT ":" INT -> mmss
    | INT "m" -> only_m
    | INT "s" -> only_s

track_block: "TRACK" IDENT "{" /[^}]+/ "}"

// Terminals (avoid duplicating DIST; defined earlier)
TIMEQ: /\d{1,2}:\d{2}/ | /\d+s/
LOADVAL: /\d+(?:\.\d+)?(kg|lb|cm|in|m|km|%|%1RM)\b/
LOADDUAL: /\d+(?:\.\d+)?\/\d+(?:\.\d+)?(kg|lb|cm|in|m|km|%|%1RM)\b/
PERCENT_LOAD: /\d+(?:\.\d+)?%(?:1RM)?/
SHORTHAND_PATTERN: /\d+(-\d+)+/  // e.g., 21-15-9, 5-10-15-20
REPDUAL: /\d+\/\d+/
CALDUAL: /\d+(?:\.\d+)?\/\d+(?:\.\d+)?\s*cal/
DISTDUAL: /\d+(?:\.\d+)?\/\d+(?:\.\d+)?(?:m|km)\b/
UNIT_WEIGHT: /(kg|lb|%1RM)/
// Height units must be defined before IDENT to have priority
UNIT_HEIGHT: /(in|cm|ft)/

// Identifiers: allow ASCII letters, digits, underscore, and common Latin-1 letters
IDENT: /[A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF][A-Za-z0-9_\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF]*/
STRING: ESCAPED_STRING

// Comments
COMMENT: /\/\/[^\n]*/
MLCOMMENT: /\/\*[\s\S]*?\*\//

%import common.INT
%import common.NUMBER
%import common.WS
%import common.NEWLINE
%import common.ESCAPED_STRING

%ignore WS
%ignore COMMENT
%ignore MLCOMMENT
"""

PROGRESS_RE = re.compile(r"(?P<sign>[+-]?)(?P<value>\d+(?:\.\d+)?)(?P<unit>[A-Za-z%]*)\s*/\s*(?P<cadence>[A-Za-z_][A-Za-z0-9_-]*)")
DISTANCE_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)(?P<unit>m|km)$", re.IGNORECASE)
CAL_DUAL_RE = re.compile(r"^(?P<male>\d+(?:\.\d+)?)/(?P<female>\d+(?:\.\d+)?)(?:\s*cal)?$", re.IGNORECASE)
CAL_SINGLE_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)(?:\s*cal)$", re.IGNORECASE)

GENDER_ALIAS_MAP = {
    "m": "male",
    "male": "male",
    "men": "male",
    "man": "male",
    "f": "female",
    "female": "female",
    "women": "female",
    "woman": "female",
}

# Type System
class UnitType(Enum):
    KG = "kg"
    LB = "lb"
    PERCENT_1RM = "%1RM"
    M = "m"
    KM = "km"
    CAL = "cal"

@dataclass
class TypeSpec:
    name: str
    units: Optional[List[UnitType]] = None
    constraints: Optional[Dict[str, Any]] = None

@dataclass
class Load:
    value: float
    unit: UnitType

    def to_kg(self, one_rm_kg: Optional[float] = None) -> 'Load':
        """Convert load to kg"""
        if self.unit == UnitType.KG:
            return self
        elif self.unit == UnitType.LB:
            kg = self.value * 0.453592
            kg_rounded = round(kg, 1)
            # Avoid rounding tiny positive values to 0.0
            if self.value > 0 and kg_rounded == 0.0:
                kg_rounded = 0.1
            return Load(kg_rounded, UnitType.KG)
        elif self.unit == UnitType.PERCENT_1RM:
            if one_rm_kg is None or one_rm_kg <= 0:
                raise ValueError("1RM required for %1RM conversion")
            return Load(round(self.value * one_rm_kg / 100, 1), UnitType.KG)
        else:
            raise ValueError(f"Cannot convert {self.unit} to kg")

    def to_lb(self, one_rm_kg: Optional[float] = None) -> 'Load':
        """Convert load to pounds"""
        if self.unit == UnitType.LB:
            return self
        elif self.unit == UnitType.KG:
            lb = self.value * 2.20462
            lb_rounded = round(lb, 1)
            # Avoid rounding tiny positive values to 0.0
            if self.value > 0 and lb_rounded == 0.0:
                lb_rounded = 0.1
            return Load(lb_rounded, UnitType.LB)
        elif self.unit == UnitType.PERCENT_1RM:
            if one_rm_kg is None or one_rm_kg <= 0:
                raise ValueError("1RM required for %1RM conversion")
            kg_load = Load(round(self.value * one_rm_kg / 100, 1), UnitType.KG)
            return kg_load.to_lb()
        else:
            raise ValueError(f"Cannot convert {self.unit} to lb")

    def auto_convert_for_preference(self, preferred_unit: UnitType, one_rm_kg: Optional[float] = None) -> 'Load':
        """Auto-convert to preferred unit system"""
        if preferred_unit == UnitType.KG:
            return self.to_kg(one_rm_kg)
        elif preferred_unit == UnitType.LB:
            return self.to_lb(one_rm_kg)
        else:
            return self

@dataclass
class Distance:
    value: float
    unit: UnitType

    def to_m(self) -> 'Distance':
        """Convert distance to meters"""
        if self.unit == UnitType.M:
            return self
        elif self.unit == UnitType.KM:
            return Distance(self.value * 1000, UnitType.M)
        else:
            raise ValueError(f"Cannot convert {self.unit} to meters")


class WODCraftError(Exception):
    """Base exception for WODCraft errors with enhanced context"""
    def __init__(self, message: str, line: Optional[int] = None, column: Optional[int] = None,
                 source_line: Optional[str] = None, suggestion: Optional[str] = None):
        self.line = line
        self.column = column
        self.source_line = source_line
        self.suggestion = suggestion
        super().__init__(message)

    def __str__(self):
        msg = super().__str__()
        if self.line is not None:
            msg = f"Line {self.line}: {msg}"
            if self.column is not None:
                msg = f"Line {self.line}, Column {self.column}: {msg}"
        if self.source_line:
            msg += f"\n  > {self.source_line.strip()}"
            if self.column is not None:
                msg += f"\n  > {' ' * (self.column - 1)}^"
        if self.suggestion:
            msg += f"\n  Suggestion: {self.suggestion}"
        return msg


def _parse_mmss(t: str) -> Optional[int]:
    """
    Parse MM:SS time format to total seconds.

    Args:
        t: Time string in format "MM:SS" (e.g., "12:30")

    Returns:
        Total seconds as integer, or None if parsing fails

    Examples:
        >>> _parse_mmss("12:30")
        750
        >>> _parse_mmss("5:00")
        300
    """
    try:
        if isinstance(t, str) and ":" in t:
            m, s = t.split(":", 1)
            return int(m) * 60 + int(s)
    except Exception:
        return None
    return None


class TeamRealizedAggregator:
    """Aggregate team realized events per PRD3 (lightweight, tolerant).

    Supports:
    - AMRAP reps: sum of event values
    - ForTime: completion_time from latest event timestamp
    - Max load: max load/value
    - Relay: only count events from the athlete whose turn it is
    - Synchro: if sync constraints present, only count events with athlete list within window
    """

    def aggregate(self, session_ast: Dict, compiled_session: Dict) -> Optional[Dict]:
        realized = session_ast.get("realized", {})
        team = session_ast.get("team", {})
        if not isinstance(realized, dict) or not realized.get("data"):
            return None
        data = realized["data"]
        events = data.get("events", []) or []
        if not events:
            return None

        # Determine scoring mode, prefer session.scoring.wod if available
        scoring = compiled_session.get("scoring", {})
        wod_scoring = None
        if isinstance(scoring, dict):
            wod_scoring = scoring.get("wod") or scoring.get("WOD") or scoring.get("Skill")

        # Normalize and filter events according to team policy
        tpol = team.get("data", {}).get("policy", {}) if isinstance(team, dict) else {}
        ordered_events = self._filter_relay(events, tpol)

        constraints = session_ast.get("components", {})
        # Placeholder: constraints for sync could be encoded elsewhere; PRD3 sample puts under wod.constraints
        # If module AST provides constraints, they are not here; accept per-event sync info

        result = {
            "total_events": len(ordered_events),
            "by_athlete": {},
        }

        # Aggregate per-athlete counts
        for ev in ordered_events:
            athletes = ev.get("athlete")
            if isinstance(athletes, list):
                ids = athletes
            elif isinstance(athletes, str):
                ids = [athletes]
            else:
                ids = ["unknown"]
            for aid in ids:
                result["by_athlete"].setdefault(aid, 0)
                result["by_athlete"][aid] += 1

        # Compute primary score per mode
        mode = self._infer_mode(scoring, data)
        if mode == "amrap_reps":
            total = 0
            for ev in ordered_events:
                val = ev.get("value")
                if isinstance(val, (int, float)):
                    total += val
            result["score"] = {"type": "AMRAP", "reps": total}
        elif mode == "max_load":
            maxv = None
            for ev in ordered_events:
                # Prefer load field, fallback to value
                val = ev.get("load") if ev.get("load") is not None else ev.get("value")
                if isinstance(val, (int, float)):
                    maxv = val if maxv is None else max(maxv, val)
            result["score"] = {"type": "MAX_LOAD", "value": maxv or 0}
        elif mode == "for_time":
            last = 0
            for ev in ordered_events:
                t = ev.get("at")
                sec = _parse_mmss(t) if isinstance(t, str) else None
                if isinstance(sec, int):
                    last = max(last, sec)
            result["score"] = {"type": "FOR_TIME", "time_s": last}
        else:
            # Default: sum reps
            total = 0
            for ev in ordered_events:
                val = ev.get("value")
                if isinstance(val, (int, float)):
                    total += val
            result["score"] = {"type": "GENERIC_SUM", "value": total}

        return result

    def _infer_mode(self, scoring: Dict, realized_data: Dict) -> str:
        # Accept explicit hint in realized.unit or scoring
        # Fallback to amrap_reps
        if isinstance(scoring, dict):
            wod_rule = scoring.get("wod") or scoring.get("WOD")
            if isinstance(wod_rule, str):
                s = wod_rule.lower()
                if "amrap" in s:
                    return "amrap_reps"
                if "time" in s:
                    return "for_time"
                if "load" in s:
                    return "max_load"
        return realized_data.get("scoring", "amrap_reps")

    def _filter_relay(self, events: List[Dict], policy: Dict) -> List[Dict]:
        if not isinstance(policy, dict) or policy.get("partition") != "relay":
            return events
        order = policy.get("relay_order") or []
        if not order:
            return events
        idx = 0
        filtered = []
        for ev in events:
            ath = ev.get("athlete")
            # Only support single-athlete events for strict relay; multi-athlete pass through
            if isinstance(ath, str):
                if ath == order[idx % len(order)]:
                    filtered.append(ev)
                    idx += 1
            else:
                filtered.append(ev)
        return filtered

# Module Resolution
class ModuleRef:
    def __init__(self, namespace: str, name: str, version: Optional[str] = None):
        self.namespace = namespace
        self.name = name
        self.version = version or "v1"

    @property
    def full_name(self) -> str:
        return f"{self.namespace}.{self.name}@{self.version}"

class ResolvedModule:
    def __init__(self, source: str, ast: Optional[Dict] = None, meta: Optional[Dict] = None):
        self.source = source
        self.ast = ast
        self.meta = meta or {}

class ModuleResolver:
    """Abstract module resolver interface"""

    def resolve(self, ref: ModuleRef) -> ResolvedModule:
        """Resolve a module reference to its AST and metadata"""
        raise NotImplementedError("Subclasses must implement resolve method")

    def list(self, namespace: Optional[str] = None) -> List[ModuleRef]:
        """List all available modules, optionally filtered by namespace"""
        raise NotImplementedError("Subclasses must implement list method")

class InMemoryResolver(ModuleResolver):
    """In-memory module registry for testing"""

    def __init__(self):
        self.registry: Dict[str, str] = {}

    def register(self, ref: ModuleRef, source: str):
        self.registry[ref.full_name] = source

    def resolve(self, ref: ModuleRef) -> ResolvedModule:
        key = ref.full_name
        source = self.registry.get(key)
        if not source:
            raise ValueError(f"Module not found: {key}")
        return ResolvedModule(source)

    def list(self, namespace: Optional[str] = None) -> List[ModuleRef]:
        refs = []
        for key in self.registry.keys():
            ns_name, version = key.split("@")
            ns, name = ns_name.split(".", 1)
            if not namespace or ns == namespace:
                refs.append(ModuleRef(ns, name, version))
        return refs

class FileSystemResolver(ModuleResolver):
    """File-based module resolver with intelligent caching"""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self._cache: Dict[str, Tuple[float, ResolvedModule]] = {}  # key -> (mtime, module)

    def resolve(self, ref: ModuleRef) -> ResolvedModule:
        # Convert namespace.name to file path: namespace/name.(wod|wodcraft)
        name_path = ref.name.replace('.', '/')
        candidates = [
            self.base_path / ref.namespace / f"{name_path}.wod",
            self.base_path / ref.namespace / f"{name_path}.wodcraft",
        ]
        file_path = None
        for c in candidates:
            if c.exists():
                file_path = c
                break
        if not file_path:
            raise ValueError(f"Module file not found: {candidates[0]}")

        # Check cache with mtime validation
        cache_key = str(file_path)
        file_mtime = file_path.stat().st_mtime

        if cache_key in self._cache:
            cached_mtime, cached_module = self._cache[cache_key]
            if cached_mtime >= file_mtime:
                return cached_module

        # Read and cache
        with open(file_path, 'r') as f:
            source = f.read()

        resolved = ResolvedModule(source)
        self._cache[cache_key] = (file_mtime, resolved)
        return resolved

    def list(self, namespace: Optional[str] = None) -> List[ModuleRef]:
        refs = []
        search_path = self.base_path / namespace if namespace else self.base_path
        for pattern in ("*.wod", "*.wodcraft"):
            for file_path in search_path.rglob(pattern):
                relative = file_path.relative_to(self.base_path)
                parts = relative.with_suffix('').parts
                if len(parts) >= 2:
                    ns = parts[0]
                    name = ".".join(parts[1:])
                    # Extract version from file content if present, fallback to v1
                    version = self._extract_version_from_file(file_path)
                    refs.append(ModuleRef(ns, name, version))
        return refs

    def _extract_version_from_file(self, file_path: Path) -> str:
        """Extract version from module declaration in file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            # Look for module declarations like "module wod.name v2 {"
            import re
            match = re.search(r'module\s+[\w.]+\s+v(\d+)\s*\{', content)
            if match:
                return f"v{match.group(1)}"
        except Exception:
            pass
        return "v1"  # fallback

# Session Compiler with semantic validation
class SessionCompiler:
    """Compiles sessions by resolving imports and applying overrides with semantic validation"""

    def __init__(self, resolver: ModuleResolver, cache_size: int = 100):
        self.resolver = resolver
        # Use a base parser without transformer; we'll transform explicitly
        self._base_parser = Lark(GRAMMAR_VNEXT, parser='lalr')
        # LRU cache with size limit and performance metrics
        self._compiled_cache: OrderedDict[str, Tuple[float, Dict]] = OrderedDict()
        self._cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0

    def compile_session(self, session_ast: Dict) -> Dict:
        """Compile a session AST to executable JSON with caching"""
        # Create cache key from session AST
        session_hash = str(hash(json.dumps(session_ast, sort_keys=True)))
        current_time = time.time()

        # Check cache (valid for 300 seconds = 5 minutes)
        if session_hash in self._compiled_cache:
            cache_time, cached_result = self._compiled_cache[session_hash]
            if current_time - cache_time < 300:
                # Move to end (LRU behavior)
                self._compiled_cache.move_to_end(session_hash)
                self._cache_hits += 1
                return cached_result
            else:
                # Expired entry, remove it
                del self._compiled_cache[session_hash]

        self._cache_misses += 1

        result = {
            "session": {
                "title": session_ast.get("title", "Untitled"),
                "components": {},
                "scoring": session_ast["scoring"] if session_ast.get("scoring") else {},
                "meta": session_ast["meta"] if session_ast.get("meta") else {},
                "exports": session_ast["exports"] if session_ast.get("exports") else {},
                # PRD3 optional blocks
                "team": session_ast.get("team", {}),
                "realized": session_ast.get("realized", {}),
                "achievements": session_ast.get("achievements", {}),
            }
        }

        if not session_ast.get("components"):
            self._compiled_cache[session_hash] = (current_time, result)
            return result

        components = session_ast["components"]

        # Resolve each component
        for comp_type in ["warmup", "skill", "strength", "wod"]:
            if comp_type in components:
                import_info = components[comp_type]
                module_ast = self._resolve_and_parse_module(import_info)

                # Extract overrides if present
                override_params = None
                if isinstance(import_info.get("override"), dict):
                    override_params = import_info["override"].get("assignments", {})

                compiled_component = self._compile_component(module_ast, comp_type, override_params)
                result["session"]["components"][comp_type] = compiled_component

                # Semantic validation for WOD components
                if comp_type == "wod" and compiled_component.get("component"):
                    self._validate_wod_semantics(compiled_component["component"])

        # Aggregate realized team results if present
        try:
            agg = TeamRealizedAggregator()
            results = agg.aggregate(session_ast, result["session"])  # pass original AST and compiled session
            if results:
                result["session"]["results"] = results
        except Exception:
            # Be tolerant: do not break compilation if realized data is malformed
            pass

        # Cache result with LRU eviction
        self._compiled_cache[session_hash] = (current_time, result)

        # Evict oldest entries if cache is full
        while len(self._compiled_cache) > self._cache_size:
            self._compiled_cache.popitem(last=False)

        return result

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "total_entries": len(self._compiled_cache),
            "max_size": self._cache_size
        }

    def clear_cache(self):
        """Clear all cached data"""
        self._compiled_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def _expand_shorthand_macros(self, wod_ast: Dict) -> Dict:
        """Expand shorthand macros like '21-15-9 Thrusters + Pull_ups' into individual movement lines"""
        if not isinstance(wod_ast, dict):
            return wod_ast

        expanded_wod = wod_ast.copy()

        # Look for shorthand macros in movement lines
        if "movements" in expanded_wod:
            expanded_movements = []
            for movement in expanded_wod["movements"]:
                if isinstance(movement, dict) and movement.get("quantity", {}).get("type") == "SHORTHAND_MACRO":
                    # Expand the macro
                    macro = movement["quantity"]
                    reps_sequence = macro["reps_sequence"]
                    movements_list = macro["movements"]

                    # Create expanded movement lines
                    for reps in reps_sequence:
                        for mov_data in movements_list:
                            expanded_movement = {
                                "quantity": {"type": "reps", "value": reps},
                                "movement": mov_data["movement"]
                            }
                            if "load" in mov_data:
                                expanded_movement["load"] = mov_data["load"]
                            expanded_movements.append(expanded_movement)
                else:
                    expanded_movements.append(movement)

            expanded_wod["movements"] = expanded_movements

        return expanded_wod

    def _validate_wod_semantics(self, wod_component: Dict):
        """Validate WOD semantic consistency"""
        form = wod_component.get("form", {})
        movements = wod_component.get("movements", [])

        if not form or not movements:
            return

        # EMOM validation: check if movements can fit in time slots
        if self._is_emom(form):
            duration_seconds = self._extract_duration_seconds(form)
            if duration_seconds and duration_seconds >= 60:  # At least 1 minute
                estimated_movement_time = len(movements) * 10  # Rough estimate: 10s per movement
                slot_time = 60  # 1 minute slots for EMOM

                if estimated_movement_time > slot_time * 0.8:  # Use 80% of slot time as threshold
                    print(f"WARNING: EMOM might be too packed - {len(movements)} movements in {slot_time}s slots")

        # Time cap validation
        time_cap = self._extract_time_cap(form)
        if time_cap:
            if time_cap < 60:  # Less than 1 minute
                print(f"WARNING: Very short time cap ({time_cap}s) - might be unrealistic")
            elif time_cap > 3600:  # More than 1 hour
                print(f"WARNING: Very long time cap ({time_cap}s) - might be unrealistic")

        # Movement and load validation
        for movement in movements:
            if movement.get("type") == "REST":
                rest_seconds = movement.get("seconds", 0)
                if rest_seconds <= 0:
                    raise WODCraftError("REST duration must be positive",
                                       suggestion="Use format like 'REST 2:00' or 'REST 120s'")
            elif movement.get("type") == "MOVEMENT_LINE":
                self._validate_movement_semantics(movement)

        # Overall WOD structure validation
        self._validate_wod_structure(form, movements)

    def _is_emom(self, form: Dict) -> bool:
        """Check if WOD form is EMOM"""
        if isinstance(form, dict):
            form_type = form.get("type") or form.get("children", [])
            if isinstance(form_type, list) and form_type:
                return str(form_type[0]).upper() == "EMOM"
            return str(form_type).upper() == "EMOM"
        return False

    def _extract_duration_seconds(self, form: Dict) -> Optional[int]:
        """Extract duration in seconds from WOD form"""
        if not isinstance(form, dict):
            return None

        children = form.get("children", [])
        for child in children:
            if isinstance(child, dict) and child.get("kind") == "duration":
                return child.get("seconds")
            elif isinstance(child, str) and ":" in child:
                return _parse_mmss(child)
        return None

    def _extract_time_cap(self, form: Dict) -> Optional[int]:
        """Extract time cap in seconds from WOD form"""
        if not isinstance(form, dict):
            return None

        # Look for "cap" keyword followed by duration
        children = form.get("children", [])
        for i, child in enumerate(children):
            if isinstance(child, str) and child.lower() == "cap":
                if i + 1 < len(children):
                    cap_duration = children[i + 1]
                    if isinstance(cap_duration, str) and ":" in cap_duration:
                        return _parse_mmss(cap_duration)
        return None

    def _validate_movement_semantics(self, movement: Dict):
        """Validate individual movement semantics"""
        movement_name = movement.get("movement", "")
        quantity = movement.get("quantity", {})
        load = movement.get("load", {})

        # Validate dangerous loads for specific movements
        if load and isinstance(load, dict):
            load_value = self._extract_load_value(load)
            if load_value and movement_name:
                self._check_dangerous_loads(movement_name, load_value)

        # Validate high rep dangerous movements
        if quantity and isinstance(quantity, dict):
            reps = quantity.get("value")
            if reps and isinstance(reps, (int, float)) and movement_name:
                self._check_high_rep_warnings(movement_name, reps)

    def _extract_load_value(self, load: Dict) -> Optional[float]:
        """Extract numeric load value in kg for comparison"""
        if load.get("type") == "LOAD_VALUE":
            value = load.get("value")
            unit = load.get("unit", "")
            if isinstance(value, (int, float)):
                # Convert to kg for standardized comparison
                if unit == "lb":
                    return value * 0.453592
                elif unit == "kg":
                    return value
        elif load.get("type") == "LOAD_DUAL" and load.get("per_gender"):
            # Use male load as reference (typically higher)
            male_load = load["per_gender"].get("male", {})
            return self._extract_load_value(male_load)
        return None

    def _check_dangerous_loads(self, movement: str, load_kg: float):
        """Check for potentially dangerous loads"""
        movement_lower = movement.lower()

        # Deadlift warnings
        if "deadlift" in movement_lower:
            if load_kg > 180:  # > 180kg deadlift
                print(f"WARNING: Very heavy deadlifts ({load_kg:.1f}kg) - verify safety progression and form")
            elif load_kg > 140:  # > 140kg deadlift
                print(f"INFO: Heavy deadlifts ({load_kg:.1f}kg) - ensure proper warmup and spotting")

        # Overhead movement warnings
        elif any(term in movement_lower for term in ["press", "jerk", "snatch", "overhead"]):
            if load_kg > 80:  # > 80kg overhead
                print(f"WARNING: Heavy overhead movement ({load_kg:.1f}kg) - check shoulder mobility and technique")

        # Squat warnings
        elif "squat" in movement_lower:
            if load_kg > 150:  # > 150kg squat
                print(f"WARNING: Very heavy squats ({load_kg:.1f}kg) - ensure proper depth and safety bars")

    def _check_high_rep_warnings(self, movement: str, reps: float):
        """Check for potentially dangerous high rep combinations"""
        movement_lower = movement.lower()

        if "deadlift" in movement_lower and reps > 20:
            print(f"WARNING: High rep deadlifts ({int(reps)} reps) - high injury risk, consider scaling")

        if "burpee" in movement_lower and reps > 50:
            print(f"INFO: High rep burpees ({int(reps)} reps) - expect significant fatigue")

        if any(term in movement_lower for term in ["thruster", "clean"]) and reps > 30:
            print(f"INFO: High rep {movement} ({int(reps)} reps) - monitor form degradation")

    def _validate_wod_structure(self, form: Dict, movements: List[Dict]):
        """Validate overall WOD structure"""
        # Check for movement variety
        movement_names = [m.get("movement", "") for m in movements if m.get("type") == "MOVEMENT_LINE"]

        if len(set(movement_names)) == 1 and len(movement_names) > 1:
            print("INFO: Single movement WOD - consider pacing and scaling options")

        # Check for balance between modalities
        cardio_count = sum(1 for name in movement_names if any(term in name.lower()
                          for term in ["run", "row", "bike", "ski"]))
        strength_count = sum(1 for name in movement_names if any(term in name.lower()
                            for term in ["deadlift", "squat", "press", "clean", "snatch"]))

        if len(movements) > 2:
            if cardio_count == 0:
                print("INFO: No cardio movements - WOD focuses on strength/gymnastics")
            elif strength_count == 0:
                print("INFO: No strength movements - WOD focuses on cardio/gymnastics")

    def _resolve_and_parse_module(self, import_info: Dict) -> Dict:
        """Resolve and parse a module import"""
        ref_parts = import_info["ref_id"].split(".")
        ref = ModuleRef(ref_parts[0], ".".join(ref_parts[1:]), import_info.get("version", "v1"))

        resolved = self.resolver.resolve(ref)
        tree = self._base_parser.parse(resolved.source)
        return ToASTvNext().transform(tree)

    def _apply_overrides(self, module_ast: Dict, overrides: Dict) -> Dict:
        """(Reserved) Apply parameter overrides to module AST.
        Currently not mutating AST; overrides are surfaced in compiled output."""
        return module_ast

    def _compile_component(self, module_ast: Dict, comp_type: str, params: Optional[Dict] = None) -> Dict:
        """Compile a single component from module AST"""
        if "modules" in module_ast and module_ast["modules"]:
            module = module_ast["modules"][0]

            # Find the component in the module body
            for item in module.get("body", []):
                if isinstance(item, dict) and item.get("type", "").lower() == comp_type.upper():
                    # Expand shorthand macros for WOD components
                    if comp_type.upper() == "WOD":
                        item = self._expand_shorthand_macros(item)

                    compiled = {
                        "id": f"{module['id']}@{module['version']}",
                        "component": item
                    }
                    if params:
                        compiled["params"] = params
                    return compiled

        return {}

    def export_json(self, compiled_session: Dict) -> str:
        """Export compiled session as JSON"""
        return json.dumps(compiled_session, indent=2)

    def export_ics(self, compiled_session: Dict) -> str:
        """Export compiled session as ICS calendar"""
        session = compiled_session["session"]
        exports = session.get("exports", {})

        if "ics" not in exports:
            raise ValueError("ICS export configuration not found")

        ics_config = exports["ics"]

        # Generate ICS content
        ics_content = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//WODCraft//Session//FR",
            "BEGIN:VEVENT",
            f"UID:session-{session['title'].lower().replace(' ', '-')}@wodcraft",
            f"DTSTAMP:{self._generate_timestamp()}",
            f"DTSTART:{ics_config['start'].replace('-', '').replace(':', '').replace('+', 'Z')}",
            f"DURATION:PT{ics_config['duration']}",
            f"SUMMARY:CrossFit – {session['title']}",
            f"LOCATION:{ics_config.get('location', 'Box')}",
            f"DESCRIPTION:{self._generate_description(session)}",
            "END:VEVENT",
            "END:VCALENDAR"
        ]

        return "\n".join(ics_content)

    def _generate_timestamp(self) -> str:
        """Generate current timestamp in ICS format (YYYYMMDDTHHMMSSZ)"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

    def _generate_description(self, session: Dict) -> str:
        """Generate event description from session components"""
        parts = []

        components = session.get("components", {})
        if "warmup" in components:
            warmup = components["warmup"].get("component", {})
            parts.append(f"Warmup: {warmup.get('title', 'N/A')}")

        if "skill" in components:
            skill = components["skill"].get("component", {})
            parts.append(f"Skill: {skill.get('title', 'N/A')}")

        if "wod" in components:
            wod = components["wod"].get("component", {})
            movements = [self._format_movement(mov) for mov in wod.get("movements", [])]
            form_text = self._flatten_node(wod.get("form")) or "WOD"
            movement_preview = ", ".join(movements[:3]) if movements else ""
            wod_desc = form_text if not movement_preview else f"{form_text} ({movement_preview})"
            parts.append(f"WOD: {wod_desc}")

        return "; ".join(parts)

    def _flatten_node(self, node: Any) -> str:
        if node is None:
            return ""
        if isinstance(node, (int, float)):
            return str(node)
        if isinstance(node, str):
            return node.strip('"')
        if isinstance(node, dict):
            if node.get("raw") is not None:
                return str(node["raw"])
            return " ".join(filter(None, (self._flatten_node(child) for child in node.get("children", []))))
        if isinstance(node, list):
            return " ".join(filter(None, (self._flatten_node(child) for child in node)))
        return str(node)

    def _describe_load(self, load: Any) -> str:
        if load is None:
            return ""
        if isinstance(load, dict):
            if load.get("raw"):
                return str(load["raw"])
            if load.get("type") == "LOAD_DUAL":
                male = self._describe_load(load.get("per_gender", {}).get("male"))
                female = self._describe_load(load.get("per_gender", {}).get("female"))
                return f"{male}/{female}".strip('/')
            if load.get("type") == "LOAD_VARIANT":
                variants = load.get("variants", {})
                formatted = [f"{k}:{self._describe_load(v)}" for k, v in variants.items() if v]
                label = load.get("label")
                if formatted and label:
                    return f"{label}({', '.join(formatted)})"
                if formatted:
                    return ", ".join(formatted)
                return label or ''
            if load.get("type") == "LOAD_VALUE":
                value = load.get("value")
                unit = load.get("unit") or ""
                return f"{value:g}{unit}" if value is not None else unit
        if isinstance(load, (int, float)):
            return str(load)
        if isinstance(load, str):
            return load
        return ""

    def _format_movement(self, mov: Dict[str, Any]) -> str:
        quantity = mov.get("quantity", {})
        qty_raw = quantity.get("raw") if isinstance(quantity, dict) else self._flatten_node(quantity)
        name = mov.get("movement")
        if isinstance(name, dict):
            name = name.get("name") or self._flatten_node(name)
        load_text = self._describe_load(mov.get("load"))
        progress = mov.get("progression", {}).get("raw") if isinstance(mov.get("progression"), dict) else None
        parts = [str(qty_raw).strip(), str(name or "").strip()]
        label = " ".join(filter(None, parts)).strip()
        if load_text:
            label = f"{label} @{load_text}" if label else f"@{load_text}"
        if progress:
            label = f"{label} (progress {progress})" if label else f"progress {progress}"
        return label or "Movement"

# AST Transformer for extended language with enhanced error context
class ToASTvNext(Transformer):
    """
    Enhanced AST transformer with better error handling and line/column tracking.

    This transformer converts Lark parse trees into structured JSON ASTs while
    preserving source location information for better error reporting.
    """

    def __init__(self):
        super().__init__()
        self.resolver = InMemoryResolver()
        self._source_lines: List[str] = []

    def set_source(self, source: str):
        """Set source text for enhanced error reporting"""
        self._source_lines = source.split('\n')

    def _get_source_context(self, line: int) -> str:
        """Get source line for error context"""
        if 0 <= line - 1 < len(self._source_lines):
            return self._source_lines[line - 1]
        return ""

    # ---- Helpers -----------------------------------------------------
    def _flatten(self, value: Any) -> str:
        """
        Flatten complex nested structures to strings.

        Handles various node types including dicts with 'raw' fields,
        lists, and nested structures while preserving meaningful content.
        """
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value.strip('"')
        if isinstance(value, dict):
            if value.get("raw") is not None:
                return str(value.get("raw"))
            children = value.get("children", [])
            return " ".join(filter(None, (self._flatten(child) for child in children)))
        if isinstance(value, (list, tuple)):
            return " ".join(filter(None, (self._flatten(child) for child in value)))
        return str(value)

    def _parse_numeric(self, value: Any) -> Optional[float]:
        """Parse numeric values with error handling"""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    def _parse_distance(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse distance values (e.g., '400m', '1.5km')"""
        match = DISTANCE_RE.match(text)
        if not match:
            return None
        value = self._parse_numeric(match.group("value"))
        unit = match.group("unit")
        return {
            "kind": "distance",
            "value": value,
            "unit": unit,
            "raw": text,
        }

    def _quantity_to_dict(self, node: Any) -> Dict[str, Any]:
        """
        Convert quantity nodes to structured dictionaries.

        Handles various quantity types:
        - Reps (numeric values)
        - Duration (time formats like '12:00')
        - Calories (with dual gender support)
        - Distances
        - MAXREP keyword
        """
        if node is None:
            return {}
        if isinstance(node, dict):
            node_type = node.get("type")
            children = node.get("children", [])
            if node_type == "REPS_SPEC" and children:
                return self._quantity_to_dict(children[0])
            if node_type == "DURATION" and len(children) == 2 and all(isinstance(c, int) for c in children):
                minutes, seconds = children
                raw = f"{minutes:02d}:{seconds:02d}"
                return {"kind": "duration", "seconds": minutes * 60 + seconds, "raw": raw}
            if node_type == "MOVEMENT_NAME":
                return {"kind": "raw", "raw": self._flatten(node)}
            if node_type == "PROGRESSION":
                return {"kind": "progression", "raw": self._flatten(node)}
            if node_type == "MOVEMENT_LINE":
                return {"kind": "raw", "raw": self._flatten(node)}
            return {"kind": "raw", "raw": self._flatten(node)}
        if isinstance(node, str):
            text = node.strip('"')
            if text.lower() == "maxrep":
                return {"kind": "maxrep", "raw": "MAXREP"}
            dual_cal = CAL_DUAL_RE.match(text)
            if dual_cal:
                male_val = self._parse_numeric(dual_cal.group("male"))
                female_val = self._parse_numeric(dual_cal.group("female"))
                return {
                    "kind": "calories",
                    "per_gender": {
                        "male": {"value": male_val, "raw": f"{dual_cal.group('male')} cal"},
                        "female": {"value": female_val, "raw": f"{dual_cal.group('female')} cal"},
                    },
                    "raw": text,
                }
            single_cal = CAL_SINGLE_RE.match(text)
            if single_cal:
                value = self._parse_numeric(single_cal.group("value"))
                return {"kind": "calories", "value": value, "raw": text}
            distance = self._parse_distance(text)
            if distance:
                return distance
            numeric = self._parse_numeric(text)
            if numeric is not None:
                return {"kind": "reps", "value": numeric, "raw": text}
            return {"kind": "raw", "raw": text}
        if isinstance(node, (int, float)):
            return {"kind": "reps", "value": float(node), "raw": str(node)}
        return {"kind": "raw", "raw": self._flatten(node)}

    def _movement_name(self, node: Any) -> str:
        """Extract movement name, converting to snake_case format"""
        if isinstance(node, dict) and node.get("type") == "MOVEMENT_NAME":
            return "_".join(str(part) for part in node.get("children", []) if part is not None)
        return self._flatten(node)

    def _coerce_load(self, value: Any) -> Optional[Dict[str, Any]]:
        """Convert various load representations to structured format"""
        if value is None:
            return None
        if isinstance(value, dict) and value.get("type") in {"LOAD_VALUE", "LOAD_DUAL", "LOAD_VARIANT", "LOAD_LITERAL"}:
            return value
        if isinstance(value, (int, float)):
            return {"type": "LOAD_VALUE", "value": float(value), "unit": None, "raw": str(value)}
        if isinstance(value, str):
            text = value.strip('"')
            return {"type": "LOAD_LITERAL", "raw": text}
        return None

    def _merge_gender_map(self, variants: Dict[str, Any]) -> Dict[str, Any]:
        """Merge gender-specific variants using alias mapping"""
        mapped: Dict[str, Any] = {}
        for key, value in variants.items():
            alias = GENDER_ALIAS_MAP.get(str(key).lower())
            if alias:
                mapped[alias] = self._coerce_load(value)
        return mapped

    def _load_to_text(self, load: Any) -> str:
        """Convert load structure back to text representation"""
        if load is None:
            return ""
        if isinstance(load, dict):
            if load.get("raw") is not None:
                return str(load["raw"])
            if load.get("type") == "LOAD_VALUE":
                value = load.get("value")
                unit = load.get("unit") or ""
                return f"{value:g}{unit}" if value is not None else unit
            if load.get("type") == "LOAD_DUAL":
                male = self._load_to_text(load.get("male") or load.get("per_gender", {}).get("male"))
                female = self._load_to_text(load.get("female") or load.get("per_gender", {}).get("female"))
                if male or female:
                    return f"{male}/{female}".strip('/')
            if load.get("type") == "LOAD_VARIANT":
                variants = load.get("variants", {})
                formatted = [f"{k}:{self._load_to_text(v)}" for k, v in variants.items() if v]
                label = load.get("label")
                if formatted and label:
                    return f"{label}({', '.join(formatted)})"
                if formatted:
                    return ", ".join(formatted)
                return label or ''
        if isinstance(load, (int, float)):
            return str(load)
        if isinstance(load, str):
            return load.strip('"')
        return ""

    # ---- Transformer Methods ----------------------------------------

    def progress_clause(self, items):
        """Parse progression clauses like PROGRESS("+15m/round")"""
        text = self._flatten(items[0]) if items else ""
        match = PROGRESS_RE.match(text.strip())
        if match:
            sign = -1 if match.group("sign") == '-' else 1
            value = self._parse_numeric(match.group("value"))
            unit = match.group("unit") or None
            cadence = match.group("cadence")
            increment_value = value * sign if value is not None else None
            increment_raw = f"{match.group('sign')}{match.group('value')}{unit or ''}"
            increment = {
                "value": increment_value,
                "unit": unit,
                "raw": increment_raw if increment_raw else text,
            }
        else:
            increment = {"raw": text}
            cadence = None
        return {
            "type": "PROGRESSION",
            "increment": increment,
            "cadence": cadence,
            "raw": text,
        }

    def load_value(self, items):
        """Parse load values like '43kg', '95lb'"""
        number = self._parse_numeric(items[0]) if items else None
        unit = str(items[1]) if len(items) > 1 else None
        raw = f"{items[0]}{items[1]}" if len(items) > 1 else str(items[0])
        return {
            "type": "LOAD_VALUE",
            "value": number,
            "unit": unit,
            "raw": raw,
        }

    def load_dual(self, items):
        """Parse dual loads like '43kg/30kg' for male/female"""
        male = self._coerce_load(items[0])
        female = self._coerce_load(items[1] if len(items) > 1 else None)
        return {
            "type": "LOAD_DUAL",
            "per_gender": {"male": male, "female": female},
            "raw": f"{self._load_to_text(male)}/{self._load_to_text(female)}",
        }

    def load_variant_entry(self, items):
        """Parse load variant entries like 'M:24kg'"""
        key = str(items[0])
        value = items[1] if len(items) > 1 else None
        return {"key": key, "value": value}

    def shorthand_macro(self, items):
        """Parse shorthand macros like '21-15-9 Thrusters + Pull_ups'"""
        pattern = str(items[0])  # e.g., "21-15-9"
        movements_with_loads = items[1]

        # Parse the pattern into a list of numbers
        reps_sequence = [int(x) for x in pattern.split('-')]

        return {
            "type": "SHORTHAND_MACRO",
            "pattern": pattern,
            "reps_sequence": reps_sequence,
            "movements": movements_with_loads,
            "raw": f"{pattern} {self._flatten(movements_with_loads)}"
        }

    def movement_list_with_loads(self, items):
        """Parse movement list with optional loads like 'Thrusters @95lb + Pull_ups'"""
        movements = []
        i = 0
        while i < len(items):
            if hasattr(items[i], 'data') and items[i].data == 'movement':
                movement = {"movement": str(items[i])}
                # Check if next item is a load
                if i + 1 < len(items) and hasattr(items[i + 1], 'type') and items[i + 1].type == 'LOAD_VALUE':
                    movement["load"] = items[i + 1]
                    i += 2
                else:
                    i += 1
                movements.append(movement)
            else:
                i += 1
        return movements

    def load_variant_amount(self, items):
        """Parse load variant amounts"""
        if not items:
            return None
        return self._coerce_load(items[0])

    def load_variant(self, items):
        """Parse load variants like 'RX(M:24kg,F:16kg)'"""
        label = str(items[0]) if items else ""
        variants: Dict[str, Any] = {}
        for entry in items[1:]:
            if isinstance(entry, dict) and "key" in entry:
                variants[entry["key"]] = self._coerce_load(entry.get("value"))
        per_gender = self._merge_gender_map(variants)
        formatted = [f"{k}:{self._load_to_text(v)}" for k, v in variants.items() if v]
        return {
            "type": "LOAD_VARIANT",
            "label": label,
            "variants": variants,
            "per_gender": per_gender,
            "raw": f"{label}({', '.join(formatted)})" if formatted else label,
        }

    def load_spec(self, items):
        """Parse load specifications"""
        if not items:
            return None
        load_data = self._coerce_load(items[0])
        return {
            "type": "LOAD_SPEC",
            "load": load_data,
            "raw": self._load_to_text(load_data),
        }

    def movement_name(self, items):
        """Parse movement names to snake_case format"""
        return {"type": "MOVEMENT_NAME", "name": "_".join(str(part) for part in items if part is not None), "children": list(items)}

    def movement_line(self, items):
        """
        Parse complete movement lines with all components.

        Handles quantity, movement name, progression, load, tempo, and notes.
        """
        quantity_token = items[0] if items else None
        movement_token = items[1] if len(items) > 1 else None
        idx = 2
        progress = None
        if idx < len(items) and isinstance(items[idx], dict) and items[idx].get("type") == "PROGRESSION":
            progress = items[idx]
            idx += 1
        load_token = items[idx] if idx < len(items) else None
        idx += 1
        tempo_token = items[idx] if idx < len(items) else None
        idx += 1
        note_token = items[idx] if idx < len(items) else None

        load_info = None
        if isinstance(load_token, dict) and load_token.get("type") == "LOAD_SPEC":
            load_info = load_token.get("load")
        else:
            load_info = self._coerce_load(load_token)

        node: Dict[str, Any] = {
            "type": "MOVEMENT_LINE",
            "children": items,
            "movement": self._movement_name(movement_token),
            "quantity": self._quantity_to_dict(quantity_token),
        }
        if progress:
            node["progression"] = progress
        if load_info:
            node["load"] = load_info
        if tempo_token:
            node["tempo"] = self._flatten(tempo_token)
        if note_token:
            node["note"] = self._flatten(note_token)
        return node

    def program(self, items):
        """Parse top-level program structure"""
        # Fast-path: already structured
        if len(items) == 1 and isinstance(items[0], dict) and ("modules" in items[0] or "sessions" in items[0]):
            return items[0]

        modules = []
        sessions = []
        programming = []
        for item in items:
            if item:
                if isinstance(item, dict):
                    if item.get("type") == "MODULE":
                        modules.append(item)
                    elif item.get("type") == "SESSION":
                        sessions.append(item)
                    elif item.get("type") == "PROGRAMMING":
                        programming.append(item)
                else:
                    # Handle other types that might not be dicts yet
                    sessions.append(item)
        result = {"modules": modules, "sessions": sessions}
        if programming:
            result["programming"] = programming
        return result

    def module(self, items):
        """Parse module declarations"""
        qualified_id = items[0]
        version = items[1] if len(items) > 1 and isinstance(items[1], dict) and "version" in items[1] else {"version": "v1"}
        body = items[2] if len(items) > 2 else []

        return {
            "type": "MODULE",
            "id": qualified_id,
            "version": version["version"],
            "body": body
        }

    def qualified_id(self, items):
        """Parse qualified identifiers like 'wod.strength.squat'"""
        return ".".join([str(token) for token in items])

    def version(self, items):
        """Parse version specifications like 'v1' or 'v1.2'"""
        if len(items) == 1:
            return {"version": f"v{items[0]}"}
        else:
            return {"version": f"v{items[0]}.{items[1]}"}

    def session(self, items):
        """Parse session declarations with all components"""
        title = str(items[0]).strip('"') if items else "Unnamed"
        components = None
        scoring = None
        meta = None
        exports = None
        team = None
        realized = None
        achievements = None

        for item in items[1:]:
            if isinstance(item, dict):
                if item.get("type") == "COMPONENTS":
                    components = item
                elif item.get("type") == "SCORING":
                    scoring = item
                elif item.get("type") == "META":
                    meta = item
                elif item.get("type") == "EXPORTS":
                    exports = item
                elif item.get("type") == "TEAM":
                    team = item
                elif item.get("type") == "REALIZED":
                    realized = item
                elif item.get("type") == "ACHIEVEMENTS":
                    achievements = item

        return {
            "type": "SESSION",
            "title": title,
            "components": components,
            "scoring": scoring,
            "meta": meta,
            "exports": exports,
            "team": team,
            "realized": realized,
            "achievements": achievements
        }

    def components(self, items):
        """Parse session components"""
        result = {"type": "COMPONENTS"}
        for item in items:
            if isinstance(item, dict):
                result.update(item)
        return result

    def warmup(self, items):
        """Parse warmup components"""
        title = items[0][1:-1] if isinstance(items[0], str) else str(items[0])
        blocks = items[1:] if len(items) > 1 else []
        return {
            "type": "WARMUP",
            "title": title,
            "blocks": blocks
        }

    def skill(self, items):
        """Parse skill components"""
        title = items[0][1:-1] if isinstance(items[0], str) else str(items[0])
        work = None
        cues = None
        for item in items[1:]:
            if isinstance(item, dict):
                if item.get("type") == "WORK":
                    work = item
                elif item.get("type") == "CUES":
                    cues = item
        return {
            "type": "SKILL",
            "title": title,
            "work": work,
            "cues": cues
        }

    # Module variable declarations
    def vars_decl(self, items):
        """Parse variable declarations in modules"""
        decls = [it for it in items if isinstance(it, dict) and it.get('kind') == 'VAR']
        return {"type": "VARS", "decls": decls}

    def var_decl(self, items):
        """Parse individual variable declarations"""
        # (name, type_spec, [default], [constraints])
        name = None
        ts = None
        default = None
        constraints = None
        # items can be mixed types/dicts
        if items:
            name = str(items[0])
        # type_spec can be dict tagged 'TYPE'
        for it in items[1:]:
            if isinstance(it, dict) and it.get('kind') == 'TYPE':
                ts = it
            elif isinstance(it, dict) and it.get('kind') == 'CONSTRAINTS':
                constraints = it.get('items')
            else:
                # default literal or value
                default = it
        return {"kind": "VAR", "name": name, "type": ts, "default": default, "constraints": constraints}

    def constraints(self, items):
        """Parse variable constraints"""
        cons = []
        for it in items:
            if isinstance(it, dict) and it.get('kind') == 'CONSTRAINT':
                cons.append(it)
        return {"kind": "CONSTRAINTS", "items": cons}

    def constraint(self, items):
        """Parse individual constraints like min=5, max=10"""
        # Forms: min=literal | max=literal | pattern=STRING | enum=array
        if len(items) >= 2:
            key = str(items[0])
            val = items[1]
            return {"kind": "CONSTRAINT", "key": key, "value": val}
        return {"kind": "CONSTRAINT"}

    def type_spec(self, items):
        """Parse type specifications with enhanced structure"""
        # Attempt to build structured type
        # Cases: 'Time','Rounds','Reps','Load(units)','Distance(units)','Calories','Tempo','Int','Float','Bool','String','Enum(array)'
        if not items:
            return {"kind": "TYPE", "name": "Unknown"}
        # items may be strings and/or lists
        head = str(items[0])
        if head in ("Time","Rounds","Reps","Calories","Tempo","Int","Float","Bool","String"):
            return {"kind": "TYPE", "name": head}
        if head == "Load" or head == "Distance":
            # units after
            units = []
            for it in items[1:]:
                if isinstance(it, list):
                    units.extend([str(x) for x in it])
                else:
                    units.append(str(it))
            return {"kind": "TYPE", "name": head, "units": units}
        if head == "Enum":
            choices = []
            for it in items[1:]:
                if isinstance(it, list):
                    choices.extend(it)
            return {"kind": "TYPE", "name": "Enum", "choices": choices}
        # Fallback join
        return {"kind": "TYPE", "name": " ".join(str(x) for x in items)}

    def work(self, items):
        """Parse work sections in skill/strength components"""
        return {"type": "WORK", "lines": items}

    def cues(self, items):
        """Parse coaching cues"""
        return {"type": "CUES", "items": [item[1:-1] for item in items if isinstance(item, str)]}

    def notes_decl(self, items):
        """Parse module-level notes"""
        value = items[0] if items else None
        return {"type": "NOTES", "scope": "module", "value": value}

    def wod_notes_decl(self, items):
        """Parse WOD-specific notes"""
        value = items[0] if items else None
        return {"type": "WOD_NOTES", "scope": "wod", "value": value}

    def wod_rest(self, items):
        """Parse REST declarations with enhanced validation"""
        token = items[0] if items else None
        duration = self._quantity_to_dict(token)
        seconds = None
        raw = None
        if isinstance(duration, dict):
            seconds = duration.get("seconds") or duration.get("value")
            raw = duration.get("raw")

        # Validate REST duration
        if seconds is not None and seconds <= 0:
            raise WODCraftError("REST duration must be positive",
                               suggestion="Use format like 'REST 2:00' or 'REST 120s'")

        return {
            "type": "REST",
            "duration": duration,
            "seconds": seconds,
            "raw": raw or self._flatten(token),
        }

    def wod(self, items):
        """Parse WOD components with notes integration"""
        form = items[0]
        movements = []
        notes: List[Any] = []
        for element in items[1:]:
            if isinstance(element, dict) and element.get("type") == "WOD_NOTES":
                value = element.get("value")
                if isinstance(value, list):
                    notes.extend(value)
                else:
                    notes.append(value)
            elif element is not None:
                movements.append(element)
        node: Dict[str, Any] = {
            "type": "WOD",
            "form": form,
            "movements": movements
        }
        if notes:
            node["notes"] = notes if len(notes) > 1 else notes[0]
        return node

    def wod_item(self, items):
        """Parse individual WOD items"""
        return items[0] if items else None

    def component_import(self, items):
        """Parse component imports in sessions"""
        key_candidate = str(items[0]) if items else "unknown"
        import_stmt = items[1] if len(items) > 1 else {}
        # If comp_key couldn't be resolved by the grammar (literal rule), infer from ref_id
        if key_candidate == "unknown" and isinstance(import_stmt, dict):
            ref = import_stmt.get("ref_id", "")
            inferred = ref.split(".")[0] if "." in ref else "unknown"
            comp_key = inferred
        else:
            comp_key = key_candidate
        return {comp_key: import_stmt}

    def import_stmt(self, items):
        """Parse import statements with version and overrides"""
        ref_id = str(items[0])
        version = None
        override = None

        for item in items[1:]:
            if isinstance(item, dict):
                if "version" in item:
                    version = item["version"]
                elif item.get("type") == "OVERRIDE":
                    override = item

        return {
            "type": "IMPORT",
            "ref_id": ref_id,
            "version": version,
            "override": override
        }

    def override_clause(self, items):
        """Parse override clauses for imports"""
        assignments = {}
        for item in items:
            if isinstance(item, dict) and "key" in item:
                assignments[item["key"]] = item["value"]
        return {
            "type": "OVERRIDE",
            "assignments": assignments
        }

    def assign(self, items):
        """Parse assignment statements in overrides"""
        key = str(items[0])
        value = items[1] if len(items) > 1 else None
        return {
            "key": key,
            "value": value
        }

    def scoring_rule(self, items):
        """Parse scoring rules for session components"""
        comp_key = str(items[0])
        policy = items[1] if len(items) > 1 else "none"
        return {comp_key: policy}

    def score_policy(self, items):
        """Parse score policies"""
        if not items:
            return "none"
        return str(items[0])

    def session_meta(self, items):
        """Parse session metadata"""
        result = {"type": "META"}
        for item in items:
            if isinstance(item, dict) and "key" in item:
                result[item["key"]] = item["value"]
        return result

    def meta_entry(self, items):
        """Parse individual metadata entries"""
        key = str(items[0])
        value = items[1] if len(items) > 1 else None
        return {
            "key": key,
            "value": value
        }

    def exports(self, items):
        """Parse export specifications"""
        return {
            "type": "EXPORTS",
            "formats": [str(item) for item in items]
        }

    # PRD3 blocks: team/realized/achievements as generic objects
    def team_block(self, items):
        """Parse team configuration blocks"""
        return {"type": "TEAM", "data": items[0] if items else {}}

    def realized_block(self, items):
        """Parse realized results blocks"""
        return {"type": "REALIZED", "data": items[0] if items else {}}

    def achievements_block(self, items):
        """Parse achievements blocks"""
        return {"type": "ACHIEVEMENTS", "data": items[0] if items else {}}

    def programming_block(self, items):
        """Parse programming blocks for coach planning"""
        return {"type": "PROGRAMMING", "data": items[0] if items else {}}

    def literal(self, items):
        """Parse literal values"""
        if not items:
            return None
        item = items[0]
        if isinstance(item, str):
            return item.strip('"')
        return item

    def array(self, items):
        """Parse array literals"""
        return list(items)

    def value(self, items):
        """Parse generic values"""
        return items[0] if items else None

    def object(self, items):
        """Parse object literals"""
        result = {}
        for kv in items:
            if isinstance(kv, dict) and "key" in kv:
                result[kv["key"]] = kv["value"]
        return result

    def key_value(self, items):
        """Parse key-value pairs in objects"""
        key = str(items[0])
        val = items[1] if len(items) > 1 else None
        return {"key": key, "value": val}

    def start(self, items):
        """Parse start node (top-level)"""
        return self.program(items)

    def ref_id(self, items):
        """Parse reference IDs"""
        return items[0] if items else ""

    def comp_key(self, items):
        """Parse component keys"""
        return str(items[0]) if items else "unknown"

    # Handle remaining terminal conversions
    def __default_token__(self, token):
        """Handle default token conversion with type preservation"""
        if token.type in ['STRING', 'IDENT']:
            return str(token.value)
        elif token.type in ['INT', 'NUMBER']:
            try:
                return int(token.value)
            except ValueError:
                return float(token.value)
        return str(token.value)

    def __default__(self, data, children, meta):
        """Handle default rule conversion to structured format"""
        # Convert any remaining Tree objects to dicts
        return {
            "type": data.upper() if isinstance(data, str) else str(data),
            "children": children
        }


def parse_vnext(text: str) -> Dict:
    """
    Parse WODCraft source with enhanced error reporting.

    Returns a structured AST dictionary with modules, sessions, and programming blocks.
    Provides detailed error messages with line/column information and suggestions.
    """
    parser = Lark(GRAMMAR_VNEXT, parser='lalr')
    try:
        tree = parser.parse(text)
        transformer = ToASTvNext()
        transformer.set_source(text)
        result = transformer.transform(tree)
        return result
    except (UnexpectedCharacters, UnexpectedToken) as e:
        # Enhanced error reporting with context
        line = getattr(e, 'line', None)
        column = getattr(e, 'column', None)

        source_lines = text.split('\n')
        source_line = source_lines[line - 1] if line and 0 <= line - 1 < len(source_lines) else ""

        # Generate suggestions based on common errors
        suggestion = None
        if hasattr(e, 'expected'):
            expected = e.expected
            if 'STRING' in expected:
                suggestion = "Expected a quoted string (use double quotes)"
            elif 'IDENT' in expected:
                suggestion = "Expected an identifier (e.g., Movement_Name)"
            elif any('"{"' in exp for exp in expected):
                suggestion = "Expected an opening brace '{'"
            elif 'LBRACE' in expected:
                suggestion = "Missing opening brace '{' after component declaration"
            elif 'RBRACE' in expected:
                suggestion = "Missing closing brace '}' to end block"
            elif 'INT' in expected:
                suggestion = "Expected a number (e.g., 10, 15, 20)"
            elif 'COLON' in expected:
                suggestion = "Missing colon ':' in declaration"
            elif 'IMPORT' in expected:
                suggestion = "Use 'import module.name@version' syntax"

        error_msg = f"Syntax error"
        if hasattr(e, 'token') and e.token:
            error_msg += f" at '{e.token}'"

        raise WODCraftError(error_msg, line, column, source_line, suggestion)
    except Exception as e:
        raise WODCraftError(f"Parse error: {e}")


# Enhanced Programming linter with detailed semantic checks
class ProgrammingLinter:
    """
    Enhanced programming linter with comprehensive validation rules.

    Validates coach programming blocks against CrossFit methodology standards
    including periodization, volume, intensity, and movement patterns.
    """

    def lint(self, programming: Dict, config: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Lint programming block with configurable validation rules.

        Returns list of issues with level (error/warning/info), code, and message.
        """
        issues: List[Dict[str, Any]] = []
        if not isinstance(programming, dict):
            return [{"level": "error", "code": "P000", "msg": "Invalid programming block"}]

        cfg = {
            "heavy_day_per_week_min": 1,
            "couplet_triplet_ratio_min": 0.6,
            "long_domain_min_per_2_weeks": 1,
            "mgw_balance_warning_threshold": 0.25,
            "max_consecutive_high_intensity": 3,
            "rest_day_ratio_min": 0.14,  # 1/7 = ~14%
        }
        if isinstance(config, dict):
            cfg.update(config)

        microcycles = programming.get("microcycles") or []
        if not isinstance(microcycles, list):
            return issues

        for mc in microcycles:
            week = mc.get("week")
            sessions = mc.get("sessions") or []
            if not sessions:
                continue

            # Heavy day validation
            heavy_count = sum(1 for s in sessions if (s.get("design", {}).get("workout") == "heavy_day"))
            if heavy_count < cfg["heavy_day_per_week_min"]:
                issues.append({"level": "warning", "code": "P101", "week": week,
                             "msg": f"Only {heavy_count} heavy day(s), recommend ≥{cfg['heavy_day_per_week_min']}"})

            # Couplet/triplet ratio validation
            ct = sum(1 for s in sessions if s.get("design", {}).get("workout") in ("couplet", "triplet"))
            non_rest = [s for s in sessions if not s.get("rest")]
            if non_rest:
                ratio = ct / len(non_rest)
                if ratio < cfg["couplet_triplet_ratio_min"]:
                    issues.append({"level": "warning", "code": "P102", "week": week,
                                 "msg": f"Couplet/Triplet ratio {ratio:.2f} < {cfg['couplet_triplet_ratio_min']}"})

            # Time domain distribution
            domain_counts = {"short": 0, "medium": 0, "long": 0}
            for s in sessions:
                dom = s.get("design", {}).get("domain")
                if dom in domain_counts:
                    domain_counts[dom] += 1

            if domain_counts["long"] == 0:
                issues.append({"level": "info", "code": "P103", "week": week,
                             "msg": "No long domain session this week - consider aerobic capacity work"})

            # Metabolic pathway balance (M/G/W)
            focuses = [s.get("focus") for s in sessions if s.get("focus") in ("M", "G", "W")]
            if focuses:
                from collections import Counter
                c = Counter(focuses)
                total = sum(c.values())
                for k, v in c.items():
                    frac = v / total
                    if frac < cfg["mgw_balance_warning_threshold"]:
                        pathway_name = {"M": "Phosphocreatine", "G": "Glycolytic", "W": "Oxidative"}[k]
                        issues.append({"level": "warning", "code": "P104", "week": week,
                                     "msg": f"Low {pathway_name} ({k}) focus: {frac:.1%} of workouts"})

            # Rest day validation
            rest_sessions = sum(1 for s in sessions if s.get("rest", False))
            rest_ratio = rest_sessions / len(sessions) if sessions else 0
            if rest_ratio < cfg["rest_day_ratio_min"]:
                issues.append({"level": "warning", "code": "P105", "week": week,
                             "msg": f"Low rest ratio {rest_ratio:.1%}, recommend ≥{cfg['rest_day_ratio_min']:.1%}"})

            # Consecutive high-intensity validation
            intensities = [s.get("design", {}).get("intensity") for s in sessions]
            consecutive_high = 0
            max_consecutive = 0
            for intensity in intensities:
                if intensity in ("high", "very_high"):
                    consecutive_high += 1
                    max_consecutive = max(max_consecutive, consecutive_high)
                else:
                    consecutive_high = 0

            if max_consecutive > cfg["max_consecutive_high_intensity"]:
                issues.append({"level": "warning", "code": "P106", "week": week,
                             "msg": f"Too many consecutive high-intensity days: {max_consecutive}"})

        return issues


def main():
    """CLI entry point for core functionality"""
    parser = argparse.ArgumentParser(description="WODCraft language core")
    parser.add_argument("command", choices=["parse", "compile", "validate", "session"])
    parser.add_argument("file", help="Input file")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("--modules-path", default="./modules", help="Path to modules directory")
    parser.add_argument("--format", choices=["json", "ics"], default="json", help="Output format for session compile")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    with open(args.file, 'r') as f:
        content = f.read()

    if args.command == "parse":
        try:
            ast = parse_vnext(content)
            output = json.dumps(ast, indent=2)

            if args.output:
                with open(args.output, 'w') as f:
                    f.write(output)
            else:
                print(output)
        except WODCraftError as e:
            print(f"Parse error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "validate":
        try:
            parse_vnext(content)
            print("✓ Valid WODCraft syntax")
        except WODCraftError as e:
            print(f"✗ Validation failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "session":
        try:
            # Parse the session file
            ast = parse_vnext(content)

            if not ast.get("sessions"):
                print("✗ No session found in file", file=sys.stderr)
                sys.exit(1)

            # Set up resolver and compiler
            resolver = FileSystemResolver(args.modules_path)
            compiler = SessionCompiler(resolver)

            # Compile the first session
            session_ast = ast["sessions"][0]
            compiled = compiler.compile_session(session_ast)

            if args.format == "json":
                output = compiler.export_json(compiled)
            elif args.format == "ics":
                output = compiler.export_ics(compiled)
            else:
                output = json.dumps(compiled, indent=2)

            if args.output:
                with open(args.output, 'w') as f:
                    f.write(output)
            else:
                print(output)

        except (WODCraftError, ValueError) as e:
            print(f"✗ Session compilation failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "compile":
        try:
            # Legacy compile command
            ast = parse_vnext(content)
            output = json.dumps(ast, indent=2)

            if args.output:
                with open(args.output, 'w') as f:
                    f.write(output)
            else:
                print(output)
        except WODCraftError as e:
            print(f"Compile error: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()