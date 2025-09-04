
#!/usr/bin/env python3
import sys, json, argparse, re
from pathlib import Path
from typing import Any, Dict, List
from lark import Lark, Transformer, Token, Tree

GRAMMAR = r"""
start: meta* segment*

?meta: title | team | cap_line | score_line | tracks_decl
title: "WOD" STRING
team:  "TEAM" INT
cap_line: "CAP" time
score_line: "SCORE" SCORE_RAW
SCORE_RAW: /[^\n]+/
tracks_decl: "TRACKS" "[" track_id ("," track_id)* "]"
track_id: "RX" | "SCALED" | "BEGINNER" | IDENT

?segment: score_line | buyin | cashout | rest | block | track_block
buyin:   "BUYIN" "{" stmt+ "}"
cashout: "CASHOUT" "{" stmt+ "}"
rest:    "REST" time
block: "BLOCK" block_head block_opt* "{" stmt+ "}" tiebreak?
block_opt: workmode | partition | cap_local

block_head: amrap_head | emom_head | ft_head | rft_head | chipper_head | tabata_head | interval_head
amrap_head: "AMRAP" time
emom_head:  "EMOM" time
ft_head:    "FT"
rft_head:   "RFT" INT
chipper_head: "CHIPPER"
tabata_head: "TABATA" time ":" time "x" INT
interval_head: "INTERVAL" INT "x" "(" time "on" "/" time "off" ")"

workmode: "WORK" "split:any"     -> work_split_any
        | "WORK" "split:even"    -> work_split_even
        | "WORK" "ygig"          -> work_ygig
        | "WORK" "relay"         -> work_relay
        | "WORK" "waterfall" "offset:" time -> work_waterfall
        | "WORK" "synchro" "all" -> work_synchro_all
        | "WORK" "synchro" "lines:" "[" INT ("," INT)* "]" -> work_synchro_lines
partition: "PARTITION" "any"     -> part_any
         | "PARTITION" "even"    -> part_even
         | "PARTITION" "scheme" rep_scheme -> part_scheme
cap_local: "CAP" time
tiebreak: "TIEBREAK" "after" INT "thrusters" -> tb_thrusters
        | "TIEBREAK" "after" INT "reps"      -> tb_reps
        | "TIEBREAK" "after" INT "cal"       -> tb_cal
        | "TIEBREAK" "after" "movement" IDENT -> tb_movement

?stmt: emom_stmt | line
emom_stmt: INT ":" line

line: quantity? movement load? suffix* (";"|NEWLINE)

quantity: REPDUAL           -> dual_reps
        | CALDUAL           -> dual_cal
        | DISTDUAL          -> dual_distance
        | INT               -> reps
        | NUMBER "cal"      -> cal_qty
        | DIST              -> distance_qty
        | TIMEQ             -> hold_time

movement: IDENT ( "_" IDENT )*
load: "@" (LOADVAL|LOADDUAL)

suffix: "SYNC"      -> suff_sync
      | "@shared"   -> suff_shared
      | "@each"     -> suff_each

rep_scheme: INT ("-" INT)*

time: INT ":" INT     -> mmss
    | INT "m"         -> only_m
    | INT "s"         -> only_s

DIST: /\d+(?:\.\d+)?(?:m|km)\b/
TIMEQ: /\d{1,2}:\d{2}/ | /\d+s/
LOADVAL: /\d+(?:\.\d+)?(kg|lb|cm|in|m|km|%)\b/
LOADDUAL: /\d+(?:\.\d+)?\/\d+(?:\.\d+)?(kg|lb|cm|in|m|km|%)\b/
REPDUAL: /\d+\/\d+/
CALDUAL: /\d+(?:\.\d+)?\/\d+(?:\.\d+)?\s*cal/
DISTDUAL: /\d+(?:\.\d+)?\/\d+(?:\.\d+)?(?:m|km)\b/

IDENT: /[a-zA-Z][a-zA-Z0-9_]*/
STRING: ESCAPED_STRING

%import common.INT
%import common.NUMBER
%import common.WS
%import common.NEWLINE
%import common.ESCAPED_STRING

track_block: "TRACK" IDENT "{" /[^}]+/ "}"

%ignore WS
"""

def to_int(x): return int(x)

