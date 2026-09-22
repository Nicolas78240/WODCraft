"""Semantic analysis: resolve, check and compile a parsed document into the JSON model."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from wodcraft import SPEC_VERSION
from wodcraft.catalog import Catalog, Equivalences, load_catalog, load_equivalences
from wodcraft.diagnostics import DiagnosticBag, Span
from wodcraft.semantics import measures
from wodcraft.semantics.estimate import estimate_workout
from wodcraft.syntax.ast import (
    Block,
    CommentLine,
    Document,
    Dual,
    MetaLine,
    MovementLine,
    RestLine,
    Statement,
    UseLine,
    WorkoutBody,
)
from wodcraft.syntax.units import format_clock

TIMED = {"for_time", "amrap", "emom", "every", "tabata", "death_by", "max_load"}
INTERVALS = {"emom", "every"}
UNTIMED = {"rounds", "ladder"}
ALLOWED_CHILDREN = {
    "rounds": TIMED | UNTIMED | {"buy_in", "cash_out"},
    "ladder": TIMED | UNTIMED,
    "emom": {"for_time", "amrap", "slot"} | UNTIMED,
    "every": {"for_time", "amrap", "slot"} | UNTIMED,
    "for_time": UNTIMED | {"buy_in", "cash_out"},
    "amrap": UNTIMED | {"buy_in", "cash_out"},
    "tabata": UNTIMED,
    "death_by": set(),
    "max_load": set(),
    "slot": UNTIMED,
    "buy_in": UNTIMED,
    "cash_out": UNTIMED,
    "root": TIMED | UNTIMED | {"buy_in", "cash_out"},
}
SCORE_TYPES = {"time", "rounds+reps", "rounds", "reps", "load", "distance", "calories", "none"}
SCORE_BY_FORMAT = {
    "for_time": "time",
    "amrap": "rounds+reps",
    "tabata": "reps",
    "death_by": "rounds+reps",
    "max_load": "load",
    "emom": "none",
    "every": "none",
    "rounds": "none",
    "ladder": "none",
}


@dataclass
class Options:
    catalog: Catalog = field(default_factory=lambda: load_catalog())
    equivalences: Equivalences = field(default_factory=lambda: load_equivalences())
    load_library: Callable[[str], tuple[dict, DiagnosticBag] | None] | None = None
    estimate: bool = True


class Compiler:
    def __init__(self, diags: DiagnosticBag, options: Options | None = None, file: str | None = None):
        self.diags = diags
        self.opt = options or Options()
        self.file = file
        self.units = "kg"
        self._units_declared = False
        self._movement_ids: list[str] = []
        self._used_workout: dict | None = None

    # ------------------------------------------------------------------ documents

    def document(self, doc: Document) -> dict:
        if doc.is_session:
            return self._session(doc)
        out = self._workout(doc.body or WorkoutBody(), doc.title)
        return out

    def _session(self, doc: Document) -> dict:
        meta = self._meta({}, doc.meta)
        if "units" in meta:
            self.units, self._units_declared = meta["units"], True
        sections = []
        for section in doc.sections or []:
            workout = self._workout(section.body, section.title)
            sections.append({"title": section.title, "workout": workout, "source": section.span.to_dict()})
        out: dict = {
            "wodcraft": SPEC_VERSION,
            "kind": "session",
            "title": doc.title,
            "sections": sections,
        }
        estimates = [s["workout"].get("estimate") for s in sections if s["workout"].get("estimate")]
        if estimates:
            out["estimate"] = {
                "min_s": round(sum(e["min_s"] for e in estimates)),
                "max_s": round(sum(e["max_s"] for e in estimates)),
            }
        for key in ("date", "time", "units", "tags", "notes", "stimulus"):
            if key in meta:
                out[key] = meta[key]
        return out

    # ------------------------------------------------------------------ workouts

    def _workout(self, body: WorkoutBody, title: str | None) -> dict:
        saved_units = self.units
        self._movement_ids = []
        saved_declared = self._units_declared
        meta = self._meta({}, [s for s in _walk(body.statements) if isinstance(s, MetaLine)])
        if "units" in meta:
            self.units, self._units_declared = meta["units"], True
        used = self._sole_use(body.statements)
        if used is not None:
            return self._adopt(used, title, meta)
        blocks = self._statements(body.statements, "root")
        blocks = [_normalize_block(b) for b in blocks]
        team = None
        for block in blocks:
            if block.get("teams"):
                team = {"size": block.pop("teams")}
        cap = meta.get("cap_s")
        if cap is not None and blocks:
            blocks[0].setdefault("cap_s", cap)
        out: dict = {
            "wodcraft": SPEC_VERSION,
            "kind": "workout",
            "title": title,
            "blocks": blocks,
            "score": self._score(blocks, meta),
        }
        if team:
            out["team"] = team
        levels = self._levels(body.levels)
        if levels:
            out["levels"] = levels
        rest = {k: v for k, v in meta.items() if k not in ("units", "cap_s", "score")}
        if rest:
            out["meta"] = rest
        if self.opt.estimate:
            estimate = estimate_workout(out, self.opt.catalog, self.diags, self.file)
            if estimate:
                out["estimate"] = estimate
        self.units, self._units_declared = saved_units, saved_declared
        return out

    def _sole_use(self, statements: list[Statement]) -> dict | None:
        """A body that is only a 'use' line adopts the whole referenced workout."""
        real = [s for s in statements if not isinstance(s, (MetaLine, CommentLine))]
        if len(real) != 1 or not isinstance(real[0], UseLine):
            return None
        blocks = self._use(real[0])
        return {"blocks": blocks, "used": real[0], "source": self._used_workout}

    def _adopt(self, used: dict, title: str | None, meta: dict) -> dict:
        source = used["source"] or {}
        out: dict = {
            "wodcraft": SPEC_VERSION,
            "kind": "workout",
            "title": title or source.get("title"),
            "blocks": used["blocks"],
            "score": source.get("score") or self._score(used["blocks"], meta),
        }
        for key in ("team", "levels", "estimate"):
            if source.get(key):
                out[key] = source[key]
        merged = {**(source.get("meta") or {}), **{k: v for k, v in meta.items() if k not in ("units", "cap_s", "score")}}
        if merged:
            out["meta"] = merged
        return out

    # ------------------------------------------------------------------ meta

    def _meta(self, out: dict, metas: list[MetaLine]) -> dict:
        # 'units' first: it decides how a load written without a unit is read
        for meta in sorted(metas, key=lambda m: m.key != "units"):
            key, value = meta.key, meta.value.strip()
            if key == "units":
                if value.lower() not in ("kg", "lb"):
                    self._err("E013", f"units must be 'kg' or 'lb', found {value!r}.", meta.value_span)
                else:
                    out["units"] = value.lower()
            elif key == "cap":
                seconds = _duration_from_text(value)
                if seconds is None:
                    self._err("E013", f"Invalid cap {value!r}.", meta.value_span, "e.g. 'cap: 12:00'")
                else:
                    out["cap_s"] = seconds
            elif key == "score":
                if value.lower() not in SCORE_TYPES:
                    self._err("E013", f"Unknown score {value!r}.", meta.value_span, "one of: " + ", ".join(sorted(SCORE_TYPES)))
                else:
                    out["score"] = value.lower()
            elif key == "vest":
                dual = _dual_from_text(value)
                if dual is None:
                    self._err("E013", f"Invalid vest load {value!r}.", meta.value_span, "e.g. 'vest: 20/14 lb'")
                else:
                    value_dual, unit = dual
                    out["vest"] = measures.load_to_json(value_dual, unit or out.get("units", self.units), self.opt.equivalences)
            elif key == "tags":
                out["tags"] = [t.strip() for t in value.split(",") if t.strip()]
            elif key in ("note", "stimulus"):
                out.setdefault("notes" if key == "note" else "stimulus", []).append(value)
            elif key in ("date", "time", "tiebreak"):
                out[key] = value
        return out

    # ------------------------------------------------------------------ statements

    def _statements(self, statements: list[Statement], parent: str) -> list[dict]:
        items: list[dict] = []
        for stmt in statements:
            if isinstance(stmt, (MetaLine, CommentLine)):
                continue
            if isinstance(stmt, RestLine):
                items.append({"type": "rest", "seconds": stmt.seconds, "source": stmt.span.to_dict()})
            elif isinstance(stmt, UseLine):
                for block in self._use(stmt):
                    if block.get("type") in ALLOWED_CHILDREN.get(parent, set()):
                        items.append(block)
                    else:
                        self._err(
                            "E015",
                            f"{stmt.path!r} is a {_human(block.get('type', ''))} workout and cannot go inside {_human(parent)}.",
                            stmt.span,
                            "put the 'use' line on its own, at the top level",
                        )
            elif isinstance(stmt, MovementLine):
                item = self._movement(stmt, parent)
                if item:
                    items.append(item)
            elif isinstance(stmt, Block):
                compiled = self._block(stmt, parent)
                if compiled:
                    items.append(compiled)
        return items

    def _block(self, block: Block, parent: str) -> dict | None:
        kind = block.kind
        if kind in ("rounds", "ladder") and block.for_time:
            kind = "for_time"
        if kind == "slot" and parent not in INTERVALS:
            self._err(
                "E014",
                "'Odd:', 'Even:' and 'Min N:' are only allowed inside an EMOM or an 'Every' block.",
                block.span,
                "indent it under the EMOM it belongs to",
            )
            return None
        allowed = ALLOWED_CHILDREN.get(parent, set())
        if kind not in allowed:
            self._err(
                "E015",
                f"A {_human(kind)} block is not allowed inside {_human(parent)}.",
                block.span,
                "indent it under an untimed block, e.g. '3 rounds'" if parent in TIMED else None,
            )
            return None
        out: dict = {"type": kind, "source": block.span.to_dict()}
        if block.kind in ("rounds", "ladder") and block.for_time:
            if block.rounds is not None:
                out["rounds"] = block.rounds
            if block.reps is not None:
                out["reps"] = block.reps
        for attr, key in (("duration_s", "duration_s"), ("interval_s", "interval_s"), ("rounds", "rounds"), ("cap_s", "cap_s")):
            value = getattr(block, attr)
            if value is not None and key not in out:
                out[key] = value
        if block.reps is not None and "reps" not in out:
            out["reps"] = block.reps
        if block.reps_open:
            out["reps_open"] = True
        if block.slot is not None:
            out["slot"] = block.slot
        if block.teams is not None:
            if parent != "root":
                self._err("E014", "'Teams of N' is only allowed on the main format line.", block.span)
            else:
                out["teams"] = block.teams
        self._check_block_args(kind, out, block.span)
        # inside a rep ladder, movements take their reps from the ladder
        out["items"] = self._statements(block.children, "ladder" if out.get("reps") else kind)
        if not out["items"] and kind not in ("max_load",):
            self._err("E016", f"Empty {_human(kind)} block.", block.span)
        return out

    def _check_block_args(self, kind: str, out: dict, span: Span) -> None:
        if kind == "amrap" and out.get("duration_s") is None:
            self._err("E034", "An AMRAP needs a duration.", span, "e.g. 'AMRAP 12'")
        if kind == "emom" and out.get("duration_s") is None:
            self._err("E034", "An EMOM needs a total duration.", span, "e.g. 'EMOM 10'")
        if kind == "every":
            if out.get("interval_s") is None:
                self._err("E034", "'Every' needs an interval.", span, "e.g. 'Every 3:00 x 5'")
            if out.get("rounds") is None:
                self._err("E034", "'Every' needs a number of intervals.", span, "e.g. 'Every 3:00 x 5'")
        for key, what in (("duration_s", "duration"), ("interval_s", "interval"), ("cap_s", "cap")):
            if out.get(key) is not None and out[key] <= 0:
                self._err("E035", f"The {what} must be greater than zero.", span)
        if kind == "tabata" and (out.get("rounds") or 0) < 1:
            self._err("E035", "A Tabata needs at least one round.", span)
        if kind == "slot" and isinstance(out.get("slot"), int) and out["slot"] < 1:
            self._err("E035", "Minutes are numbered from 1.", span)
        if kind in ("rounds", "for_time") and out.get("rounds") is not None and out["rounds"] < 1:
            self._err("E035", "The number of rounds must be at least 1.", span)
        for value in out.get("reps", []) or []:
            if value < 1:
                self._err("E035", "Rep ladder values must be at least 1.", span)
                break

    # ------------------------------------------------------------------ movements

    def _movement(self, mv: MovementLine, parent: str) -> dict | None:
        entry = self.opt.catalog.get(mv.name)
        if entry is None:
            hints = self.opt.catalog.suggest(mv.name)
            self._err(
                "E020",
                f"Unknown movement {mv.name!r}.",
                mv.name_span,
                ("did you mean " + " or ".join(repr(h) for h in hints) + "?") if hints else "add it to the movement catalog",
            )
            return None
        self._movement_ids.append(entry.id)
        out: dict = {"type": "movement", "movement": entry.id, "name": entry.name}
        quantity = mv.quantity
        params = list(mv.params)

        # a distance or calorie parameter written after the name is the quantity
        if quantity is None:
            for param in list(params):
                if param.kind in ("distance", "calories") and param.kind in entry.quantities:
                    from wodcraft.syntax.ast import Quantity

                    quantity = Quantity(param.kind, param.value, param.unit, param.span)
                    params.remove(param)
                    break

        if quantity is not None:
            kind = "reps" if quantity.kind == "max" and quantity.unit is None else quantity.kind
            if quantity.kind == "max":
                kind = {"cal": "calories", "m": "distance"}.get(quantity.unit or "", "reps")
            if kind not in entry.quantities:
                self._err(
                    "E033",
                    f"{entry.name} is not measured in {_quantity_word(kind)}.",
                    quantity.span,
                    "it is measured in " + " or ".join(_quantity_word(q) for q in entry.quantities),
                )
            elif quantity.kind == "max" or quantity.value is None:
                out["quantity"] = {"kind": "max", "of": kind}
            elif kind == "distance":
                out["quantity"] = dict(measures.distance_to_json(quantity.value, quantity.unit or "m"), kind="distance")
                self._check_distance(out["quantity"], entry, quantity.span)
            elif kind == "calories":
                out["quantity"] = {"kind": "calories", "cal": measures.amount(quantity.value)}
            elif kind == "time":
                out["quantity"] = {"kind": "time", "s": measures.amount(quantity.value)}
            else:
                out["quantity"] = {"kind": "reps", "reps": measures.amount(quantity.value)}
                if max(quantity.value.men, quantity.value.women) > 1000:
                    self._err("W105", "That is a lot of reps — is the number right?", quantity.span)
        elif mv.sets is None and parent not in ("ladder", "max_load", "death_by", "tabata") and entry.quantities:
            self._err("E030", f"{entry.name} needs a quantity.", mv.name_span, "e.g. '21 " + entry.name + "'")

        if mv.sets is not None:
            out["sets"] = {"reps": mv.sets.reps}

        for param in params:
            self._param(out, param, entry, mv)

        if mv.modifiers:
            out["modifiers"] = mv.modifiers
        out["source"] = mv.name_span.to_dict()
        return out

    def _param(self, out: dict, param, entry, mv: MovementLine) -> None:
        eq = self.opt.equivalences
        if param.kind in ("load", "percent", "rpe", "bw") and "load" not in entry.params:
            expected = "a height (in, cm)" if "height" in entry.params else "no load"
            self._err("E032", f"{entry.name} takes {expected}, not a load.", param.span)
            return
        if param.kind == "distance" and "height" in entry.params:
            # a target height written in feet ("10/9 ft") rather than in inches
            from wodcraft.syntax.ast import Param as _Param
            from wodcraft.syntax.units import M_PER

            centimetres = Dual(param.value.men * M_PER[param.unit or "m"] * 100, param.value.women * M_PER[param.unit or "m"] * 100, param.value.is_dual)
            param = _Param("height", centimetres, "cm", param.span)
        if param.kind in ("distance", "calories"):
            self._err(
                "E032",
                f"{entry.name} does not take a {param.kind} parameter.",
                param.span,
                "write it as the quantity, before the movement name",
            )
            return
        if param.kind == "height" and "height" not in entry.params:
            expected = "a load (kg, lb)" if "load" in entry.params else "no height"
            self._err("E032", f"{entry.name} takes {expected}, not a height.", param.span)
            return
        if param.kind == "load":
            unit = param.unit or self.units
            if param.unit is None and not self._units_declared:
                self._err(
                    "E031",
                    "Load without a unit.",
                    param.span,
                    "write 'kg' or 'lb', or add 'units: kg' at the top of the workout",
                )
                return
            if min(param.value.men, param.value.women) <= 0:
                self._err("E035", "A load must be greater than zero.", param.span)
                return
            out["load"] = measures.load_to_json(param.value, unit, eq)
            self._check_load(out["load"], entry, param.span)
        elif param.kind == "height":
            out["height"] = measures.height_to_json(param.value, param.unit or "cm", eq)
        elif param.kind == "percent":
            if param.value.men > 200 or param.value.women > 200:
                self._err("E035", "A percentage above 200 % is not plausible.", param.span)
                return
            percent: dict = {"value": measures.amount(param.value)}
            if param.of:
                ref = self.opt.catalog.get(param.of)
                if ref is None:
                    self._err("E020", f"Unknown movement {param.of!r}.", param.of_span or param.span)
                else:
                    percent["of"] = ref.id
            else:
                percent["of"] = entry.id
            out["percent"] = percent
        elif param.kind == "rpe":
            if not 1 <= param.value.men <= 10:
                self._err("E035", "RPE must be between 1 and 10.", param.span)
                return
            out["rpe"] = measures.amount(param.value)
        elif param.kind == "bw":
            out["bodyweight"] = measures.amount(param.value)

    def _check_load(self, load: dict, entry, span: Span) -> None:
        men = measures.pick(load["kg"], "men") if isinstance(load["kg"], dict) else load["kg"]
        women = measures.pick(load["kg"], "women") if isinstance(load["kg"], dict) else men
        if women > men:
            self._err("W101", "The women load is heavier than the men load — are the values reversed?", span)
        if entry.rx and entry.rx.get("unit", "kg") == "kg":
            reference = float(entry.rx.get("men", 0))
            if reference and men > reference * 3:
                self._err("W104", f"{men} kg is far above the usual load for {entry.name} ({reference:g} kg).", span)

    def _check_distance(self, quantity: dict, entry, span: Span) -> None:
        metres = quantity["m"]
        metres = min(metres.values()) if isinstance(metres, dict) else metres
        if quantity.get("unit") == "m" and metres < 10 and entry.family == "M":
            self._err(
                "W100",
                f"{measures.pick(quantity['written'], 'men') if isinstance(quantity['written'], dict) else quantity['written']} m of {entry.name} is very short.",
                span,
                "did you mean miles ('1 mi')?",
            )

    # ------------------------------------------------------------------ use, levels, score

    def _use(self, stmt: UseLine) -> list[dict]:
        if self.opt.load_library is None:
            self._err("E050", f"No library configured to resolve {stmt.path!r}.", stmt.span)
            return []
        loaded = self.opt.load_library(stmt.path)
        if loaded == "cycle":
            self._err("E051", f"Circular use of {stmt.path!r}.", stmt.span)
            return []
        if loaded is None or isinstance(loaded, str):
            self._err("E050", f"Workout {stmt.path!r} not found.", stmt.span, "e.g. 'use girls/fran'")
            return []
        workout, diags = loaded
        self.diags.extend(diags)
        self._used_workout = workout
        blocks = [dict(b) for b in workout.get("blocks", [])]
        for block in blocks:
            block["used"] = {"path": stmt.path, "title": workout.get("title")}
            block["source"] = stmt.span.to_dict()
        return blocks

    def _levels(self, levels: list[Block]) -> dict:
        out: dict = {}
        for level in levels:
            if level.kind in out:
                self._err("E041", f"Duplicate '{level.kind.title()}:' block.", level.span)
                continue
            operations: list[dict] = []
            for stmt in level.children:
                if isinstance(stmt, MetaLine):
                    if stmt.key not in ("vest", "cap", "note"):
                        self._err("E014", f"A level block cannot change {stmt.key!r}.", stmt.span, "only vest, cap and note can be adapted")
                        continue
                    if stmt.key == "vest" and stmt.value.strip().lower() in ("none", "no", "off"):
                        operations.append({"meta": {"vest": None}})
                    else:
                        operations.append({"meta": self._meta({}, [stmt])})
                    continue
                if not isinstance(stmt, MovementLine):
                    self._err("E014", "A level block only contains movement lines.", getattr(stmt, "span", level.span))
                    continue
                entry = self.opt.catalog.get(stmt.name)
                if entry is None:
                    self._err("E020", f"Unknown movement {stmt.name!r}.", stmt.name_span, None)
                    continue
                if entry.id not in self._movement_ids:
                    self._err(
                        "E040",
                        f"{entry.name} does not appear in the Rx work.",
                        stmt.name_span,
                        "a level block only adapts movements of the workout",
                    )
                    continue
                target = entry
                operation: dict = {"movement": entry.id}
                if stmt.replace_with:
                    replacement = self.opt.catalog.get(stmt.replace_with)
                    if replacement is None:
                        hints = self.opt.catalog.suggest(stmt.replace_with)
                        self._err(
                            "E020",
                            f"Unknown movement {stmt.replace_with!r}.",
                            stmt.replace_span or stmt.name_span,
                            ("did you mean " + " or ".join(repr(h) for h in hints) + "?") if hints else None,
                        )
                        continue
                    operation["replace_with"] = replacement.id
                    operation["name"] = replacement.name
                    target = replacement
                if stmt.selector_params:
                    selector: dict = {}
                    for param in stmt.selector_params:
                        self._param(selector, param, entry, stmt)
                    if "load" in selector:
                        operation["when"] = {"load": selector["load"]}
                    if "height" in selector:
                        operation.setdefault("when", {})["height"] = selector["height"]
                params: dict = {}
                for param in stmt.params:
                    self._param(params, param, target, stmt)
                if stmt.quantity is not None:
                    self._err("E014", "A level block does not change quantities.", stmt.quantity.span)
                operation.update(params)
                operation["source"] = stmt.name_span.to_dict()
                operations.append(operation)
            out[level.kind] = operations
        return out

    def _score(self, blocks: list[dict], meta: dict) -> dict:
        parts = [b for b in blocks if b.get("type") in TIMED]
        if len(parts) > 1 and "score" not in meta:
            return {
                "type": "multi",
                "parts": [{"type": SCORE_BY_FORMAT.get(b["type"], "none"), "block": i} for i, b in enumerate(blocks) if b in parts],
            }
        main = blocks[0] if blocks else None
        kind = main["type"] if main else "none"
        inferred = SCORE_BY_FORMAT.get(kind, "none")
        if kind in INTERVALS and main and _has_max(main):
            inferred = "reps"
        if kind in ("rounds", "ladder") and main and main.get("for_time"):
            inferred = "time"
        declared = meta.get("score")
        if declared is None:
            score: dict = {"type": inferred}
        elif declared != inferred and not _score_compatible(declared, kind, main):
            self._err(
                "E036",
                f"A {_human(kind)} workout cannot be scored by {declared!r}.",
                Span(main["source"]["line"], main["source"]["col"]) if main else Span(1, 1),
                f"this workout scores {inferred!r}",
            )
            score = {"type": inferred}
        else:
            score = {"type": declared}
        cap = meta.get("cap_s") or (main or {}).get("cap_s")
        if score["type"] == "time" and cap:
            score["capped"] = "reps"
        if meta.get("tiebreak"):
            score["tiebreak"] = meta["tiebreak"]
        return score

    # ------------------------------------------------------------------ helpers

    def _err(self, code: str, message: str, span: Span, suggestion: str | None = None) -> None:
        self.diags.add(code, message, Span(span.line, span.col, span.end_col, self.file), suggestion)


def _has_max(block: dict) -> bool:
    for item in block.get("items", []):
        if item.get("type") == "movement" and isinstance(item.get("quantity"), dict) and item["quantity"].get("kind") == "max":
            return True
        if _has_max(item):
            return True
    return False


def _score_compatible(declared: str, kind: str, main: dict | None) -> bool:
    """A declared score is accepted when the format can plausibly measure it."""
    if declared == "none":
        return True
    if kind in INTERVALS:
        return declared in ("reps", "rounds", "rounds+reps", "calories", "distance", "none")
    if kind in ("for_time", "rounds", "ladder"):
        return declared in ("time", "reps", "rounds") or (declared == "load" and kind != "for_time")
    if kind == "amrap":
        return declared in ("rounds+reps", "rounds", "reps", "calories", "distance")
    if kind == "max_load":
        return declared in ("load", "reps")
    if kind == "tabata":
        return declared in ("reps", "rounds", "calories", "distance")
    return True


def _quantity_word(kind: str) -> str:
    return {"reps": "reps", "distance": "distance", "calories": "calories", "time": "time"}.get(kind, kind)


def _human(kind: str) -> str:
    return {
        "for_time": "For time",
        "amrap": "AMRAP",
        "emom": "EMOM",
        "every": "Every",
        "tabata": "Tabata",
        "death_by": "Death by",
        "max_load": "Max load",
        "rounds": "rounds",
        "ladder": "rep ladder",
        "slot": "minute",
        "buy_in": "Buy-in",
        "cash_out": "Cash-out",
        "root": "the workout body",
    }.get(kind, kind)


def _walk(statements: list[Statement]):
    for stmt in statements:
        yield stmt
        if isinstance(stmt, Block):
            yield from _walk(stmt.children)


def _normalize_block(block: dict) -> dict:
    """Canonical form: 'For time' + a single untimed child merges into one block (SPEC §13)."""
    block["items"] = [_normalize_block(i) if i.get("type") in ALLOWED_CHILDREN else i for i in block.get("items", [])]
    if block["type"] in ("for_time", "amrap") and len(block["items"]) == 1:
        child = block["items"][0]
        if child.get("type") in ("rounds", "ladder") and not {"cap_s", "duration_s", "teams"} & set(child):
            merged = dict(block)
            for key in ("rounds", "reps", "reps_open"):
                if key in child and key not in merged:
                    merged[key] = child[key]
            merged["items"] = child["items"]
            return merged
    return block


def _duration_from_text(text: str) -> float | None:
    from wodcraft.diagnostics import DiagnosticBag as _Bag
    from wodcraft.syntax.lexer import Line, tokenize
    from wodcraft.syntax.lines import Cursor, LineError, parse_duration

    line = Line(1, 0, text, text)
    cur = Cursor(tokenize(line, _Bag(), None), line)
    try:
        value = parse_duration(cur, bare_minutes=True)
        cur.expect_end()
        return value
    except LineError:
        return None


def _dual_from_text(text: str):
    from wodcraft.diagnostics import DiagnosticBag as _Bag
    from wodcraft.syntax.lexer import Line, tokenize
    from wodcraft.syntax.lines import Cursor, LineError, parse_dual
    from wodcraft.syntax.units import unit_kind

    line = Line(1, 0, text, text)
    cur = Cursor(tokenize(line, _Bag(), None), line)
    try:
        value = parse_dual(cur)
    except LineError:
        return None
    unit = None
    tok = cur.peek()
    if tok is not None and tok.kind == "WORD":
        uk = unit_kind(tok.text)
        if uk and uk[0] == "load":
            unit = uk[1]
            cur.next()
    return (value, unit) if cur.done else None


def format_duration(seconds: float) -> str:
    return format_clock(seconds)
