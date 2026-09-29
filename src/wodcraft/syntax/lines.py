"""Parse one logical line into a statement (format, label, movement, rest, use or meta)."""

from __future__ import annotations

import re

from wodcraft.diagnostics import DiagnosticBag, Span
from wodcraft.syntax.ast import Block, CommentLine, Dual, MetaLine, MovementLine, Param, Quantity, RestLine, Sets, Statement, UseLine
from wodcraft.syntax.lexer import Line, Token, tokenize
from wodcraft.syntax.units import parse_clock, seconds, unit_kind

META_KEYS = {"cap", "score", "tiebreak", "units", "vest", "stimulus", "note", "tags", "date", "time"}
LABELS = {
    "buy-in": "buy_in",
    "buyin": "buy_in",
    "cash-out": "cash_out",
    "cashout": "cash_out",
    "odd": "odd",
    "even": "even",
    "scaled": "scaled",
    "intermediate": "intermediate",
    "foundations": "foundations",
}
MODIFIERS = {"sync", "split", "each", "alternating", "unbroken", "strict"}
_ENMOM = re.compile(r"^e(\d+)mom$", re.IGNORECASE)
_XN = re.compile(r"^x(\d+)$", re.IGNORECASE)


class LineError(Exception):
    def __init__(self, code: str, message: str, col: int, end_col: int = 0, suggestion: str | None = None):
        super().__init__(message)
        self.code, self.message, self.col, self.end_col, self.suggestion = code, message, col, end_col, suggestion


class Cursor:
    def __init__(self, tokens: list[Token], line: Line):
        self.toks = tokens
        self.i = 0
        self.line = line

    def peek(self, k: int = 0) -> Token | None:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def next(self) -> Token:
        tok = self.peek()
        if tok is None:
            raise LineError("E001", "Unexpected end of line.", self.end_col)
        self.i += 1
        return tok

    @property
    def done(self) -> bool:
        return self.i >= len(self.toks)

    @property
    def end_col(self) -> int:
        return self.line.indent + len(self.line.text) + 1

    def accept_word(self, *words: str) -> Token | None:
        tok = self.peek()
        if tok is not None and tok.is_word(*words):
            self.i += 1
            return tok
        return None

    def accept_sym(self, sym: str) -> Token | None:
        tok = self.peek()
        if tok is not None and tok.is_sym(sym):
            self.i += 1
            return tok
        return None

    def expect_end(self) -> None:
        tok = self.peek()
        if tok is not None:
            raise LineError("E001", f"Unexpected {tok.text!r}.", tok.col, tok.end_col)

    def span(self, tok: Token, file: str | None, end: Token | None = None) -> Span:
        return Span(self.line.number, tok.col, (end or tok).end_col, file)


# --------------------------------------------------------------------------- primitives


def _number(tok: Token) -> float:
    return float(tok.text)


def parse_dual(cur: Cursor) -> Dual:
    """NUM [/ NUM]"""
    first = cur.next()
    if first.kind != "NUM":
        raise LineError("E001", f"Expected a number, found {first.text!r}.", first.col, first.end_col)
    if cur.peek() is not None and cur.peek().is_sym("/"):  # type: ignore[union-attr]
        cur.next()
        second = cur.next()
        if second.kind != "NUM":
            raise LineError("E001", "Expected a number after '/'.", second.col, second.end_col)
        return Dual(_number(first), _number(second), True)
    return Dual.single(_number(first))


def parse_duration(cur: Cursor, bare_minutes: bool) -> float:
    """CLOCK | NUM unit | NUM (minutes, format lines only)."""
    tok = cur.next()
    if tok.kind == "CLOCK":
        return parse_clock(tok.text)
    if tok.kind == "NUM":
        unit_tok = cur.peek()
        uk = unit_kind(unit_tok.text) if unit_tok is not None and unit_tok.kind == "WORD" else None
        if uk and uk[0] == "time":
            cur.next()
            return seconds(_number(tok), uk[1])
        if uk and uk[1] == "m":
            raise LineError(
                "E001",
                "'m' means metres, not minutes.",
                unit_tok.col,  # type: ignore[union-attr]
                unit_tok.end_col,  # type: ignore[union-attr]
                f"write '{tok.text} min' or '{tok.text}:00'",
            )
        if bare_minutes:
            return _number(tok) * 60
        raise LineError("E001", f"Duration {tok.text!r} needs a unit.", tok.col, tok.end_col, f"write '{tok.text}:00' or '{tok.text} s'")
    raise LineError("E001", f"Expected a duration, found {tok.text!r}.", tok.col, tok.end_col)