def time_from_tree(t)->int:
    if isinstance(t, list): t = t[0]
    if isinstance(t, Tree):
        if t.data == "mmss": return int(t.children[0])*60 + int(t.children[1])
        if t.data == "only_m": return int(t.children[0]) * 60
        if t.data == "only_s": return int(t.children[0])
    raise ValueError("bad time")

class ToAST(Transformer):
    def track_block(self, xs): return {'type':'TRACK_BLOCK','ignored':True}
    def segment(self, xs): return xs[0] if xs else None
    def block_head(self, xs): return xs[0] if xs else None
    def stmt(self, xs): return xs[0] if xs else None
    def start(self, items):
        meta = {"title": None, "team": None, "cap": None, "score": {}, "tracks_declared": [], "tracks": []}
        program = []
        for it in items:
            if isinstance(it, dict) and it.get("_k")=="meta":
                k = it["k"]; v = it["v"]
                if k=="title": meta["title"]=v
                elif k=="team": meta["team"]=v
                elif k=="cap": meta["cap"]=v
                elif k=="score": meta["score"].update(v)
                elif k=="tracks_decl": meta["tracks_declared"]=v
            else:
                program.append(it)
        return {"meta": meta, "program": program}
    def title(self, s): return {"_k":"meta","k":"title","v": s[0][1:-1]}
    def team(self, xs): return {"_k":"meta","k":"team","v":{"size": int(xs[0])}}
    def cap_line(self, t): return {"_k":"meta","k":"cap","v": time_from_tree(t)}
    def score_line(self, xs):
        raw = xs[0].value if hasattr(xs[0],'value') else str(xs[0])
        out={}
        for part in raw.split(','):
            if '=' in part:
                k,v = part.split('=',1); out[k.strip()] = v.strip()
        return {"_k":"meta","k":"score","v": out}
    def tracks_decl(self, xs): return {"_k":"meta","k":"tracks_decl","v":[x.value for x in xs if isinstance(x,Token)]}

    def buyin(self, xs):   return {"type":"BUYIN","stmts": xs}
    def cashout(self, xs): return {"type":"CASHOUT","stmts": xs}
    def rest(self, t):     return {"type":"REST","duration": time_from_tree(t)}
    def block(self, xs):
        head = xs[0]; work=None; part=None; cap=None; tb=None; stmts=[]
        for x in xs[1:]:
            if isinstance(x, dict) and x.get("_k")=="work": work = x["v"]
            elif isinstance(x, dict) and x.get("_k")=="part": part = x["v"]
            elif isinstance(x, dict) and x.get("_k")=="cap": cap = x["v"]
            elif isinstance(x, dict) and x.get("_k")=="tiebreak": tb = x["v"]
            elif isinstance(x, dict) and x.get("type") in ("LINE","EMOM_LINE"): stmts.append(x)
            elif isinstance(x, list): stmts.extend([y for y in x if isinstance(y, dict)])
        out = {"type":"BLOCK","head":head,"stmts":stmts}
        if work: out["work"]=work
        if part: out["partition"]=part
        if cap:  out["cap"]=cap
        if tb:   out["tiebreak"]=tb
        return out
    def amrap_head(self, t): return {"mode":"AMRAP","duration": time_from_tree(t)}
    def emom_head(self, t):  return {"mode":"EMOM","duration": time_from_tree(t)}
    def ft_head(self, _):    return {"mode":"FT"}
    def rft_head(self, n):   return {"mode":"RFT","rounds": int(n[0])}
    def chipper_head(self,_):return {"mode":"CHIPPER"}
    def tabata_head(self, xs): return {"mode":"TABATA","work":time_from_tree(xs[0]),"rest":time_from_tree(xs[1]),"sets":int(xs[2])}
    def interval_head(self, xs): return {"mode":"INTERVAL","sets":int(xs[0]),"work":time_from_tree(xs[1]),"rest":time_from_tree(xs[2])}
    def work_split_any(self,_):  return {"_k":"work","v":{"mode":"split_any"}}
    def work_split_even(self,_): return {"_k":"work","v":{"mode":"split_even"}}
    def work_ygig(self,_):       return {"_k":"work","v":{"mode":"ygig"}}
    def work_relay(self,_):      return {"_k":"work","v":{"mode":"relay"}}
    def work_waterfall(self, t): return {"_k":"work","v":{"mode":"waterfall","offset": time_from_tree(t)}}
    def work_synchro_all(self,_):return {"_k":"work","v":{"mode":"synchro_all"}}
    def work_synchro_lines(self, xs):
        lines = [int(x) for x in xs if isinstance(x, Token)]
        return {"_k":"work","v":{"mode":"synchro_lines","lines": lines}}
    def part_any(self,_):   return {"_k":"part","v":{"mode":"any"}}
    def part_even(self,_):  return {"_k":"part","v":{"mode":"even"}}
    def part_scheme(self, xs):
        ints = [str(i) for i in xs if isinstance(i, Token)]
        return {"_k":"part","v":{"mode":"scheme","scheme":"-".join(ints)}}
    def cap_local(self, t): return {"_k":"cap","v": time_from_tree(t)}
    def tb_thrusters(self, xs): return {"_k":"tiebreak","v":{"type":"after_thrusters","count": int(xs[0])}}
    def tb_reps(self, xs):      return {"_k":"tiebreak","v":{"type":"after_reps","count": int(xs[0])}}
    def tb_cal(self, xs):       return {"_k":"tiebreak","v":{"type":"after_cal","count": int(xs[0])}}
    def tb_movement(self, xs):  return {"_k":"tiebreak","v":{"type":"after_movement","movement": xs[0].value}}

    def emom_stmt(self, xs): return {"type":"EMOM_LINE","slot": int(xs[0]), "line": xs[1]}
    def line(self, xs):
        qty=None; mv=None; load=None; flags=[]
        for x in xs:
            if isinstance(x, dict) and x.get("_k")=="qty": qty=x["v"]
            elif isinstance(x, dict) and x.get("_k")=="mv": mv=x["v"]
            elif isinstance(x, dict) and x.get("_k")=="load": load=x["v"]
            elif isinstance(x, str): flags.append(x)
        return {"type":"LINE","qty":qty,"movement":mv,"load":load,"flags":flags}
    def dual_reps(self, tok):
        raw = tok[0].value if hasattr(tok[0],'value') else str(tok[0]); a,b = raw.split('/')
        return {'_k':'qty','v':{'kind':'dual_reps','a': int(a), 'b': int(b)}}
    def dual_cal(self, tok):
        raw = tok[0].value if hasattr(tok[0],'value') else str(tok[0]); raw = raw.replace('cal','').strip()
        a,b = [float(x) for x in raw.split('/')]
        return {'_k':'qty','v':{'kind':'dual_cal','a': a, 'b': b}}
    def dual_distance(self, tok):
        raw = tok[0].value if hasattr(tok[0],'value') else str(tok[0])
        m = re.match(r'^(\\d+(?:\\.\\d+)?)/(\\d+(?:\\.\\d+)?)(m|km)$', raw)
        if m:
            a,b,unit = m.groups()
            def to_m(x): v=float(x); return v*(1000 if unit=='km' else 1)
            return {'_k':'qty','v':{'kind':'dual_distance','a': to_m(a), 'b': to_m(b), 'unit':'m'}}
        return {'_k':'qty','v':{'kind':'dual_distance','a':0,'b':0,'unit':'m'}}
    def reps(self, n):         return {'_k':'qty','v':{'kind':'reps','value': int(n[0])}}
    def cal_qty(self, xs):     return {'_k':'qty','v':{'kind':'cal','value': float(xs[0])}}
    def distance_qty(self, d):
        tok = d[0] if isinstance(d, list) else d
        raw = tok.value if hasattr(tok,'value') else str(tok)
        m = re.match(r'^(\\d+(?:\\.\\d+)?)(m|km)\\b', raw)
        if not m:
            return {'_k':'qty','v':{'kind':'distance','value': 0, 'unit':'m'}}
        val,unit = m.groups()
        meters = float(val) * (1000 if unit=='km' else 1)
        return {'_k':'qty','v':{'kind':'distance','value': meters, 'unit':'m'}}
    def hold_time(self, t):
        tok = t[0] if isinstance(t, list) else t
        raw = tok.value if hasattr(tok,'value') else str(tok)
        if ':' in raw: mm,ss=raw.split(':'); return {'_k':'qty','v':{'kind':'time','value': int(mm)*60+int(ss)}}
        m = re.match(r'^(\\d+)s$', raw); 
        return {'_k':'qty','v':{'kind':'time','value': int(m.group(1)) if m else 0}}
    def movement(self, parts):
        vals = [p.value if isinstance(p,Token) else str(p) for p in parts]
        return {"_k":"mv","v":"_".join(vals)}
    def load(self, v):
        raw = v[0].value if hasattr(v[0],'value') else str(v[0])
        m = re.match(r'^(\\d+(?:\\.\\d+)?)/(\\d+(?:\\.\\d+)?)(kg|lb|cm|in|m|km|%)$', raw)
        if m:
            a,b,unit = m.groups()
            def mk(val,unit):
                if unit in ('kg','lb'): return {'kind':'weight','value': float(val),'unit':unit}
                if unit in ('cm','in'): return {'kind':'height','value': float(val),'unit':unit}
                if unit in ('m','km'):
                    meters = float(val) * (1000 if unit=='km' else 1)
                    return {'kind':'distance','value': meters,'unit':'m'}
                if unit=='%': return {'kind':'percent_raw','value': float(val)}
            return {'_k':'load','v':{'kind':'dual','a': mk(a,unit), 'b': mk(b,unit)}}
        m2 = re.match(r'^(\\d+(?:\\.\\d+)?)(kg|lb|cm|in|m|km|%)$', raw)
        if m2:
            val, unit = m2.groups()
            if unit in ('kg','lb'): return {'_k':'load','v':{'kind':'weight','value': float(val), 'unit': unit}}
            if unit in ('cm','in'): return {'_k':'load','v':{'kind':'height','value': float(val), 'unit': unit}}
            if unit in ('m','km'):
                meters = float(val) * (1000 if unit=='km' else 1)
                return {'_k':'load','v':{'kind':'distance','value': meters, 'unit':'m'}}
            if unit == '%': return {'_k':'load','v':{'kind':'percent_raw','value': float(val)}}
        return {'_k':'load','v':{'kind':'raw','value': raw}}
    def suff_sync(self,_):   return "SYNC"
    def suff_shared(self,_): return "@shared"
    def suff_each(self,_):   return "@each"

