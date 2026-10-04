"""Writes data.js: every output shown on the page comes from the real compiler (wodc)."""
import itertools, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent
WODC = sys.argv[1] if len(sys.argv) > 1 else "wodc"


def run(*args):
    p = subprocess.run([WODC, *args], cwd=HERE / "wods", capture_output=True, text=True)
    return (p.stdout + p.stderr).rstrip("\n")


src = lambda n: (HERE / "wods" / f"{n}.wod").read_text().rstrip("\n")
data = {"sources": {}, "boards": {}, "fran": {}, "timers": {}}
for n in ["fran", "cindy", "emom", "strength", "tabata", "deathby", "intervals", "teams", "murph", "session", "bad", "teams_en", "tuesday"]:
    data["sources"][n] = src(n)
for n in ["fran", "cindy", "emom", "strength", "tabata", "deathby", "intervals", "teams", "murph"]:
    data["boards"][n] = run("show", f"{n}.wod", "--lang", "fr" if n == "teams" else "en")
for cat, lvl, units, lang in itertools.product(["men", "women"], ["rx", "scaled"], ["kg", "lb"], ["en", "fr"]):
    data["fran"][f"{cat}-{lvl}-{units}-{lang}"] = run("show", "fran.wod", "--category", cat, "--level", lvl, "--units", units, "--lang", lang)
data["check_bad"] = run("check", "bad.wod")
data["check_tuesday"] = run("check", "tuesday.wod")
data["boards"]["teams_en"] = run("show", "teams_en.wod")
data["session_en"] = run("show", "session.wod")
data["catalog_thruster"] = run("catalog", "thruster")
data["check_fran"] = run("check", "fran.wod")
data["build_fran"] = run("build", "fran.wod")
data["timers"]["fran"] = run("timer", "fran.wod")
data["timers"]["session"] = run("timer", "session.wod")
data["session_fr"] = run("show", "session.wod", "--lang", "fr")
(HERE / "data.js").write_text("window.WOD = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n")
print("data.js:", len(json.dumps(data)), "bytes")