def looks_like_duration(cur: Cursor) -> bool:
    tok = cur.peek()
    return tok is not None and tok.kind in ("CLOCK", "NUM")


# --------------------------------------------------------------------------- format lines

FORMAT_STARTERS = {"for", "amrap", "emom", "every", "tabata", "death", "max", "teams"}


def is_format_start(tokens: list[Token]) -> bool:
    if not tokens:
        return False
    t0 = tokens[0]
    if t0.kind == "WORD":
        w = t0.lower
        if w in ("for",):
            return len(tokens) > 1 and tokens[1].is_word("time")
        if w == "max":
            return len(tokens) > 1 and tokens[1].is_word("load")
        if w == "death":
            return len(tokens) > 1 and tokens[1].is_word("by")
        if w == "teams":
            return len(tokens) > 1 and tokens[1].is_word("of")
        return w in FORMAT_STARTERS or bool(_ENMOM.match(w))
    if t0.kind == "NUM":
        # "3 rounds …" or a rep ladder "21-15-9" (a ladder has at least one '-' and nothing else)
        if len(tokens) > 1 and tokens[1].is_word("rounds", "round", "rft"):
            return True
        if len(tokens) >= 3 and tokens[1].is_sym("-") and tokens[2].kind == "NUM":
            return True
    return False


TIMED_STARTERS = {"for", "amrap", "emom", "every", "tabata", "death", "max"}


def format_is_timed(tokens: list[Token]) -> bool:
    """A format line that puts the athlete on the clock (SPEC §4.1 rule 2)."""
    return any(tok.kind == "WORD" and (tok.lower in TIMED_STARTERS or _ENMOM.match(tok.text) or tok.lower == "rft") for tok in tokens)


def _split_segments(tokens: list[Token]) -> list[list[Token]]:
    segs: list[list[Token]] = [[]]
    for tok in tokens:
        if tok.is_sym(","):
            segs.append([])
        else:
            segs[-1].append(tok)
    return segs


def parse_format(line: Line, tokens: list[Token], file: str | None) -> Block:
    span = Span(line.number, line.col0, line.indent + len(line.text) + 1, file)
    block: Block | None = None
    options: list[list[Token]] = []
    for seg in _split_segments(tokens):
        if not seg:
            raise LineError("E001", "Empty element between commas.", span.col, span.end_col)
        if block is None and is_format_start(seg) and not seg[0].is_word("teams"):
            block = _parse_format_core(Cursor(seg, line), span)
        else:
            options.append(seg)
    if block is None:
        raise LineError("E010", "A format line needs a format (For time, AMRAP, EMOM, N rounds…).", span.col, span.end_col)
    for seg in options:
        cur = Cursor(seg, line)
        if cur.accept_word("cap"):
            block.cap_s = parse_duration(cur, bare_minutes=True)
        elif cur.accept_word("teams"):
            if not cur.accept_word("of"):
                raise LineError("E001", "Expected 'Teams of N'.", seg[0].col, seg[-1].end_col)
            n = cur.next()
            if n.kind != "NUM":
                raise LineError("E001", "Expected the team size.", n.col, n.end_col)
            block.teams = int(_number(n))
        elif cur.accept_word("for"):
            if not cur.accept_word("time"):
                raise LineError("E001", "Expected 'for time'.", seg[0].col, seg[-1].end_col)
            block.for_time = True
        else:
            raise LineError(
                "E001", f"Unknown option {seg[0].text!r}.", seg[0].col, seg[-1].end_col, "options are: cap, teams of N, for time"
            )
        cur.expect_end()
    return block