def parse_wod_text(text:str)->Dict[str,Any]:
    parser = Lark(GRAMMAR, start="start", parser="earley", lexer="dynamic_complete")
    tree = parser.parse(text)
    ast = ToAST().transform(tree)
    return ast

# Movement aliases and known list
KNOWN_MOVEMENTS = {
    "wall_balls","box_jumps","run","thrusters","pullups","ring_rows","bike",
    "burpees","sandbag_carry","hollow_hold","toes_to_bar","row","double_unders",
    "clean","rope_climbs","burpee_box_jump_over","power_clean","assault_bike"
}
MOVEMENT_ALIASES = {
    "wb":"wall_balls","wallball":"wall_balls",
    "bj":"box_jumps","box_jump":"box_jumps",
    "pu":"pullups","pull_up":"pullups",
    "rr":"ring_rows","ring_row":"ring_rows",
    "t2b":"toes_to_bar","ttb":"toes_to_bar",
    "du":"double_unders","dus":"double_unders","double_under":"double_unders",
    "row":"row","run":"run","bike":"bike","echo_bike":"bike","assault_bike":"assault_bike",
    "bbjo":"burpee_box_jump_over","bjo":"burpee_box_jump_over","burpee_box_jumps":"burpee_box_jump_over",
    "rc":"rope_climbs","rope_climb":"rope_climbs",
    "pc":"power_clean","power_clean":"power_clean","clean":"clean","cleans":"clean",
    "sb_carry":"sandbag_carry","sandbag_carry":"sandbag_carry",
    "burpee":"burpees","burpees":"burpees","hollow_hold":"hollow_hold"
}
def _normalize_mv(name:str): return MOVEMENT_ALIASES.get(name.lower(), name)

