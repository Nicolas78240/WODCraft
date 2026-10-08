"use strict";
const D = window.WOD;
const LANG = window.LANG, t = window.t;
if (LANG === "fr") document.getElementById("playFr").checked = true;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------- WODCraft syntax highlighting (display only) ---------- */
const META = /^(cap|score|units|vest|note|stimulus|tags|date|time):/i;
const LABEL = /^(\s*)(Scaled|Intermediate|Foundations|Adapted|Buy-in|Cash-out|Odd|Even|Min \d+|Rx):/i;
const FMT = /\b(for time|rounds?|AMRAP|E2MOM|EMOM|Every|Tabata|Death by|Max load|cap|teams of|there and back|aller-retour)\b/gi;
const QTY = /\b(\d+(?:\.\d+)?(?:\/\d+(?:\.\d+)?)?\s?(?:kg|lb|pood|cal|km|mi|ft|in|cm|m|s|min)\b|\d+:\d\d|\d+(?:\.\d+)?%|@)/g;

function hlInline(txt) {
  // tokens: strings, modifiers, operators, quantities, numbers
  const re = /("[^"]*")|(\([^)]*\))|(->|\|)|(\d+(?:\.\d+)?(?:\/\d+(?:\.\d+)?)?\s?(?:kg|lb|pood|cal|km|mi|ft|in|cm|m|s|min)\b|\d+:\d\d|\d+(?:\.\d+)?%|@)|(\b\d+x\d+\b|\b\d+(?:-\d+)+\b|\b\d+\b|\.\.\.)/g;
  let out = "", last = 0, m;
  while ((m = re.exec(txt))) {
    out += esc(txt.slice(last, m.index));
    const cls = m[1] ? "t-str" : m[2] ? "t-mod" : m[3] ? "t-op" : m[4] ? "t-q" : "t-n";
    out += `<span class="${cls}">${esc(m[0])}</span>`;
    last = re.lastIndex;
  }
  return out + esc(txt.slice(last));
}

