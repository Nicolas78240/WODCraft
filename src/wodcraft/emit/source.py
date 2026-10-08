"""Canonical source form (``wodc fmt``): renders a parsed document back to .wod text."""

from __future__ import annotations

from wodcraft.semantics.compiler import SCORE_ALIASES
from wodcraft.syntax.ast import (
    LEVEL_LABELS,
    Block,
    CommentLine,
    Document,
    Dual,
    MetaLine,
    MovementLine,
    Param,
    Quantity,
    RestLine,
    Sets,
    SourceFile,
    Statement,
    UseLine,
    WorkoutBody,
)
from wodcraft.syntax.units import fmt_num, format_clock

INDENT = "  "


def format_source(source_file: SourceFile) -> str:
    chunks = [format_document(doc) for doc in source_file.documents]
    return "\n\n".join(c for c in chunks if c).rstrip() + "\n"


def format_document(doc: Document) -> str:
    lines: list[str] = []
    if doc.title:
        lines.append(f"# {doc.title}")
    if doc.is_session:
        lines += [_meta(m) for m in doc.meta]
        for section in doc.sections or []:
            lines.append("")
            lines.append(f"## {section.title}")
            lines += _body(section.body)
    elif doc.body is not None:
        lines += _body(doc.body)
    return "\n".join(lines)


def _body(body: WorkoutBody, depth: int = 0) -> list[str]:
    lines = _statements(body.statements, depth)
    for level in body.levels:
        lines.append("")
        lines += _statements([level], depth)
    return lines


def _statements(statements: list[Statement], depth: int) -> list[str]:
    out: list[str] = []
    for stmt in statements:
        out += _statement(stmt, depth)
    return out


def _statement(stmt: Statement, depth: int) -> list[str]:
    pad = INDENT * depth
    if isinstance(stmt, CommentLine):
        return [f"{pad}// {stmt.text}"]
    if isinstance(stmt, MetaLine):
        return [pad + _meta(stmt)]
    if isinstance(stmt, RestLine):
        return [f"{pad}Rest {_duration(stmt.seconds)}"]
    if isinstance(stmt, UseLine):
        return [f"{pad}use {stmt.path}"]
    if isinstance(stmt, MovementLine):
        return [pad + movement(stmt)]
    block = _merge(stmt)
    head = _block_head(block)
    lines = [pad + head] if head else []
    child_depth = depth + (1 if head else 0)
    if block.is_label and block.kind not in LEVEL_LABELS and len(block.children) == 1 and isinstance(block.children[0], MovementLine):
        return [f"{pad}{head} {movement(block.children[0])}"]
    lines += _statements(block.children, child_depth)
    return lines


def _merge(block: Block) -> Block:
    """'For time' + a single untimed child becomes one canonical line (SPEC §13). An AMRAP keeps its
    own line: '1-2-3 ...' alone would lose the clock."""
    if block.kind == "for_time" and len(block.children) == 1:
        child = block.children[0]
        blocked = child.cap_s or child.teams or child.there_and_back or block.there_and_back if isinstance(child, Block) else True
        if isinstance(child, Block) and child.kind in ("rounds", "ladder") and not blocked:
            merged = Block(
                child.kind,
                block.span,
                children=child.children,
                duration_s=block.duration_s,
                interval_s=block.interval_s,
                rounds=child.rounds,
                reps=child.reps,
                reps_open=child.reps_open,
                cap_s=block.cap_s,
                teams=block.teams,
                for_time=block.kind == "for_time",
            )
            return merged
    return block