def _apply_catalog_and_resolve(ast, catalog, track, gender, issues_out):
    def resolve_qty(q):
        if not q: return q
        k = q.get('kind')
        if k=='dual_reps': return {'kind':'reps','value': q['a'] if gender=='male' else q['b']}
        if k=='dual_cal': return {'kind':'cal','value': q['a'] if gender=='male' else q['b']}
        if k=='dual_distance': return {'kind':'distance','value': q['a'] if gender=='male' else q['b'], 'unit':'m'}
        return q
    def resolve_load(ld):
        if not ld: return ld
        if ld.get('kind')=='dual': return ld['a'] if gender=='male' else ld['b']
        if ld.get('kind')=='raw':
            raw = str(ld.get('value',''))
            m = re.match(r'^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)(kg|lb|cm|in|m|km|%)$', raw)
            if m:
                a,b,unit = m.groups()
                pick = a if gender=='male' else b
                if unit in ('kg','lb'): return {'kind':'weight','value': float(pick), 'unit': unit}
                if unit in ('cm','in'): return {'kind':'height','value': float(pick), 'unit': unit}
                if unit in ('m','km'):
                    meters = float(pick) * (1000 if unit=='km' else 1)
                    return {'kind':'distance','value': meters, 'unit':'m'}
                if unit=='%': return {'kind':'percent_raw','value': float(pick)}
        return ld
    def apply_catalog_line(ln):
        if not catalog: return
        mv = ln.get('movement'); tkey = track.lower()
        move = (catalog.get('movements') or {}).get(mv) or {}
        if not ln.get('qty') or (ln.get('qty',{}).get('kind')=='distance' and ln.get('qty',{}).get('value')==0):
            v = (move.get('reps') or {}).get(tkey,{}).get(gender)
            if v is not None: ln['qty']={'kind':'reps','value':int(v)}
            else:
                v = (move.get('distance') or {}).get(tkey,{}).get(gender)
                if v is not None: ln['qty']={'kind':'distance','value':float(v),'unit':'m'}
                else:
                    v = (move.get('cal') or {}).get(tkey,{}).get(gender)
                    if v is not None: ln['qty']={'kind':'cal','value':float(v)}
        if not ln.get('load'):
            ld = (move.get('load') or {}).get(tkey,{}).get(gender)
            if isinstance(ld,str):
                m = re.match(r'^(\\d+(?:\\.\\d+)?)(kg|lb|cm|in|m)$', ld)
                if m:
                    val,unit=m.groups()
                    if unit in ('kg','lb'): ln['load']={'kind':'weight','value':float(val),'unit':unit}
                    elif unit in ('cm','in'): ln['load']={'kind':'height','value':float(val),'unit':unit}
                    elif unit=='m': ln['load']={'kind':'distance','value':float(val),'unit':'m'}
            elif isinstance(ld,dict): ln['load']=ld

    notes=[]
    for seg in ast.get('program', []):
        if seg.get('type') in ('BUYIN','CASHOUT'):
            it = seg.get('stmts',[])
        elif seg.get('type')=='BLOCK':
            it = [ st if st.get('type')=='LINE' else st.get('line',{}) for st in seg.get('stmts',[]) ]
        else:
            it = []
        for ln in it:
            mv = ln.get('movement')
            if mv:
                norm=_normalize_mv(mv)
                if norm!=mv: ln['movement']=norm; notes.append({'code':'W050','from':mv,'to':norm})
            ln['qty']=resolve_qty(ln.get('qty'))
            ln['load']=resolve_load(ln.get('load'))
            apply_catalog_line(ln)
    ast.setdefault('meta',{}).setdefault('normalized',notes)

