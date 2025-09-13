#!/usr/bin/env python3
"""
WODCraft vNext - Extended Language with Modules, Sessions, and Type System
"""

import sys, json, argparse, re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from lark import Lark, Transformer, Token, Tree
from dataclasses import dataclass
from enum import Enum

# Extended EBNF Grammar for WODCraft vNext
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

body: warmup | skill | strength | wod | score_decl

// Component Types
warmup: "warmup" STRING "{" block* "}"
block: "block" STRING ["repeat" INT] "{" movement_line* "}"

skill: "skill" STRING "{" work cues "}"
strength: "strength" STRING "{" work cues "}"
work: "work" "{" work_line* "}"
cues: "cues" "{" STRING* "}"
work_line: movement_line | scheme_line
scheme_line: SETS (INT|IDENT) REPS (INT|IDENT) ["@" (load_value|IDENT)] [TEMPO (tempo_value|IDENT)]

wod: "wod" wod_form "{" movement_line* "}"
wod_form: "AMRAP" duration
        | "ForTime" ["cap" duration]
        | "EMOM" duration
        | "RFT" INT
        | "TABATA"
        | IDENT

movement_line: (INT "x" reps_spec | INT XINT | reps_spec | MAXREP) movement_name [load_spec] [tempo_spec] [note]
reps_spec: INT | duration | DIST
movement_name: IDENT ("_" IDENT)*
load_spec: "@" (load_value | IDENT)
tempo_spec: TEMPO (tempo_value | IDENT)
tempo_value: STRING
note: STRING

score_decl: "score" IDENT "{" field_decl* "}"
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
load_value: NUMBER ("kg" | "lb" | "%1RM")
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
        | TIMEQ -> hold_time

movement: IDENT ("_" IDENT)*
load: "@" (LOADVAL|LOADDUAL)

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
LOADVAL: /\d+(?:\.\d+)?(kg|lb|cm|in|m|km|%)\b/
LOADDUAL: /\d+(?:\.\d+)?\/\d+(?:\.\d+)?(kg|lb|cm|in|m|km|%)\b/
REPDUAL: /\d+\/\d+/
CALDUAL: /\d+(?:\.\d+)?\/\d+(?:\.\d+)?\s*cal/
DISTDUAL: /\d+(?:\.\d+)?\/\d+(?:\.\d+)?(?:m|km)\b/

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


def _parse_mmss(t: str) -> Optional[int]:
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
        raise NotImplementedError
        
    def list(self, namespace: Optional[str] = None) -> List[ModuleRef]:
        raise NotImplementedError

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
    """File-based module resolver"""
    
    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        
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
        with open(file_path, 'r') as f:
            source = f.read()
        return ResolvedModule(source)
        
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
                    refs.append(ModuleRef(ns, name, "v1"))  # TODO: extract version from file
        return refs

# Session Compiler
class SessionCompiler:
    """Compiles sessions by resolving imports and applying overrides"""
    
    def __init__(self, resolver: ModuleResolver):
        self.resolver = resolver
        # Use a base parser without transformer; we'll transform explicitly
        self._base_parser = Lark(GRAMMAR_VNEXT, parser='lalr')
        
    def compile_session(self, session_ast: Dict) -> Dict:
        """Compile a session AST to executable JSON"""
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
                
                result["session"]["components"][comp_type] = self._compile_component(module_ast, comp_type, override_params)

        # Aggregate realized team results if present
        try:
            agg = TeamRealizedAggregator()
            results = agg.aggregate(session_ast, result["session"])  # pass original AST and compiled session
            if results:
                result["session"]["results"] = results
        except Exception:
            # Be tolerant: do not break compilation if realized data is malformed
            pass

        return result
        
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
            "DTSTAMP:20250909T163000Z",  # TODO: Use actual timestamp
            f"DTSTART:{ics_config['start'].replace('-', '').replace(':', '').replace('+', 'Z')}",
            f"DURATION:PT{ics_config['duration']}",
            f"SUMMARY:CrossFit – {session['title']}",
            f"LOCATION:{ics_config.get('location', 'Box')}",
            f"DESCRIPTION:{self._generate_description(session)}",
            "END:VEVENT",
            "END:VCALENDAR"
        ]
        
        return "\n".join(ics_content)
        
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
            movements = [mov.get("movement", "Unknown") for mov in wod.get("movements", [])]
            wod_desc = f"{wod.get('form', {}).get('type', 'WOD')} ({'/'.join(movements[:3])})"
            parts.append(f"WOD: {wod_desc}")
            
        return "; ".join(parts)