function hlLine(line) {
  let code = line, comment = "";
  const ci = line.indexOf("//");
  if (ci >= 0) { code = line.slice(0, ci); comment = line.slice(ci); }
  let html;
  if (/^#{1,2}\s/.test(code)) html = `<span class="t-h">${esc(code)}</span>`;
  else if (META.test(code)) {
    const k = code.indexOf(":") + 1;
    html = `<span class="t-meta">${esc(code.slice(0, k))}</span>${hlInline(code.slice(k))}`;
  } else if (LABEL.test(code)) {
    const m = code.match(LABEL);
    html = esc(m[1]) + `<span class="t-lab">${esc(m[0].slice(m[1].length))}</span>` + hlInline(code.slice(m[0].length));
  } else if (code && !/^\s/.test(code) && (FMT.test(code) || /^\d+(-\d+)+/.test(code))) {
    FMT.lastIndex = 0;
    // format line: keywords in red, numbers as usual
    html = hlInline(code).replace(/(^|>)([^<]*)/g, (all, a, t) => a + t.replace(FMT, '<span class="t-fmt">$1</span>'));
  } else html = hlInline(code);
  FMT.lastIndex = 0;
  return html + (comment ? `<span class="t-c">${esc(comment)}</span>` : "");
}
const hl = (src) => src.split("\n").map(hlLine).join("\n");

/* whiteboard rendering: title lines in red, meta lines dimmed */
function boardHtml(txt) {
  return txt.split("\n").map((l, i, a) => {
    const prev = i === 0 || a[i - 1] === "";
    if (prev && l && l === l.toUpperCase() && /[A-Z]/.test(l)) return `<span class="b-title">${esc(l)}</span>`;
    if (/^(Score|Estimate|Levels|Note|Stimulus|Vest|Adapted|Session estimate):|^\[.*\]$|^\d{4}-\d\d-\d\d$/.test(l)) return `<span class="b-dim">${esc(l)}</span>`;
    return esc(l);
  }).join("\n");
}

/* ---------- reveal on scroll ---------- */
const io = new IntersectionObserver((es) => es.forEach((e) => {
  if (!e.isIntersecting) return;
  e.target.classList.add("in");
  e.target.dispatchEvent(new CustomEvent("enter"));
  io.unobserve(e.target);
}), { threshold: 0.18 });
$$("main > section:not(.hero), .why article, .cards article").forEach((el) => { el.classList.add("reveal"); io.observe(el); });

/* ---------- ticker ---------- */
{
  const words = ["For time", "AMRAP 20", "EMOM 12", "21-15-9", "E2MOM 20", "Every 4:00 x 4", "Tabata", "Death by",
    "5x5 @ 75%", "Max load", "Buy-in", "Cash-out", "Teams of 2", t("Aller-retour", "There and back"), "95/65 lb", "Scaled", "1-2-3 …"];
  const html = words.map((w) => `<span>${esc(w.toUpperCase())}</span>`).join("");
  $("#ticker").innerHTML = html + html;
}

/* ---------- hero: type Fran, then compile ---------- */
const heroViews = {
  board: () => boardHtml("$ wodc show fran.wod\n\n" + D.boards.fran).replace("$ wodc show fran.wod", '<span class="b-dim">$ wodc show fran.wod</span>'),
  json: () => esc(D.build_fran),
  timer: () => '<span class="b-dim">$ wodc timer fran.wod</span>\n\n' + esc(D.timers.fran),
};
let heroView = "board", heroAuto = true;
function showHero(v, animate) {
  heroView = v;
  $$("#heroOut [role=tab]").forEach((b) => b.setAttribute("aria-selected", b.dataset.v === v));
  const el = $("#heroBoard");
  el.innerHTML = heroViews[v]();
  el.scrollTop = 0;
  if (animate && !reduced) {
    const lines = el.innerHTML.split("\n");
    el.innerHTML = lines.map((l, i) => `<span class="line-in" style="animation-delay:${Math.min(i, 30) * 45}ms">${l || " "}</span>`).join("\n");
  }
}
$$("#heroOut [role=tab]").forEach((b) => b.addEventListener("click", () => { heroAuto = false; showHero(b.dataset.v, true); }));

async function heroType() {
  const src = D.sources.fran, code = $("#heroCode"), status = $("#heroStatus");
  $("#heroBoard").innerHTML = '<span class="b-dim">' + t("En attente du coach…", "Waiting for the coach…") + "</span>";
  if (reduced) { code.innerHTML = hl(src); status.textContent = D.check_fran; showHero("board"); return; }
  for (let i = 1; i <= src.length; i++) {
    code.innerHTML = hl(src.slice(0, i)) + '<span class="caret"></span>';
    const ch = src[i - 1];
    await sleep(ch === "\n" ? 180 : 28 + Math.random() * 40);
  }
  status.textContent = "$ wodc check fran.wod";
  await sleep(500);
  status.textContent = D.check_fran;
  showHero("board", true);
  const order = ["board", "json", "timer"];
  let k = 0;
  setInterval(() => { if (heroAuto) showHero(order[++k % 3], true); }, 6000);
}
heroType();

/* the box clock: counts up to the 10:00 cap, then starts over */
{
  let t = 0;
  setInterval(() => {
    t = (t + 1) % 601;
    $("#heroClock").textContent = `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
  }, 1000);
}

/* ---------- pipeline ---------- */
const PIPE = [
  () => `<div><p>${t("Le coach écrit le WOD comme il l'écrirait au tableau : un titre, un format, des mouvements. Les valeurs doubles sont hommes/femmes, les niveaux se déclarent en dessous.", "The coach writes the WOD as it would go on the whiteboard: a title, a format, movements. Dual values are men/women, levels are declared underneath.")}</p>
    <div class="chips"><span class="chip">21-15-9 for time</span><span class="chip">cap 10:00</span><span class="chip">95/65 lb</span><span class="chip">Scaled:</span><span class="chip">-></span></div></div>
    <div class="editor"><div class="editor-bar"><i></i><i></i><i></i><span>fran.wod</span></div><pre class="code">${hl(D.sources.fran)}</pre></div>`,
  () => `<div><p>${t("Le lexer découpe en lignes et en jetons, le parseur fait d'une ligne une instruction et rattache chaque bloc à son format. Une erreur de syntaxe pointe la colonne exacte.", "The lexer splits lines into tokens, the parser turns each line into a statement and attaches every block to its format. A syntax error points at the exact column.")}</p>
    <div class="chips"><span class="chip">syntax/lexer.py</span><span class="chip">syntax/lines.py</span><span class="chip">syntax/parser.py</span></div></div>
    <pre class="panel">${esc(PARSE)}</pre>`,
  () => `<div><p>${t("Chaque nom est résolu dans le catalogue — <code>Pull-up</code>, <code>pull ups</code> ou <code>tractions</code> donnent <code>pull_up</code>. Les paramètres sont contrôlés (une charge, une hauteur, une distance ?), les unités converties, le score et la durée déduits.", "Every name is resolved against the catalog — <code>Pull-up</code>, <code>pull ups</code> or <code>tractions</code> all give <code>pull_up</code>. Parameters are checked (a load, a height, a distance?), units converted, the score and the duration inferred.")}</p>
    <div class="chips"><span class="chip">Pull-up → pull_up</span><span class="chip">95/65 lb ↔ 43/30 kg</span><span class="chip">score: time (capped: reps)</span><span class="chip">${t("estimation", "estimate")} 3:22–6:14</span></div></div>
    <pre class="panel"><span class="muted">$ wodc catalog thruster</span>\n${esc(D.catalog_thruster)}</pre>`,
  () => `<div><p>${t("Le document compilé suit <code>spec/workout.schema.json</code>. Il garde la valeur écrite <em>et</em> sa conversion, et la position de chaque ligne source : de quoi afficher, chronométrer, comparer, ou renvoyer une erreur à la bonne place.", "The compiled document follows <code>spec/workout.schema.json</code>. It keeps the written value <em>and</em> its conversion, and the position of every source line: enough to display, time, compare, or report an error in the right place.")}</p>
    <div class="chips"><span class="chip">$ wodc build fran.wod</span></div></div>
    <pre class="panel">${esc(D.build_fran)}</pre>`,
  () => `<div><p>${t("Du même JSON sortent le tableau blanc, le déroulé du chrono, l'événement d'agenda, l'écran d'une app iOS ou la réponse d'un agent IA.", "The same JSON feeds the whiteboard, the timer's run sheet, the calendar event, an iOS app screen or an AI agent's answer.")}</p>
    <pre class="panel" style="margin-top:12px"><span class="muted">$ wodc timer fran.wod</span>\n${esc(D.timers.fran)}</pre>
    <div class="chips"><span class="chip">board</span><span class="chip">timer</span><span class="chip">ics</span><span class="chip">markdown</span><span class="chip">Swift</span><span class="chip">MCP</span></div></div>
    <div class="whiteboard"><pre class="board">${boardHtml(D.boards.fran)}</pre></div>`,
];
const PARSE = `L1  document   # Fran
L2  format     for_time · reps [21, 15, 9] · cap 600 s
L3  movement   Thruster · load 95/65 lb
L4  movement   Pull-up
L6  level      Scaled:
L7    load     Thruster → 65/45 lb
L8    swap     Pull-up → Jumping pull-up`;
let pipeIdx = 0, pipeAuto = true;
function showPipe(i) {
  pipeIdx = i;
  $$("#pipe li").forEach((li) => li.setAttribute("aria-current", +li.dataset.step === i));
  const d = $("#pipeDetail");
  d.innerHTML = PIPE[i]();
  d.style.animation = "none"; void d.offsetWidth; d.style.animation = "";
}
$$("#pipe li").forEach((li) => {
  li.tabIndex = 0;
  const go = () => { pipeAuto = false; showPipe(+li.dataset.step); };
  li.addEventListener("click", go);
  li.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), go()));
});
showPipe(0);
$("#how").addEventListener("enter", () => {
  const t = setInterval(() => { if (!pipeAuto) return clearInterval(t); showPipe((pipeIdx + 1) % PIPE.length); }, 4500);
});

/* ---------- diagnostics: parse the real `wodc check` output ---------- */
{
  const diags = [];
  const DG = t("bad", "tuesday"), DGF = DG === "bad" ? "mardi.wod" : "tuesday.wod";
  const lines = D["check_" + DG].split("\n");
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^\S+:(\d+):(\d+): (warning|error) (\w+): (.*)$/);
    if (!m) continue;
    const caret = (lines[i + 2] || "").match(/\^+/);
    const help = (lines[i + 3] || "").match(/^\s+help: (.*)$/);
    diags.push({ line: +m[1], col: +m[2], sev: m[3], code: m[4], msg: m[5], len: caret ? caret[0].length : 1, help: help && help[1] });
  }
  const src = D.sources[DG].split("\n");
  $("#diagCode").innerHTML = src.map((l, i) => {
    const d = diags.find((x) => x.line === i + 1);
    let body = hlLine(l);
    if (d) {
      const a = d.col - 1, b = a + d.len;
      body = hlLine(l.slice(0, a)) + `<span class="squig ${d.sev}" data-l="${d.line}">${hlInline(l.slice(a, b))}</span>` + hlInline(l.slice(b));
    }
    return `<span class="ln">${i + 1}</span>${body}`;
  }).join("\n");
  $("#diagList").innerHTML = diags.map((d) =>
    `<div class="dcard ${d.sev}" data-l="${d.line}"><span class="code-tag">${d.code}</span>${esc(d.msg)}
     <span class="pos">${DGF}:${d.line}:${d.col} · ${d.sev}</span>${d.help ? `<span class="help">help: ${esc(d.help)}</span>` : ""}</div>`).join("");
  $("#diag").addEventListener("enter", async () => {
    for (const d of diags) {
      await sleep(reduced ? 0 : 700);
      $$(`[data-l="${d.line}"]`, $("#diag")).forEach((el) => el.classList.add("on"));
    }
  });
}

/* ---------- formats gallery ---------- */
{
  const F = [["fran", "21-15-9"], ["cindy", "AMRAP"], ["emom", "EMOM"], ["intervals", "Every x"], ["tabata", "Tabata"],
    ["deathby", "Death by"], ["strength", t("Force 5x5", "Strength 5x5")], ["murph", "Buy-in · Cash-out"], [t("teams", "teams_en"), t("Équipes · 1.1", "Teams · 1.1")]];
  const tabs = $("#fmtTabs");
  tabs.innerHTML = F.map(([k, l]) => `<button role="tab" data-k="${k}">${esc(l)}</button>`).join("");
  const show = (k) => {
    $$("button", tabs).forEach((b) => b.setAttribute("aria-selected", b.dataset.k === k));
    $("#fmtName").textContent = k + ".wod";
    $("#fmtCode").innerHTML = hl(D.sources[k]);
    const b = $("#fmtBoard");
    b.innerHTML = boardHtml(D.boards[k]).split("\n").map((l, i) => `<span class="line-in" style="animation-delay:${i * 40}ms">${l || " "}</span>`).join("\n");
  };
  tabs.addEventListener("click", (e) => e.target.dataset.k && show(e.target.dataset.k));
  show("fran");
}

/* ---------- profile resolution ---------- */
{
  const st = { cat: "men", lvl: "rx", units: "kg", lang: LANG };
  Object.entries(st).forEach(([k, v]) => $$(`#profileCtl button[data-k="${k}"]`).forEach((b) => b.setAttribute("aria-pressed", b.dataset.v === v)));
  let prev = null;
  const render = () => {
    const txt = D.fran[`${st.cat}-${st.lvl}-${st.units}-${st.lang}`];
    const old = prev ? prev.split("\n") : [];
    $("#profileBoard").innerHTML = boardHtml(txt).split("\n").map((l, i) =>
      prev && old[i] !== txt.split("\n")[i] ? `<span class="flash">${l}</span>` : l).join("\n");
    setTimeout(() => $$("#profileBoard .flash").forEach((e) => (e.style.background = "transparent")), 60);
    prev = txt;
    $("#profileCmd").textContent = `wodc show fran.wod --category ${st.cat} --level ${st.lvl} --units ${st.units} --lang ${st.lang}`;
  };
  $("#profileCtl").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-k]");
    if (!b) return;
    st[b.dataset.k] = b.dataset.v;
    $$(`button[data-k="${b.dataset.k}"]`).forEach((x) => x.setAttribute("aria-pressed", x === b));
    render();
  });
  render();
}