def lint(ast:Dict[str,Any])->List[Dict[str,Any]]:
    issues = []
    # Alias notes
    for n in ast.get('meta',{}).get('normalized',[]): issues.append({'level':'warning','code':'W050','path':'META','msg':f"Alias '{n['from']}' -> '{n['to']}'"})
    def check_line(ln, path):
        mv = ln.get("movement")
        if mv and mv not in KNOWN_MOVEMENTS:
            issues.append({"level":"warning","code":"W001","path":path,"msg":f"Unknown movement '{mv}'"})
        ld = ln.get("load")
        if ld and ld.get("kind")=="raw":
            raw = ld.get("value","")
            if not re.match(r'^\d+(?:\.\d+)?(kg|lb|cm|in|m|km|%.*)?$', raw):
                issues.append({"level":"warning","code":"W002","path":path,"msg":f"Suspicious load '{raw}'"})
    for i, seg in enumerate(ast.get("program", [])):
        t = seg.get("type")
        if t in ("BUYIN","CASHOUT"):
            for j, ln in enumerate(seg.get("stmts", [])):
                if ln.get("type")=="LINE": check_line(ln, f"{t}[{j}]")
        elif t == "REST":
            if seg.get("duration",0) <= 0:
                issues.append({"level":"error","code":"E010","path":f"REST[{i}]","msg":"REST must be > 0"})
        elif t == "BLOCK":
            head = seg.get("head",{})
            if head.get("mode")=="EMOM":
                if not any(s.get("type")=="EMOM_LINE" for s in seg.get("stmts",[])):
                    issues.append({"level":"error","code":"E020","path":f"BLOCK[{i}]","msg":"EMOM has no slots"})
            for j, st in enumerate(seg.get("stmts", [])):
                ln = st.get("line", st)
                check_line(ln, f"BLOCK[{i}].LINE[{j}]")
    return issues