def _parse_format_core(cur: Cursor, span: Span) -> Block:
    tok = cur.next()
    w = tok.lower if tok.kind == "WORD" else ""
    if w == "for":
        cur.next()  # "time"
        block = Block("for_time", span, for_time=True)
    elif w == "amrap":
        block = Block("amrap", span)
        if looks_like_duration(cur):
            block.duration_s = parse_duration(cur, bare_minutes=True)
    elif w == "emom" or _ENMOM.match(w):
        m = _ENMOM.match(w)
        block = Block("emom", span, interval_s=60.0 * (int(m.group(1)) if m else 1))
        if looks_like_duration(cur):
            block.duration_s = parse_duration(cur, bare_minutes=True)
    elif w == "every":
        block = Block("every", span)
        if looks_like_duration(cur):
            block.interval_s = parse_duration(cur, bare_minutes=True)
        x = cur.peek()
        if x is not None and x.kind == "WORD" and _XN.match(x.text):
            cur.next()
            block.rounds = int(_XN.match(x.text).group(1))  # type: ignore[union-attr]
        elif cur.accept_word("x", "for"):
            n = cur.next()
            if n.kind != "NUM":
                raise LineError("E001", "Expected the number of intervals.", n.col, n.end_col)
            block.rounds = int(_number(n))
            cur.accept_word("rounds", "intervals", "sets")
    elif w == "tabata":
        block = Block("tabata", span, rounds=8, interval_s=30.0)
        rounds_tok = cur.peek()
        if rounds_tok is not None and rounds_tok.kind == "NUM":
            cur.next()
            block.rounds = int(_number(rounds_tok))
    elif w == "death":
        cur.next()  # "by"
        block = Block("death_by", span, interval_s=60.0)
        if not cur.done:  # "Death by Burpee" — the rest of the line is the movement
            rest = cur.toks[cur.i :]
            cur.i = len(cur.toks)
            block.children.append(parse_movement(cur.line, rest, span.file))
    elif w == "max":
        cur.next()  # "load"
        block = Block("max_load", span)
    elif tok.kind == "NUM" and cur.peek() is not None and cur.peek().is_word("rounds", "round", "rft"):  # type: ignore[union-attr]
        word = cur.next()
        block = Block("rounds", span, rounds=int(_number(tok)))
        if word.is_word("rft"):
            block.for_time = True
    elif tok.kind == "NUM":
        reps = [int(_number(tok))]
        while cur.accept_sym("-"):
            n = cur.next()
            if n.kind != "NUM":
                raise LineError("E001", "Expected a number in the rep ladder.", n.col, n.end_col)
            reps.append(int(_number(n)))
        block = Block("ladder", span, reps=reps)
        nxt = cur.peek()
        if nxt is not None and nxt.kind == "ELLIPSIS":
            cur.next()
            if len(reps) < 2 or len({reps[i + 1] - reps[i] for i in range(len(reps) - 1)}) != 1:
                raise LineError("E035", "An open ladder needs a constant step, e.g. '3-6-9 ...'.", span.col, span.end_col)
            block.reps_open = True
    else:
        raise LineError("E010", f"Unknown format {tok.text!r}.", tok.col, tok.end_col)
    if cur.accept_word("for"):
        if not cur.accept_word("time"):
            raise LineError("E001", "Expected 'for time'.", span.col, span.end_col)
        block.for_time = True
    cur.expect_end()
    return block


# --------------------------------------------------------------------------- movement lines

_NAME_STOP_WORDS = {"bw", "rpe", "max"}


def _parse_quantity(cur: Cursor, file: str | None) -> Quantity | None:
    tok = cur.peek()
    if tok is None:
        return None
    if tok.kind == "CLOCK":
        cur.next()
        return Quantity("time", Dual.single(parse_clock(tok.text)), "s", cur.span(tok, file))
    if tok.is_word("max"):
        cur.next()
        unit = None
        nxt = cur.peek()
        uk = unit_kind(nxt.text) if nxt is not None and nxt.kind == "WORD" else None
        if uk and uk[0] in ("calories", "distance"):
            cur.next()
            unit = uk[1]
        return Quantity("max", None, unit, cur.span(tok, file))
    if tok.kind != "NUM":
        return None
    start = cur.i
    value = parse_dual(cur)
    unit_tok = cur.peek()
    uk = unit_kind(unit_tok.text) if unit_tok is not None and unit_tok.kind == "WORD" else None
    end_tok = cur.toks[cur.i - 1]
    if uk and uk[0] in ("distance", "calories", "time"):
        cur.next()
        kind = uk[0]
        unit = uk[1]
        if kind == "time":
            value = Dual(seconds(value.men, unit), seconds(value.women, unit), value.is_dual)
            unit = "s"
        return Quantity(kind, value, unit, cur.span(cur.toks[start], file, unit_tok))
    if uk and uk[0] in ("load", "height"):
        raise LineError(
            "E030",
            f"A movement line starts with its quantity; {cur.toks[start].text} {unit_tok.text} is a {uk[0]}.",  # type: ignore[union-attr]
            cur.toks[start].col,
            unit_tok.end_col,  # type: ignore[union-attr]
            "write the quantity first, e.g. '21 Thruster 43/30 kg'",
        )
    if value.men != int(value.men) or value.women != int(value.women):
        raise LineError("E035", "A number of reps must be a whole number.", cur.toks[start].col, end_tok.end_col)
    return Quantity("reps", value, None, cur.span(cur.toks[start], file, end_tok))