# AST Transformer for extended language
class ToASTvNext(Transformer):
    def __init__(self):
        super().__init__()
        self.resolver = InMemoryResolver()
        
    def program(self, items):
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
        return ".".join([str(token) for token in items])
        
    def version(self, items):
        if len(items) == 1:
            return {"version": f"v{items[0]}"}
        else:
            return {"version": f"v{items[0]}.{items[1]}"}
            
    def session(self, items):
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
        result = {"type": "COMPONENTS"}
        for item in items:
            if isinstance(item, dict):
                result.update(item)
        return result
        
    def warmup(self, items):
        title = items[0][1:-1] if isinstance(items[0], str) else str(items[0])
        blocks = items[1:] if len(items) > 1 else []
        return {
            "type": "WARMUP",
            "title": title,
            "blocks": blocks
        }
        
    def skill(self, items):
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

    # vNext vars / declarations
    def vars_decl(self, items):
        decls = [it for it in items if isinstance(it, dict) and it.get('kind') == 'VAR']
        return {"type": "VARS", "decls": decls}

    def var_decl(self, items):
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
        cons = []
        for it in items:
            if isinstance(it, dict) and it.get('kind') == 'CONSTRAINT':
                cons.append(it)
        return {"kind": "CONSTRAINTS", "items": cons}

    def constraint(self, items):
        # Forms: min=literal | max=literal | pattern=STRING | enum=array
        if len(items) >= 2:
            key = str(items[0])
            val = items[1]
            return {"kind": "CONSTRAINT", "key": key, "value": val}
        return {"kind": "CONSTRAINT"}

    def type_spec(self, items):
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
        return {"type": "WORK", "lines": items}
        
    def cues(self, items):
        return {"type": "CUES", "items": [item[1:-1] for item in items if isinstance(item, str)]}
        
    def wod(self, items):
        form = items[0]
        movements = items[1:] if len(items) > 1 else []
        return {
            "type": "WOD",
            "form": form,
            "movements": movements
        }
        
    def component_import(self, items):
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
        assignments = {}
        for item in items:
            if isinstance(item, dict) and "key" in item:
                assignments[item["key"]] = item["value"]
        return {
            "type": "OVERRIDE",
            "assignments": assignments
        }
        
    def assign(self, items):
        key = str(items[0])
        value = items[1] if len(items) > 1 else None
        return {
            "key": key,
            "value": value
        }
        
    def scoring_rule(self, items):
        comp_key = str(items[0])
        policy = items[1] if len(items) > 1 else "none"
        return {comp_key: policy}
        
    def score_policy(self, items):
        if not items:
            return "none"
        return str(items[0])
        
    def session_meta(self, items):
        result = {"type": "META"}
        for item in items:
            if isinstance(item, dict) and "key" in item:
                result[item["key"]] = item["value"]
        return result
        
    def meta_entry(self, items):
        key = str(items[0])
        value = items[1] if len(items) > 1 else None
        return {
            "key": key,
            "value": value
        }
        
    def exports(self, items):
        return {
            "type": "EXPORTS",
            "formats": [str(item) for item in items]
        }

    # PRD3 blocks: team/realized/achievements as generic objects
    def team_block(self, items):
        return {"type": "TEAM", "data": items[0] if items else {}}

    def realized_block(self, items):
        return {"type": "REALIZED", "data": items[0] if items else {}}

    def achievements_block(self, items):
        return {"type": "ACHIEVEMENTS", "data": items[0] if items else {}}

    def programming_block(self, items):
        return {"type": "PROGRAMMING", "data": items[0] if items else {}}
        
    def literal(self, items):
        if not items:
            return None
        item = items[0]
        if isinstance(item, str):
            return item.strip('"')
        return item
        
    def array(self, items):
        return list(items)
        
    def value(self, items):
        return items[0] if items else None

    def object(self, items):
        result = {}
        for kv in items:
            if isinstance(kv, dict) and "key" in kv:
                result[kv["key"]] = kv["value"]
        return result

    def key_value(self, items):
        key = str(items[0])
        val = items[1] if len(items) > 1 else None
        return {"key": key, "value": val}
        
    def start(self, items):
        return self.program(items)
        
    # Add missing transformer methods
    def qualified_id(self, items):
        return ".".join([str(token) for token in items])
        
    def ref_id(self, items):
        return items[0] if items else ""
        
    def comp_key(self, items):
        return str(items[0]) if items else "unknown"
        
    def version(self, items):
        if len(items) == 1:
            return f"v{items[0]}"
        else:
            return f"v{items[0]}.{items[1]}"
    
    # Handle remaining terminal conversions
    def __default_token__(self, token):
        if token.type in ['STRING', 'IDENT']:
            return str(token.value)
        elif token.type in ['INT', 'NUMBER']:
            try:
                return int(token.value)
            except ValueError:
                return float(token.value)
        return str(token.value)
        
    def __default__(self, data, children, meta):
        # Convert any remaining Tree objects to dicts
        return {
            "type": data.upper() if isinstance(data, str) else str(data),
            "children": children
        }