/* ---------- session timeline, from `wodc timer` ---------- */
{
  const toS = (t) => t.replace("~", "").split(":").map(Number).reduce((a, b) => a * 60 + b, 0);
  const fmt = (s) => { s = Math.round(s); const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, x = s % 60;
    return (h ? h + ":" + String(m).padStart(2, "0") : String(m).padStart(2, "0")) + ":" + String(x).padStart(2, "0"); };
  const segs = D.timers.session.split("\n").map((l) => l.match(/^\s+(\d+:\d\d)\s+(\d+:\d\d~?)\s+(.*)$/)).filter(Boolean)
    .map((m) => ({ start: toS(m[1]), dur: toS(m[2]) }));
  const names = D.sources.session.split("\n").filter((l) => l.startsWith("## ")).map((l) => l.slice(3));
  const blocks = D[t("session_fr", "session_en")].split("\n\n").slice(1).filter((b) => !b.startsWith("Session"));
  const total = segs.reduce((a, s) => a + s.dur, 0);
  const colors = ["var(--green)", "var(--yellow)", "var(--red)", "var(--blue)"];
  const bar = $("#tlBar");
  segs.forEach((s, i) => {
    const el = document.createElement("div");
    el.className = "tl-seg";
    el.style.flex = s.dur; el.style.background = colors[i % 4];
    el.textContent = names[i] || "";
    el.addEventListener("click", () => { stop(); setT(s.start + 1); });
    bar.appendChild(el);
  });
  $("#tlTicks").innerHTML = segs.map((s) => `<span style="left:${(s.start / total) * 100}%">${fmt(s.start)}</span>`).join("") + `<span style="left:100%">${fmt(total)}</span>`;
  let cur = -1, raf = 0;
  const setT = (t) => {
    $("#tlHead").style.left = `calc(${(t / total) * 100}% - 1px)`;
    $("#tlClock").textContent = fmt(t);
    const i = Math.max(0, segs.findIndex((s) => t >= s.start && t < s.start + s.dur));
    if (i !== cur) {
      cur = i;
      $$(".tl-seg").forEach((e, k) => e.classList.toggle("on", k === i));
      $("#tlBoard").innerHTML = boardHtml(blocks[i] || "");
    }
  };
  const stop = () => cancelAnimationFrame(raf);
  const play = () => {
    stop();
    const t0 = performance.now(), D_MS = 18000;
    const step = (now) => { const p = Math.min(1, (now - t0) / D_MS); setT(p * (total - 1)); if (p < 1) raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
  };
  setT(0);
  $("#tlPlay").addEventListener("click", play);
  $("#session").addEventListener("enter", () => (reduced ? null : play()));
}

/* ---------- stats count-up ---------- */
$("#stats").closest("section").addEventListener("enter", () => {
  $$("#stats dt").forEach((dt) => {
    const n = +dt.dataset.n, t0 = performance.now();
    if (reduced || !n) { dt.textContent = n; return; }
    const step = (now) => { const p = Math.min(1, (now - t0) / 1400); dt.textContent = Math.round(n * (1 - (1 - p) ** 3)); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  });
});

/* ---------- playground: the real compiler, in Pyodide ---------- */
const WHEEL = "/py/wodcraft-1.1.1-py3-none-any.whl";
const FN = t("mon.wod", "my.wod");
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.2/full/";
{
  $("#try .editor-bar span").textContent = FN;
  const ta = $("#playSrc"), hlEl = $("#playHl"), out = $("#playOut");
  const sync = () => { hlEl.innerHTML = hl(ta.value) + "\n"; hlEl.scrollTop = ta.scrollTop; hlEl.scrollLeft = ta.scrollLeft; };
  const load = (k) => { ta.value = D.sources[{ bad: t("bad", "tuesday"), teams: t("teams", "teams_en") }[k] || k]; sync(); };
  ta.addEventListener("input", sync);
  ta.addEventListener("scroll", () => { hlEl.scrollTop = ta.scrollTop; hlEl.scrollLeft = ta.scrollLeft; });
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Tab") { e.preventDefault(); ta.setRangeText("  ", ta.selectionStart, ta.selectionEnd, "end"); sync(); }
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); run(); }
  });
  $("#playEx").addEventListener("change", (e) => { load(e.target.value); run(); });
  load("fran");

  let py = null;
  const boot = async () => {
    if (py) return py;
    out.innerHTML = '<span class="muted">' + t("Chargement de Python (Pyodide)…", "Loading Python (Pyodide)…") + "</span>";
    await new Promise((ok, ko) => { const s = document.createElement("script"); s.src = PYODIDE + "pyodide.js"; s.onload = ok; s.onerror = ko; document.head.appendChild(s); });
    const p = await loadPyodide({ indexURL: PYODIDE });
    out.innerHTML = '<span class="muted">' + t("Installation de wodcraft…", "Installing wodcraft…") + "</span>";
    await p.loadPackage("micropip");
    await p.runPythonAsync(`
import micropip
await micropip.install(${JSON.stringify(new URL(WHEEL, location.href).href)})
import io, os, contextlib
from wodcraft.cli import main as _wodc
os.makedirs("/w", exist_ok=True); os.chdir("/w")
def wodc(argv, source):
    with open("${FN}", "w") as f: f.write(source)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try: rc = _wodc(argv)
        except SystemExit as e: rc = e.code
    return buf.getvalue().rstrip("\\n"), rc or 0
`);
    py = p;
    return p;
  };
  const color = (t) => esc(t).replace(/^(.*(?:✓).*)$/gm, '<span class="ok">$1</span>')
    .replace(/(error E\d+)/g, '<span class="err">$1</span>').replace(/(warning W\d+)/g, '<span class="warn">$1</span>')
    .replace(/^(\s+help: .*)$/gm, '<span class="ok">$1</span>');
  let busy = false;
  async function run() {
    if (busy) return;
    busy = true; $("#playRun").disabled = true;
    try {
      const p = await boot();
      const f = p.globals.get("wodc");
      const call = (argv) => { const r = f(p.toPy(argv), ta.value); const v = r.toJs(); r.destroy(); return v; };
      const [chk, rc] = call(["check", FN]);
      let html = `<span class="muted">$ wodc check ${FN}</span>\n` + color(chk);
      if (!rc) {
        const argv = ["show", FN].concat($("#playFr").checked ? ["--lang", "fr"] : []);
        const [shw] = call(argv);
        html += `\n\n<span class="muted">$ wodc ${argv.join(" ")}</span>\n` + esc(shw);
      }
      out.innerHTML = html;
    } catch (e) {
      out.innerHTML = '<span class="err">' + t("Le compilateur n'a pas pu se charger : ", "The compiler could not load: ") + esc(String(e.message || e)) + "</span>";
    } finally { busy = false; $("#playRun").disabled = false; }
  }
  $("#playRun").addEventListener("click", run);
  $("#playFr").addEventListener("change", () => py && run());
}