def _parse_name(cur: Cursor) -> tuple[str, int, int]:
    words: list[Token] = []
    while not cur.done:
        tok = cur.peek()
        assert tok is not None
        if tok.kind != "WORD" or tok.lower in _NAME_STOP_WORDS:
            break
        if words and unit_kind(tok.text) and cur.peek(-1) is not None and cur.peek(-1).kind == "NUM":  # type: ignore[union-attr]
            break
        words.append(cur.next())
    if not words:
        tok = cur.peek()
        raise LineError("E001", "Expected a movement name.", tok.col if tok else cur.end_col, tok.end_col if tok else 0)
    return " ".join(w.text for w in words), words[0].col, words[-1].end_col


def _parse_sets(cur: Cursor, file: str | None) -> Sets | None:
    tok = cur.peek()
    if tok is None:
        return None
    if tok.kind == "SETS":
        cur.next()
        n, m = (int(x) for x in tok.text.split("x"))
        return Sets([m] * n, cur.span(tok, file), "nxm")
    nxt = cur.peek(1)
    if tok.kind == "NUM" and nxt is not None and nxt.is_sym("-"):
        start = cur.next()
        reps = [int(_number(start))]
        last: Token = start
        while cur.accept_sym("-"):
            last = cur.next()
            if last.kind != "NUM":
                raise LineError("E001", "Expected a number in the set scheme.", last.col, last.end_col)
            reps.append(int(_number(last)))
        return Sets(reps, cur.span(start, file, last), "ladder")
    return None


def _parse_param(cur: Cursor, file: str | None) -> Param:
    at = cur.accept_sym("@")
    tok = cur.peek()
    if tok is None:
        raise LineError("E001", "Expected a load after '@'.", cur.end_col)
    first = at or tok
    if tok.is_word("bw"):
        cur.next()
        return Param("bw", Dual.single(1.0), None, cur.span(first, file, tok))
    if tok.is_word("rpe"):
        cur.next()
        val = cur.next()
        if val.kind != "NUM":
            raise LineError("E001", "Expected a number after RPE.", val.col, val.end_col)
        return Param("rpe", Dual.single(_number(val)), None, cur.span(first, file, val))
    value = parse_dual(cur)
    last = cur.toks[cur.i - 1]
    if cur.accept_sym("%"):
        last = cur.toks[cur.i - 1]
        param = Param("percent", value, "%", cur.span(first, file, last))
        cur.accept_word("of")
        nxt, after = cur.peek(), cur.peek(1)
        if nxt is not None and nxt.kind == "NUM" and nxt.text == "1" and after is not None and after.is_word("rm"):
            cur.next()
            cur.next()
            cur.accept_word("of")
        cur.accept_word("1rm")
        if not cur.done and cur.peek().kind == "WORD":  # type: ignore[union-attr]
            name, c0, c1 = _parse_name(cur)
            param.of, param.of_span = name, Span(cur.line.number, c0, c1, file)
        return param
    unit_tok = cur.peek()
    if unit_tok is not None and unit_tok.is_word("bw"):
        cur.next()
        return Param("bw", value, None, cur.span(first, file, unit_tok))
    uk = unit_kind(unit_tok.text) if unit_tok is not None and unit_tok.kind == "WORD" else None
    if uk is None or unit_tok is None:
        return Param("load", value, None, cur.span(first, file, last))
    cur.next()
    if uk[0] == "time":
        raise LineError(
            "E032", "A duration cannot follow the movement name.", first.col, unit_tok.end_col, "put the duration first: '30 s Plank'"
        )
    return Param(uk[0], value, uk[1], cur.span(first, file, unit_tok))