def est_line_seconds(ln:dict)->float:
    q = ln.get("qty"); mv = ln.get("movement","")
    if not q: return 2.0
    k = q.get("kind")
    if k=="reps": pace = {"thrusters":3.0,"pullups":2.0,"ring_rows":1.8,"burpees":3.5,"wall_balls":2.5,"box_jumps":2.8,"toes_to_bar":2.5}.get(mv,3.0); return pace*float(q["value"])
    if k=="cal":  pace = 3.0 if mv=="row" else 3.5; return pace*float(q["value"])
    if k=="distance": pace = {"row":0.35,"run":0.6,"sandbag_carry":0.9}.get(mv,0.9); return pace*float(q["value"])
    if k=="time": return float(q["value"])
    return 5.0

def est_block_seconds(block:dict)->float:
    head = block.get("head",{}); mode = head.get("mode")
    if mode in ("AMRAP","EMOM"): return float(head.get("duration",0))
    if mode=="FT": return sum(est_line_seconds(st if st.get("type")=="LINE" else st.get("line",{})) for st in block.get("stmts",[]))
    if mode=="RFT":
        r=int(head.get("rounds",1)); per=sum(est_line_seconds(st if st.get("type")=="LINE" else st.get("line",{})) for st in block.get("stmts",[])); return r*per
    if mode=="CHIPPER": return sum(est_line_seconds(st if st.get("type")=="LINE" else st.get("line",{})) for st in block.get("stmts",[]))
    if mode=="TABATA": return int(head.get("sets",0))*(float(head.get("work",0))+float(head.get("rest",0)))
    if mode=="INTERVAL": return int(head.get("sets",0))*(float(head.get("work",0))+float(head.get("rest",0)))
    return 0.0

def build_timeline(ast:Dict[str,Any])->List[Dict[str,Any]]:
    t = 0; ev = []
    def emit(typ, **kw): ev.append({"t": t, "type": typ, **kw})
    for seg in ast.get("program", []):
        typ = seg.get("type")
        if typ == "BUYIN":
            emit("START_BUYIN")
            for ln in seg.get("stmts", []):
                if ln.get("type")=="LINE": emit("PROMPT", text=render_line(ln))
            emit("END_BUYIN")
        elif typ == "REST":
            dur = seg.get("duration",0); emit("REST_START", duration=dur); t += dur; emit("REST_END")
        elif typ == "BLOCK":
            head = seg.get("head",{}); mode = head.get("mode")
            emit("START_BLOCK", mode=mode)
            if mode == "AMRAP":
                for ln in seg.get("stmts", []):
                    if ln.get("type")=="LINE": emit("PROMPT", text=render_line(ln))
                t += head.get("duration",0); emit("END_BLOCK")
            elif mode == "EMOM":
                dur = head.get("duration",0); minutes = dur // 60
                slots = {}
                for st in seg.get("stmts", []):
                    if st.get("type")=="EMOM_LINE": slots[st["slot"]] = st["line"]
                for i in range(minutes):
                    if not slots: break
                    idx = (i % len(slots)) + 1
                    emit("NEXT_SLOT", slot=idx, text=render_line(slots[idx])); t += 60
                emit("END_BLOCK")
            else:
                for ln in seg.get("stmts", []):
                    if ln.get("type")=="LINE": emit("PROMPT", text=render_line(ln))
                t += int(est_block_seconds(seg)); emit("END_BLOCK")
        elif typ == "CASHOUT":
            emit("START_CASHOUT")
            for ln in seg.get("stmts", []):
                if ln.get("type")=="LINE": emit("PROMPT", text=render_line(ln))
            emit("END_CASHOUT")
    return ev