def _block_head(block: Block) -> str:
    kind = block.kind
    parts: list[str] = []
    if kind == "for_time":
        parts.append("For time")
    elif kind == "amrap":
        parts.append("AMRAP" + (f" {_duration(block.duration_s)}" if block.duration_s else ""))
    elif kind == "emom":
        interval = int((block.interval_s or 60) // 60)
        name = "EMOM" if interval <= 1 else f"E{interval}MOM"
        parts.append(name + (f" {_duration(block.duration_s)}" if block.duration_s else ""))
    elif kind == "every":
        head = "Every"
        if block.interval_s:
            head += f" {format_clock(block.interval_s)}"
        if block.rounds is not None:
            head += f" x {block.rounds}"
        parts.append(head)
    elif kind == "tabata":
        parts.append("Tabata" + ("" if (block.rounds or 8) == 8 else f" {block.rounds}"))
    elif kind == "death_by":
        parts.append("Death by")
    elif kind == "max_load":
        parts.append("Max load")
        if block.attempts is not None:
            parts.append(f"{block.attempts} attempt{'' if block.attempts == 1 else 's'}")
    elif kind == "rounds":
        parts.append(f"{block.rounds} rounds" + (" for time" if block.for_time else ""))
    elif kind == "ladder":
        ladder = "-".join(str(r) for r in (block.reps or []))
        parts.append(ladder + (" ..." if block.reps_open else "") + (" for time" if block.for_time else ""))
    elif kind == "slot":
        return f"{'Odd' if block.slot == 'odd' else 'Even' if block.slot == 'even' else f'Min {block.slot}'}:"
    elif kind in ("buy_in", "cash_out"):
        return "Buy-in:" if kind == "buy_in" else "Cash-out:"
    else:  # level labels
        return f"{kind.title()}:"
    if block.teams:
        parts.append(f"teams of {block.teams}")
    if block.cap_s:
        parts.append(f"cap {format_clock(block.cap_s)}")
    if block.there_and_back:
        parts.append("there and back")
    return ", ".join(parts)


def movement(mv: MovementLine) -> str:
    parts: list[str] = []
    if mv.quantity is not None:
        parts.append(_quantity(mv.quantity))
    parts.append(mv.name)
    if mv.selector_params:
        parts += [_param(p) for p in mv.selector_params]
    if mv.replace_with:
        parts.append("->")
        if mv.factor is not None:
            parts.append(f"{fmt_num(mv.factor)}x")
        if mv.replace_quantity is not None:
            parts.append(_quantity(mv.replace_quantity))
        parts.append(mv.replace_with)
    if mv.sets is not None:
        parts.append(_sets(mv.sets))
    parts += [_param(p) for p in mv.params]
    text = " ".join(parts)
    if mv.modifiers:
        text += " (" + ", ".join(_modifier(m) for m in mv.modifiers) + ")"
    for alternative in mv.alternatives:
        text += " | " + movement(alternative)
    return text


def _modifier(modifier: str) -> str:
    from wodcraft.syntax.lines import MODIFIERS

    known = modifier in MODIFIERS or modifier == "per side" or modifier.startswith("rest ") or modifier.split(" ")[0] == "hold"
    return modifier if known else chr(34) + modifier + chr(34)


def _meta(meta: MetaLine) -> str:
    if meta.key == "score" and "," in meta.value:
        return f"score: {_score_value(meta.value)}"
    if meta.key == "score" and meta.value.strip().lower() in SCORE_ALIASES:
        return f"score: {SCORE_ALIASES[meta.value.strip().lower()]}"
    return f"{meta.key}: {meta.value}"


def _score_value(value: str) -> str:
    """'score: charge, total' is written back 'score: load, total' (1.2)."""
    head, *modifiers = [part.strip().lower() for part in value.split(",")]
    return ", ".join([SCORE_ALIASES.get(head, head), *modifiers])


def _dual(value: Dual) -> str:
    if value.is_dual:
        return f"{fmt_num(value.men)}/{fmt_num(value.women)}"
    return fmt_num(value.men)


def _quantity(quantity: Quantity) -> str:
    if quantity.kind == "max":
        return "max" + (f" {quantity.unit}" if quantity.unit else "")
    assert quantity.value is not None
    if quantity.kind == "reps":
        return _dual(quantity.value)
    if quantity.kind == "time":
        return _duration(quantity.value.men)
    return f"{_dual(quantity.value)} {quantity.unit}"


def _param(param: Param) -> str:
    if param.kind == "percent":
        return f"@ {_dual(param.value)}%" + (f" {param.of}" if param.of else "")
    if param.kind == "rpe":
        return f"@ RPE {fmt_num(param.value.men)}"
    if param.kind == "bw":
        return "bw" if param.value.men == 1 and not param.value.is_dual else f"@ {_dual(param.value)} bw"
    if param.unit is None:
        return _dual(param.value)
    return f"{_dual(param.value)} {param.unit}"


def _sets(sets: Sets) -> str:
    if sets.notation == "nxm" and sets.reps:
        return f"{len(sets.reps)}x{sets.reps[0]}"
    return "-".join(str(r) for r in sets.reps)


def _duration(seconds: float) -> str:
    if seconds and seconds < 60:
        return f"{fmt_num(seconds)} s"
    if seconds % 60 == 0 and seconds < 3600:
        return format_clock(seconds)
    return format_clock(seconds)