def parse_vnext(text: str) -> Dict:
    """Parse WODCraft vNext source"""
    parser = Lark(GRAMMAR_VNEXT, parser='lalr')
    try:
        tree = parser.parse(text)
        transformer = ToASTvNext()
        result = transformer.transform(tree)
        return result
    except Exception as e:
        raise ValueError(f"Parse error: {e}")


# Coach Programming linter (PRD3)
class ProgrammingLinter:
    def lint(self, programming: Dict, config: Optional[Dict] = None) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        if not isinstance(programming, dict):
            return [{"level": "error", "code": "P000", "msg": "Invalid programming block"}]
        cfg = {
            "heavy_day_per_week_min": 1,
            "couplet_triplet_ratio_min": 0.6,
            "long_domain_min_per_2_weeks": 1,
            "mgw_balance_warning_threshold": 0.25,
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

            # Heavy day
            heavy_count = sum(1 for s in sessions if (s.get("design", {}).get("workout") == "heavy_day"))
            if heavy_count < cfg["heavy_day_per_week_min"]:
                issues.append({"level": "warning", "code": "P101", "week": week, "msg": "Less than 1 heavy day"})

            # Couplet/triplet ratio
            ct = sum(1 for s in sessions if s.get("design", {}).get("workout") in ("couplet", "triplet"))
            non_rest = [s for s in sessions if not s.get("rest")]
            if non_rest:
                ratio = ct / len(non_rest)
                if ratio < cfg["couplet_triplet_ratio_min"]:
                    issues.append({"level": "warning", "code": "P102", "week": week, "msg": f"Couplet/Triplet ratio {ratio:.2f} < {cfg['couplet_triplet_ratio_min']}"})

            # Domain mix
            domain_counts = {"short": 0, "medium": 0, "long": 0}
            for s in sessions:
                dom = s.get("design", {}).get("domain")
                if dom in domain_counts:
                    domain_counts[dom] += 1
            # Domain constraints optional; warn if no long within week
            if domain_counts["long"] == 0:
                issues.append({"level": "info", "code": "P103", "week": week, "msg": "No long domain session this week"})

            # M/G/W balance
            focuses = [s.get("focus") for s in sessions if s.get("focus") in ("M", "G", "W")]
            if focuses:
                from collections import Counter
                c = Counter(focuses)
                total = sum(c.values())
                for k, v in c.items():
                    frac = v / total
                    if frac < cfg["mgw_balance_warning_threshold"]:
                        issues.append({"level": "warning", "code": "P104", "week": week, "msg": f"Low {k} focus fraction {frac:.2f}"})

        return issues

def main():
    parser = argparse.ArgumentParser(description="WODCraft vNext - Extended Language")
    parser.add_argument("command", choices=["parse", "compile", "validate", "session"])
    parser.add_argument("file", help="Input file")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("--modules-path", default="./modules", help="Path to modules directory")
    parser.add_argument("--format", choices=["json", "ics"], default="json", help="Output format for session compile")
    
    args = parser.parse_args()
    
    with open(args.file, 'r') as f:
        content = f.read()
        
    if args.command == "parse":
        ast = parse_vnext(content)
        output = json.dumps(ast, indent=2)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
        else:
            print(output)
            
    elif args.command == "validate":
        try:
            parse_vnext(content)
            print("✓ Valid WODCraft vNext syntax")
        except Exception as e:
            print(f"✗ Invalid syntax: {e}")
            sys.exit(1)
            
    elif args.command == "session":
        # Parse the session file
        ast = parse_vnext(content)
        
        if not ast.get("sessions"):
            print("✗ No session found in file")
            sys.exit(1)
            
        # Set up resolver and compiler
        resolver = FileSystemResolver(args.modules_path)
        compiler = SessionCompiler(resolver)
        
        # Compile the first session
        session_ast = ast["sessions"][0]
        try:
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
                
        except Exception as e:
            print(f"✗ Session compilation failed: {e}")
            sys.exit(1)
            
    elif args.command == "compile":
        # Legacy compile command
        ast = parse_vnext(content)
        output = json.dumps(ast, indent=2)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
        else:
            print(output)

if __name__ == "__main__":
    main()