def _parse_modifiers(cur: Cursor) -> list[str]:
    mods: list[str] = []
    open_tok = cur.next()  # "("
    current: list[Token] = []
    while True:
        tok = cur.peek()
        if tok is None:
            raise LineError("E001", "Missing ')'.", open_tok.col, cur.end_col)
        cur.next()
        if tok.is_sym(")") or tok.is_sym(","):
            if not current:
                raise LineError("E001", "Empty modifier.", tok.col, tok.end_col)
            mods.append(_modifier_text(current))
            current = []
            if tok.is_sym(")"):
                return mods
        else:
            current.append(tok)


def _modifier_text(toks: list[Token]) -> str:
    if len(toks) == 1 and toks[0].kind == "STRING":
        return toks[0].text.strip('"')
    words = [t.text for t in toks]
    text = " ".join(words).lower()
    if text in MODIFIERS or text in ("per side",):
        return text
    if toks[0].is_word("rest"):
        return "rest " + " ".join(words[1:])
    if toks[0].is_word("hold"):
        rest = toks[1:]
        timed = len(rest) == 2 and rest[0].kind == "NUM" and (unit_kind(rest[1].text) or ("", ""))[0] == "time"
        if rest and not timed and not (len(rest) == 1 and rest[0].kind == "CLOCK"):
            raise LineError("E001", "'hold' takes a duration.", rest[0].col, rest[-1].end_col, "e.g. '(hold 10 s)' or '(hold 0:30)'")
        return " ".join(["hold", *words[1:]])
    raise LineError(
        "E001",
        f"Unknown modifier {' '.join(words)!r}.",
        toks[0].col,
        toks[-1].end_col,
        'known modifiers: sync, split, each, alternating, unbroken, strict, per side, rest DURATION, hold [DURATION] — or free text in quotes: ("tempo 3-1-1")',
    )


def parse_movement(line: Line, tokens: list[Token], file: str | None, allow_replace: bool = False) -> MovementLine:
    """A movement line, or several separated by '|': the athlete does one of them (SPEC §7.6)."""
    parts: list[list[Token]] = [[]]
    for tok in tokens:
        if tok.is_sym("|"):
            if allow_replace:
                raise LineError("E014", "An alternative ('|') is not allowed in a level block.", tok.col, tok.end_col)
            if not parts[-1]:
                raise LineError("E001", "Expected a movement before '|'.", tok.col, tok.end_col)
            parts.append([])
        else:
            parts[-1].append(tok)
    if not parts[-1]:
        raise LineError("E001", "Expected a movement after '|'.", tokens[-1].col, tokens[-1].end_col)
    mv = _parse_one_movement(line, parts[0], file, allow_replace)
    mv.alternatives = [_parse_one_movement(line, part, file) for part in parts[1:]]
    return mv


def _parse_one_movement(line: Line, tokens: list[Token], file: str | None, allow_replace: bool = False) -> MovementLine:
    cur = Cursor(tokens, line)
    quantity = _parse_quantity(cur, file)
    name, c0, c1 = _parse_name(cur)
    mv = MovementLine(name, Span(line.number, c0, c1, file), Span(line.number, tokens[0].col, cur.end_col, file), quantity)
    mv.sets = _parse_sets(cur, file)
    if allow_replace:
        # a level line may carry selector parameters before the arrow: "Deadlift 225 lb -> Deadlift 155 lb"
        while not cur.done and (cur.peek().is_sym("@") or cur.peek().kind == "NUM" or cur.peek().is_word("bw", "rpe")):  # type: ignore[union-attr]
            mv.selector_params.append(_parse_param(cur, file))
    if cur.peek() is not None and cur.peek().kind == "ARROW":  # type: ignore[union-attr]
        arrow = cur.next()
        if not allow_replace:
            raise LineError("E014", "'->' is only allowed in a level block (Scaled:, …).", arrow.col, arrow.end_col)
        rname, r0, r1 = _parse_name(cur)
        mv.replace_with, mv.replace_span = rname, Span(line.number, r0, r1, file)
        mv.sets = _parse_sets(cur, file) or mv.sets
    else:
        mv.params, mv.selector_params = mv.selector_params, []
    while not cur.done:
        tok = cur.peek()
        assert tok is not None
        if tok.is_sym("("):
            mv.modifiers.extend(_parse_modifiers(cur))
            continue
        if tok.is_sym("@") or tok.kind == "NUM" or tok.is_word("bw", "rpe"):
            mv.params.append(_parse_param(cur, file))
            continue
        if tok.is_sym(","):
            cur.next()
            continue
        raise LineError("E001", f"Unexpected {tok.text!r} in a movement line.", tok.col, tok.end_col)
    return mv


