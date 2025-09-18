#!/usr/bin/env python3
"""
Build a unified movements catalog from:
- box_catalog.json (root)
- mcp/data/movements.json
- all .wod files under repository (heuristic extraction)

Writes data/movements_catalog.json
"""
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]

LEGACY = ROOT / "box_catalog.json"
MCP = ROOT / "mcp" / "data" / "movements.json"
SEEDS = ROOT / "data" / "movements_seeds.json"
CROSSFIT_WARMUP = ROOT / "crossfit_warmup_movements.json"
OUTPUT = ROOT / "data" / "movements_catalog.json"

KEYWORDS = set(
    k.lower()
    for k in [
        "wod","team","cap","score","tracks","buyin","cashout","rest","block","track","tiebreak","work","partition",
        "amrap","emom","ft","rft","chipper","tabata","interval",
        # Language core modules
        "module","vars","warmup","skill","strength","wod","score","session","components","import","override","scoring","meta","exports","json","html","ics","programming","team","realized","achievements",
        # qualifiers
        "maxrep","max",
    ]
)

GUESS_CATEGORY = [
    (re.compile(r"run|row|bike|ski|du|double_unders|burpee|jumping_jacks|row_cal"), "mono"),
    (re.compile(r"squat|deadlift|clean|snatch|press|jerk|thruster|kb|kettlebell|dumbbell|ohs|overhead"), "weightlifting"),
    (re.compile(r"pull[_-]?up|push[_-]?up|hspu|handstand|dip|muscle[_-]?up|pistol|sit[_-]?up|toes[_-]?to[_-]?bar|ttb|ring"), "gymnastics"),
    (re.compile(r"wall[_-]?ball|slam|box[_-]?jump"), "conditioning"),
]

def canon_id(name: str) -> str:
    t = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return t.lower()

def gen_aliases(cid: str) -> list[str]:
    base = cid.replace("_", " ")
    dashed = cid.replace("_", "-")
    title = base.title()
    return sorted({base, dashed, title, cid})

def guess_category(cid: str) -> str:
    for pat, cat in GUESS_CATEGORY:
        if pat.search(cid):
            return cat
    return "general"

def merge_dict(dst: dict, src: dict):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge_dict(dst[k], v)
        else:
            dst[k] = v

def load_sources():
    catalog = {"movements": {}}
    # Legacy
    if LEGACY.exists():
        data = json.loads(LEGACY.read_text())
        moves = data.get("movements", {})
        for name, spec in moves.items():
            cid = canon_id(name)
            catalog["movements"].setdefault(cid, {})
            merge_dict(catalog["movements"][cid], spec)
    # MCP
    if MCP.exists():
        data = json.loads(MCP.read_text())
        for name, spec in data.items():
            cid = canon_id(name)
            entry = catalog["movements"].setdefault(cid, {})
            if "category" in spec:
                entry["category"] = spec["category"]
            if "defaultLoad" in spec:
                entry.setdefault("defaults", {})["defaultLoad"] = spec["defaultLoad"]
    # Seeds
    if SEEDS.exists():
        data = json.loads(SEEDS.read_text())
        for name, spec in data.items():
            cid = canon_id(name)
            entry = catalog["movements"].setdefault(cid, {})
            if "category" in spec:
                entry["category"] = spec["category"]
            if "aliases" in spec:
                entry["aliases"] = sorted(set(spec["aliases"] + gen_aliases(cid)))
    # CrossFit warmup movements (optional)
    if CROSSFIT_WARMUP.exists():
        try:
            data = json.loads(CROSSFIT_WARMUP.read_text())
            items = data.get("warmup_movements", [])
            def map_cat(c: str) -> str:
                m = (c or '').lower()
                return {
                    'cardio': 'mono',
                    'bodyweight': 'activation',
                    'barbell_drill': 'skill',
                    'band_work': 'activation',
                    'dynamic_mobility': 'mobility',
                }.get(m, m or 'mobility')
            for it in items:
                name = it.get('name') or it.get('id')
                if not name:
                    continue
                cid = canon_id(name)
                entry = catalog["movements"].setdefault(cid, {})
                entry.setdefault('category', map_cat(it.get('category')))
                entry.setdefault('preferred', name)
                # Keep original name as preferred alias
                aliases = set(entry.get('aliases') or []) | set(gen_aliases(cid)) | {name}
                entry['aliases'] = sorted(aliases)
        except Exception:
            pass
    return catalog

def extract_from_wod(catalog: dict):
    # regex patterns
    files = list(ROOT.rglob("*.wod"))
    for fp in files:
        if "/mcp/" in str(fp):
            continue
        for line in fp.read_text(errors="ignore").splitlines():
            s = line.strip()
            if not s or s.startswith("//") or s.startswith("/*"):
                continue
            # Try match: [count] Movement
            m = re.match(r"^(\d+(?:x\d+)?\s+)?([A-Za-z][A-Za-z0-9_]*)(?:\s|@|$)", s)
            if not m:
                continue
            raw = m.group(2)
            low = raw.lower()
            if low in KEYWORDS:
                continue
            cid = canon_id(raw)
            mv = catalog["movements"].setdefault(cid, {})
            mv.setdefault("aliases", gen_aliases(cid))
            mv.setdefault("category", guess_category(cid))
            mv.setdefault("preferred", raw.replace('_', ' ').title())
    # Finalize aliases for all
    for cid, mv in catalog["movements"].items():
        mv.setdefault("aliases", gen_aliases(cid))
        mv.setdefault("category", guess_category(cid))
        mv.setdefault("preferred", cid.replace('_', ' ').title())

def main():
    catalog = load_sources()
    extract_from_wod(catalog)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {OUTPUT}")

if __name__ == "__main__":
    main()