def hhmmss(s:int)->str:
    m, sec = divmod(s,60); h, m = divmod(m,60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"

def render_line(ln:Dict[str,Any])->str:
    qty = ln.get("qty"); qtxt = ""
    if qty:
        k = qty["kind"]
        if k=="reps": qtxt = f"{qty['value']} "
        elif k=="cal": qtxt = f"{qty['value']} cal "
        elif k=="distance": qtxt = f"{int(qty['value'])}m "
        elif k=="time": qtxt = f"{hhmmss(int(qty['value']))} "
    mv = ln.get("movement",""); ltxt = ""
    ld = ln.get("load")
    if ld:
        kind = ld.get("kind")
        if kind in ("weight","height"): ltxt = f" @{int(ld['value'])}{ld['unit']}"
        elif kind=="distance": ltxt = f" @{int(ld['value'])}m"
        elif kind=="percent_raw": ltxt = f" @{int(ld['value'])}%"
    flags = " ".join(ln.get("flags",[])) if ln.get("flags") else ""
    return (qtxt + mv + ltxt + (" " + flags if flags else "")).strip()

def _normalize_wod_text(text: str) -> str:
    # Minimal, safe normalization: strip trailing spaces, collapse multiple
    # blank lines to a single one, and ensure a trailing newline.
    lines = text.splitlines()
    out = []
    prev_blank = False
    for ln in lines:
        s = ln.rstrip()
        is_blank = (s == "")
        if is_blank and prev_blank:
            continue
        out.append(s)
        prev_blank = is_blank
    return "\n".join(out).rstrip("\n") + "\n"

def main():
    ap = argparse.ArgumentParser(prog="wodc2")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("parse"); p1.add_argument("file"); p1.add_argument("-o","--out")
    p2 = sub.add_parser("lint");  p2.add_argument("file")
    p3 = sub.add_parser("run");   p3.add_argument("file"); p3.add_argument("--format", choices=["text","json"], default="text")
    p4 = sub.add_parser("export");p4.add_argument("file"); p4.add_argument("--to", choices=["json","ics","html"], required=True); p4.add_argument("-o","--out", required=True)
    p5 = sub.add_parser("fmt");   p5.add_argument("file"); p5.add_argument("-i","--in-place", action="store_true"); p5.add_argument("-o","--out")
    for pp in (p1,p2,p3,p4):
        pp.add_argument('--catalog', help='movement catalog JSON')
        pp.add_argument('--track', choices=['RX','INTERMEDIATE','SCALED'], default='RX')
        pp.add_argument('--gender', choices=['male','female'], default='male')
    args = ap.parse_args()
    text = Path(args.file).read_text()
    ast = parse_wod_text(text)
    catalog = json.loads(Path(args.catalog).read_text()) if args.catalog else None
    issues_buf=[]
    _apply_catalog_and_resolve(ast, catalog, args.track, args.gender, issues_buf)

    if args.cmd=="parse":
        data = json.dumps(ast, ensure_ascii=False, indent=2)
        if args.out: Path(args.out).write_text(data); print(f"Saved -> {args.out}")
        else: print(data); sys.exit(0)
        sys.exit(0)
    if args.cmd=="lint":
        issues = lint(ast) + issues_buf
        for i in issues: print(f"{i['level'].upper()} {i['code']} {i['path']}: {i['msg']}")
        sys.exit(1 if any(x['level']=='error' for x in issues) else 0)
    if args.cmd=="run":
        tl = build_timeline(ast)
        if args.format=="json": print(json.dumps(tl, indent=2))
        else:
            for e in tl:
                mm, ss = divmod(e['t'],60)
                rest = {k:v for k,v in e.items() if k not in ('t','type')}
                if rest: print(f"{mm:02d}:{ss:02d} {e['type']} {json.dumps(rest)}")
                else: print(f"{mm:02d}:{ss:02d} {e['type']}")
        sys.exit(0)
    if args.cmd=="export":
        if args.to=="json":
            Path(args.out).write_text(json.dumps(ast, ensure_ascii=False, indent=2)); print(f"Saved -> {args.out}"); sys.exit(0)
        if args.to=="ics":
            # Compute cap = meta.cap or estimated sum
            cap = ast.get("meta",{}).get("cap")
            if cap is None:
                total = 0
                for seg in ast.get("program", []):
                    if seg.get("type")=="REST":
                        total += int(seg.get("duration",0))
                    elif seg.get("type")=="BLOCK":
                        total += int(est_block_seconds(seg))
                cap = int(total)
            def escape(s): return s.replace("\n","\n").replace(",","\,").replace(";","\;")
            lines = []
            lines.append("BEGIN:VCALENDAR")
            lines.append("VERSION:2.0")
            lines.append("PRODID:-//CFDSL//wodc-merged//EN")
            lines.append("BEGIN:VEVENT")
            lines.append(f"UID:wodc-{abs(hash(args.file))}@cf-dsl")
            lines.append("DTSTAMP:20250101T000000Z")
            lines.append("DTSTART:20250101T000000Z")
            lines.append(f"DURATION:PT{int(cap)}S")
            title = ast.get("meta",{}).get("title") or "WOD"
            lines.append(f"SUMMARY:{escape(title)}")
            desc = []
            for seg in ast.get("program", []):
                if seg.get("type")=="BLOCK":
                    head = seg.get("head",{})
                    desc.append(f"- {head.get('mode')}")
                    for st in seg.get("stmts", []):
                        ln = st.get("line", st)
                        if ln.get("type")=="LINE":
                            desc.append("  • " + render_line(ln))
                elif seg.get("type")=="REST":
                    desc.append(f"- REST {int(seg.get('duration',0))}s")
            lines.append("DESCRIPTION:" + escape("\n".join(desc)))
            lines.append("END:VEVENT")
            lines.append("END:VCALENDAR")
            Path(args.out).write_text("\n".join(lines))
            print(f"Saved -> {args.out}"); sys.exit(0)
        if args.to=="html":
            title = ast.get('meta',{}).get('title') or "WOD"
            html = ["""<!doctype html><html><head><meta charset=\"utf-8\"><title>WOD</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;padding:24px;line-height:1.4}
h1{margin:0 0 8px}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;background:#eee;margin-right:8px;font-size:12px}
.block{border:1px solid #e5e7eb;border-radius:12px;padding:12px;margin:12px 0}
.line{padding:2px 0}
.meta{color:#555;margin-bottom:12px}
</style></head><body>"""]
            html.append(f"<h1>{title}</h1>")
            meta = ast.get("meta",{})
            chips = []
            team = meta.get("team"); 
            if team: chips.append(f"<span class='badge'>Team {team.get('size')}</span>")
            if meta.get("cap"): chips.append(f"<span class='badge'>Cap {int(meta['cap']/60)}m</span>")
            score = meta.get("score"); 
            if score: chips.append(f"<span class='badge'>Score {score.get('primary')}</span>")
            if chips: html.append("<div class='meta'>" + " ".join(chips) + "</div>")
            for seg in ast.get("program", []):
                if seg.get("type")=="REST":
                    html.append(f"<div class='block'><strong>REST</strong> {int(seg.get('duration',0))}s</div>")
                elif seg.get("type") in ("BUYIN","CASHOUT"):
                    html.append(f"<div class='block'><strong>{seg['type']}</strong>")
                    for ln in seg.get("stmts", []):
                        if ln.get("type")=="LINE": html.append(f"<div class='line'>{render_line(ln)}</div>")
                    html.append("</div>")
                elif seg.get("type")=="BLOCK":
                    head = seg.get("head",{}); mode = head.get("mode")
                    html.append(f"<div class='block'><strong>{mode}</strong>")
                    if mode in ("AMRAP","EMOM"): html.append(f" <em>{int(head.get('duration',0))}s</em>")
                    part = seg.get("partition"); work = seg.get("work"); capl = seg.get("cap")
                    badges=[]; 
                    if work: badges.append(work.get('mode'))
                    if part: badges.append("partition:"+part.get('mode'))
                    if capl: badges.append(f"cap:{int(capl)}s")
                    if badges: html.append("<div class='meta'>" + " · ".join(badges) + "</div>")
                    for st in seg.get("stmts", []):
                        ln = st.get("line", st)
                        if ln.get("type")=="LINE": html.append(f"<div class='line'>{render_line(ln)}</div>")
                    tb = seg.get("tiebreak")
                    if tb: html.append(f"<div class='meta'><em>TIEBREAK</em> {tb}</div>")
                    html.append("</div>")
            html.append("</body></html>")
            Path(args.out).write_text("".join(html))
            print(f"Saved -> {args.out}"); sys.exit(0)

    if args.cmd=="fmt":
        raw = Path(args.file).read_text()
        # Validate via parse (raises on syntax errors)
        try:
            _ = parse_wod_text(raw)
        except Exception as e:
            print(f"Format check failed: parse error: {e}", file=sys.stderr)
            sys.exit(2)
        normalized = _normalize_wod_text(raw)
        if args.out:
            Path(args.out).write_text(normalized)
            print(f"Saved -> {args.out}")
        elif args.in_place:
            Path(args.file).write_text(normalized)
        else:
            print(normalized, end="")
        sys.exit(0)

if __name__ == "__main__":
    main()