# --------------------------------------------------------------------------- dispatch

_LABEL_RE = re.compile(r"^([A-Za-zÀ-ÿ][\w'’\-]*(?: \d+)?)\s*:(.*)$", re.DOTALL)


def _meta_or_label(line: Line, tokens: list[Token], file: str | None) -> tuple[str, str, int] | None:
    """Return (kind, name, colon_index) where kind is 'meta' or 'label'."""
    if not tokens or tokens[0].kind != "WORD":
        return None
    idx = 1
    name = tokens[0].lower
    if tokens[0].is_word("min") and len(tokens) > 2 and tokens[1].kind == "NUM" and tokens[2].is_sym(":"):
        return ("label", f"min {int(float(tokens[1].text))}", 2)
    if len(tokens) > idx and tokens[idx].is_sym(":"):
        if name in META_KEYS:
            return ("meta", name, idx)
        if name in LABELS:
            return ("label", LABELS[name], idx)
        return ("unknown", name, idx)
    return None


def parse_line(line: Line, diags: DiagnosticBag, file: str | None, allow_replace: bool = False) -> Statement | None:
    """Parse a non-heading line. Returns None when the line is invalid (a diagnostic was emitted)."""
    if not line.text:
        return CommentLine(line.comment or "", Span(line.number, line.col0, file=file)) if line.comment else None
    scratch = DiagnosticBag()
    tokens = tokenize(line, scratch, file)
    # meta values and library paths are free text: they must not go through the lexer's expectations
    free_text = bool(tokens) and (_meta_or_label(line, tokens, file) == ("meta", tokens[0].lower, 1) or tokens[0].is_word("use"))
    if not free_text:
        diags.extend(scratch)
    if not tokens:
        return None
    span = Span(line.number, line.col0, line.indent + len(line.text) + 1, file)
    try:
        kind_name = _meta_or_label(line, tokens, file)
        if kind_name is not None:
            kind, name, colon = kind_name
            rest = tokens[colon + 1 :]
            if kind == "unknown":
                if tokens[0].text[0].islower():
                    raise LineError(
                        "E012",
                        f"Unknown meta key {name!r}.",
                        tokens[0].col,
                        tokens[colon].end_col,
                        "known keys: " + ", ".join(sorted(META_KEYS)),
                    )
                raise LineError(
                    "E011",
                    f"Unknown label {tokens[0].text!r}.",
                    tokens[0].col,
                    tokens[colon].end_col,
                    "known labels: Buy-in, Cash-out, Odd, Even, Min N, Scaled, Intermediate, Foundations",
                )
            if kind == "meta":
                raw = line.text.split(":", 1)[1].strip()
                value_col = line.indent + line.text.index(":") + 2
                return MetaLine(name, raw, span, Span(line.number, value_col, span.end_col, file))
            block = Block(name.split(" ")[0] if name.startswith("min ") else name, span, is_label=True)
            if name.startswith("min "):
                block.slot = int(name.split(" ")[1])
                block.kind = "slot"
            elif name in ("odd", "even"):
                block.slot = name
                block.kind = "slot"
            if rest:
                if rest[0].is_word("rest"):
                    inline = Cursor(rest, line)
                    inline.next()
                    block.children.append(RestLine(parse_duration(inline, bare_minutes=False), span))
                    inline.expect_end()
                else:
                    block.children.append(parse_movement(line, rest, file, allow_replace))
            return block
        if tokens[0].is_word("rest"):
            cur = Cursor(tokens, line)
            cur.next()
            duration = parse_duration(cur, bare_minutes=False)
            cur.expect_end()
            return RestLine(duration, span)
        if tokens[0].is_word("use"):
            path = line.text.split(None, 1)
            if len(path) < 2 or not path[1].strip():
                raise LineError("E001", "Expected a library path after 'use'.", tokens[0].col, tokens[0].end_col, "e.g. 'use girls/fran'")
            return UseLine(path[1].strip(), span)
        if is_format_start(tokens):
            return parse_format(line, tokens, file)
        return parse_movement(line, tokens, file, allow_replace)
    except LineError as err:
        diags.add(err.code, err.message, Span(line.number, err.col, err.end_col, file), err.suggestion)
        return None
