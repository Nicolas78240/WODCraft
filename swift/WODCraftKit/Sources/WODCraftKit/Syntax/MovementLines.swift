/// Movement lines and the dispatch that turns any logical line into a statement (SPEC §7).
import Foundation

private let nameStopWords: Set<String> = ["bw", "rpe", "max"]

private func number(_ tok: Token) -> Double {
    Double(tok.text) ?? 0
}

func parseQuantity(_ cur: Cursor, _ file: String?) throws -> QuantityNode? {
    guard let tok = cur.peek() else { return nil }
    if tok.kind == .clock {
        _ = try cur.next()
        let value = Dual.single(Units.parseClock(tok.text))
        return QuantityNode("time", value, "s", cur.span(tok, file))
    }
    if tok.isWord("max") {
        _ = try cur.next()
        var unit: String?
        if let ahead = cur.peek(), ahead.kind == .word, let kind = Units.unitKind(ahead.text),
           kind.kind == "calories" || kind.kind == "distance" {
            _ = try cur.next()
            unit = kind.unit
        }
        return QuantityNode("max", nil, unit, cur.span(tok, file))
    }
    guard tok.kind == .number else { return nil }
    let start: Int = cur.i
    var value = try parseDual(cur)
    let unitTok: Token? = cur.peek()
    var unitKind: (kind: String, unit: String)?
    if let unitTok, unitTok.kind == .word {
        unitKind = Units.unitKind(unitTok.text)
    }
    let endTok: Token = cur.toks[cur.i - 1]
    if let unitKind, let unitTok, ["distance", "calories", "time"].contains(unitKind.kind) {
        _ = try cur.next()
        var kind: String = unitKind.kind
        var unit: String = unitKind.unit
        if kind == "time" {
            value = Dual(Units.seconds(value.men, unit), Units.seconds(value.women, unit), value.isDual)
            unit = "s"
        }
        kind = unitKind.kind
        return QuantityNode(kind, value, unit, cur.span(cur.toks[start], file, unitTok))
    }
    if let unitKind, let unitTok, unitKind.kind == "load" || unitKind.kind == "height" {
        throw LineError(
            "E030",
            "A movement line starts with its quantity; \(cur.toks[start].text) \(unitTok.text) is a \(unitKind.kind).",
            cur.toks[start].col,
            unitTok.endCol,
            "write the quantity first, e.g. '21 Thruster 43/30 kg'"
        )
    }
    if value.men != value.men.rounded(.towardZero) || value.women != value.women.rounded(.towardZero) {
        throw LineError("E035", "A number of reps must be a whole number.", cur.toks[start].col, endTok.endCol)
    }
    return QuantityNode("reps", value, nil, cur.span(cur.toks[start], file, endTok))
}

func parseName(_ cur: Cursor) throws -> (name: String, startCol: Int, endCol: Int) {
    var words: [Token] = []
    while !cur.done {
        guard let tok = cur.peek() else { break }
        if tok.kind != .word || nameStopWords.contains(tok.lower) {
            break
        }
        if !words.isEmpty, Units.unitKind(tok.text) != nil, let previous = cur.peek(-1), previous.kind == .number {
            break
        }
        words.append(try cur.next())
    }
    if words.isEmpty {
        let tok: Token? = cur.peek()
        throw LineError("E001", "Expected a movement name.", tok?.col ?? cur.endCol, tok?.endCol ?? 0)
    }
    let name: String = words.map(\.text).joined(separator: " ")
    return (name, words[0].col, words[words.count - 1].endCol)
}

func parseSets(_ cur: Cursor, _ file: String?) throws -> SetsNode? {
    guard let tok = cur.peek() else { return nil }
    if tok.kind == .sets {
        _ = try cur.next()
        let parts: [Substring] = tok.text.split(separator: "x")
        let sets: Int = Int(parts[0]) ?? 0
        let reps: Int = Int(parts[1]) ?? 0
        return SetsNode(Array(repeating: reps, count: sets), cur.span(tok, file), "nxm")
    }
    guard let ahead = cur.peek(1), tok.kind == .number, ahead.isSymbol("-") else { return nil }
    let start = try cur.next()
    var reps: [Int] = [Int(number(start))]
    var last: Token = start
    while cur.acceptSymbol("-") != nil {
        last = try cur.next()
        guard last.kind == .number else {
            throw LineError("E001", "Expected a number in the set scheme.", last.col, last.endCol)
        }
        reps.append(Int(number(last)))
    }
    return SetsNode(reps, cur.span(start, file, last), "ladder")
}

func parseParam(_ cur: Cursor, _ file: String?) throws -> ParamNode {
    let at: Token? = cur.acceptSymbol("@")
    guard let tok = cur.peek() else {
        throw LineError("E001", "Expected a load after '@'.", cur.endCol)
    }
    let first: Token = at ?? tok
    if tok.isWord("bw") {
        _ = try cur.next()
        return ParamNode("bw", Dual.single(1.0), nil, cur.span(first, file, tok))
    }
    if tok.isWord("rpe") {
        _ = try cur.next()
        let value = try cur.next()
        guard value.kind == .number else {
            throw LineError("E001", "Expected a number after RPE.", value.col, value.endCol)
        }
        return ParamNode("rpe", Dual.single(number(value)), nil, cur.span(first, file, value))
    }
    let value = try parseDual(cur)
    var last: Token = cur.toks[cur.i - 1]
    if cur.acceptSymbol("%") != nil {
        last = cur.toks[cur.i - 1]
        let param = ParamNode("percent", value, "%", cur.span(first, file, last))
        _ = cur.acceptWord("of")
        let ahead: Token? = cur.peek()
        let after: Token? = cur.peek(1)
        if let ahead, let after, ahead.kind == .number, ahead.text == "1", after.isWord("rm") {
            _ = try cur.next()
            _ = try cur.next()
            _ = cur.acceptWord("of")
        }
        _ = cur.acceptWord("1rm")
        if let next = cur.peek(), next.kind == .word {
            let named = try parseName(cur)
            param.of = named.name
            param.ofSpan = Span(cur.line.number, named.startCol, named.endCol, file)
        }
        return param
    }
    let unitTok: Token? = cur.peek()
    if let unitTok, unitTok.isWord("bw") {
        _ = try cur.next()
        return ParamNode("bw", value, nil, cur.span(first, file, unitTok))
    }
    var unitKind: (kind: String, unit: String)?
    if let unitTok, unitTok.kind == .word {
        unitKind = Units.unitKind(unitTok.text)
    }
    guard let unitKind, let unitTok else {
        return ParamNode("load", value, nil, cur.span(first, file, last))
    }
    _ = try cur.next()
    if unitKind.kind == "time" {
        throw LineError(
            "E032",
            "A duration cannot follow the movement name.",
            first.col,
            unitTok.endCol,
            "put the duration first: '30 s Plank'"
        )
    }
    return ParamNode(unitKind.kind, value, unitKind.unit, cur.span(first, file, unitTok))
}

func parseModifiers(_ cur: Cursor) throws -> [String] {
    var mods: [String] = []
    let openTok = try cur.next() // "("
    var current: [Token] = []
    while true {
        guard let tok = cur.peek() else {
            throw LineError("E001", "Missing ')'.", openTok.col, cur.endCol)
        }
        _ = try cur.next()
        if tok.isSymbol(")") || tok.isSymbol(",") {
            if current.isEmpty {
                throw LineError("E001", "Empty modifier.", tok.col, tok.endCol)
            }
            mods.append(try modifierText(current))
            current = []
            if tok.isSymbol(")") {
                return mods
            }
        } else {
            current.append(tok)
        }
    }
}

private func modifierText(_ toks: [Token]) throws -> String {
    if toks.count == 1, toks[0].kind == .string {
        return String(toks[0].text.dropFirst().dropLast())
    }
    let words: [String] = toks.map(\.text)
    let text: String = words.joined(separator: " ").lowercased()
    if modifierWords.contains(text) || text == "per side" {
        return text
    }
    if toks[0].isWord("rest") {
        return "rest " + words.dropFirst().joined(separator: " ")
    }
    if toks[0].isWord("hold") {
        let rest: [Token] = Array(toks.dropFirst())
        var timed: Bool = rest.count == 1 && rest[0].kind == .clock
        if rest.count == 2, rest[0].kind == .number, Units.unitKind(rest[1].text)?.kind == "time" {
            timed = true
        }
        if !rest.isEmpty, !timed {
            throw LineError(
                "E001",
                "'hold' takes a duration.",
                rest[0].col,
                rest[rest.count - 1].endCol,
                "e.g. '(hold 10 s)' or '(hold 0:30)'"
            )
        }
        return (["hold"] + words.dropFirst()).joined(separator: " ")
    }
    throw LineError(
        "E001",
        "Unknown modifier '\(words.joined(separator: " "))'.",
        toks[0].col,
        toks[toks.count - 1].endCol,
        "known modifiers: sync, split, each, alternating, unbroken, strict, per side, rest DURATION, hold [DURATION]"
            + " — or free text in quotes: (\"tempo 3-1-1\")"
    )
}

/// A movement line, or several separated by `|`: the athlete does one of them (SPEC §7.6).
func parseMovement(_ line: SourceLine, _ tokens: [Token], _ file: String?, _ allowReplace: Bool = false) throws -> MovementLine {
    var parts: [[Token]] = [[]]
    for tok in tokens {
        if tok.isSymbol("|") {
            if allowReplace {
                throw LineError("E014", "An alternative ('|') is not allowed in a level block.", tok.col, tok.endCol)
            }
            if parts[parts.count - 1].isEmpty {
                throw LineError("E001", "Expected a movement before '|'.", tok.col, tok.endCol)
            }
            parts.append([])
        } else {
            parts[parts.count - 1].append(tok)
        }
    }
    if parts[parts.count - 1].isEmpty, let last = tokens.last {
        throw LineError("E001", "Expected a movement after '|'.", last.col, last.endCol)
    }
    let mv = try parseOneMovement(line, parts[0], file, allowReplace)
    for part in parts.dropFirst() {
        mv.alternatives.append(try parseOneMovement(line, part, file))
    }
    return mv
}

private func parseOneMovement(
    _ line: SourceLine,
    _ tokens: [Token],
    _ file: String?,
    _ allowReplace: Bool = false
) throws -> MovementLine {
    let cur = Cursor(tokens, line)
    let quantity = try parseQuantity(cur, file)
    let named = try parseName(cur)
    let nameSpan = Span(line.number, named.startCol, named.endCol, file)
    let lineSpan = Span(line.number, tokens[0].col, cur.endCol, file)
    let mv = MovementLine(named.name, nameSpan, lineSpan, quantity)
    mv.sets = try parseSets(cur, file)
    if allowReplace {
        // a level line may carry selector parameters before the arrow: "Deadlift 225 lb -> Deadlift 155 lb"
        while !cur.done, let tok = cur.peek(), tok.isSymbol("@") || tok.kind == .number || tok.isWord("bw", "rpe") {
            mv.selectorParams.append(try parseParam(cur, file))
        }
    }
    if let ahead = cur.peek(), ahead.kind == .arrow {
        let arrow = try cur.next()
        guard allowReplace else {
            throw LineError("E014", "'->' is only allowed in a level block (Scaled:, …).", arrow.col, arrow.endCol)
        }
        let replacement = try parseName(cur)
        mv.replaceWith = replacement.name
        mv.replaceSpan = Span(line.number, replacement.startCol, replacement.endCol, file)
        mv.sets = try parseSets(cur, file) ?? mv.sets
    } else {
        mv.params = mv.selectorParams
        mv.selectorParams = []
    }
    while !cur.done {
        guard let tok = cur.peek() else { break }
        if tok.isSymbol("(") {
            mv.modifiers.append(contentsOf: try parseModifiers(cur))
            continue
        }
        if tok.isSymbol("@") || tok.kind == .number || tok.isWord("bw", "rpe") {
            mv.params.append(try parseParam(cur, file))
            continue
        }
        if tok.isSymbol(",") {
            _ = try cur.next()
            continue
        }
        throw LineError("E001", "Unexpected '\(tok.text)' in a movement line.", tok.col, tok.endCol)
    }
    return mv
}

// MARK: - dispatch

enum MetaOrLabelKind: String {
    case meta
    case label
    case unknown
}

struct MetaOrLabel: Equatable {
    var kind: MetaOrLabelKind
    var name: String
    var colonIndex: Int
}

/// `(kind, name, colon index)` where kind is `meta` or `label`.
func metaOrLabel(_ line: SourceLine, _ tokens: [Token], _ file: String?) -> MetaOrLabel? {
    guard let first = tokens.first, first.kind == .word else { return nil }
    let index: Int = 1
    let name: String = first.lower
    if first.isWord("min"), tokens.count > 2, tokens[1].kind == .number, tokens[2].isSymbol(":") {
        let minute: Int = Int(Double(tokens[1].text) ?? 0)
        return MetaOrLabel(kind: .label, name: "min \(minute)", colonIndex: 2)
    }
    if tokens.count > index, tokens[index].isSymbol(":") {
        if metaKeys.contains(name) {
            return MetaOrLabel(kind: .meta, name: name, colonIndex: index)
        }
        if let label = labelNames[name] {
            return MetaOrLabel(kind: .label, name: label, colonIndex: index)
        }
        return MetaOrLabel(kind: .unknown, name: name, colonIndex: index)
    }
    return nil
}

/// Parse a non-heading line. Returns nil when the line is invalid (a diagnostic was emitted).
func parseLine(_ line: SourceLine, _ diags: DiagnosticBag, _ file: String?, _ allowReplace: Bool = false) -> Statement? {
    if line.text.isEmpty {
        if let comment = line.comment, !comment.isEmpty {
            return CommentLine(comment, Span(line.number, line.col0, 0, file))
        }
        return nil
    }
    let scratch = DiagnosticBag()
    let tokens: [Token] = Lexer.tokenize(line, scratch, file)
    // meta values and library paths are free text: they must not go through the lexer's expectations
    var freeText: Bool = false
    if let first = tokens.first {
        let found = metaOrLabel(line, tokens, file)
        let isMeta: Bool = found == MetaOrLabel(kind: .meta, name: first.lower, colonIndex: 1)
        freeText = isMeta || first.isWord("use")
    }
    if !freeText {
        diags.extend(scratch)
    }
    if tokens.isEmpty {
        return nil
    }
    let span = Span(line.number, line.col0, line.indent + line.text.count + 1, file)
    do {
        if let found = metaOrLabel(line, tokens, file) {
            let rest: [Token] = Array(tokens[(found.colonIndex + 1)...])
            if found.kind == .unknown {
                let head: Token = tokens[0]
                let colonEnd: Int = tokens[found.colonIndex].endCol
                if head.text.first?.isLowercase == true {
                    throw LineError(
                        "E012",
                        "Unknown meta key '\(found.name)'.",
                        head.col,
                        colonEnd,
                        "known keys: " + metaKeys.sorted().joined(separator: ", ")
                    )
                }
                throw LineError(
                    "E011",
                    "Unknown label '\(head.text)'.",
                    head.col,
                    colonEnd,
                    "known labels: Buy-in, Cash-out, Odd, Even, Min N, Scaled, Intermediate, Foundations"
                )
            }
            if found.kind == .meta {
                let characters: [Character] = Array(line.text)
                guard let colonAt = characters.firstIndex(of: ":") else { return nil }
                let raw: String = String(characters[(colonAt + 1)...]).trimmingCharacters(in: .whitespaces)
                let valueCol: Int = line.indent + colonAt + 2
                let valueSpan = Span(line.number, valueCol, span.endCol, file)
                return MetaLine(found.name, raw, span, valueSpan)
            }
            let isMinute: Bool = found.name.hasPrefix("min ")
            let block = BlockNode(isMinute ? "min" : found.name, span)
            block.isLabel = true
            if isMinute {
                block.slotMinute = Int(found.name.dropFirst(4))
                block.kind = "slot"
            } else if found.name == "odd" || found.name == "even" {
                block.slotName = found.name
                block.kind = "slot"
            }
            if !rest.isEmpty {
                if rest[0].isWord("rest") {
                    let inline = Cursor(rest, line)
                    _ = try inline.next()
                    block.children.append(RestLine(try parseDuration(inline, bareMinutes: false), span))
                    try inline.expectEnd()
                } else {
                    block.children.append(try parseMovement(line, rest, file, allowReplace))
                }
            }
            return block
        }
        if tokens[0].isWord("rest") {
            let cur = Cursor(tokens, line)
            _ = try cur.next()
            let duration = try parseDuration(cur, bareMinutes: false)
            try cur.expectEnd()
            return RestLine(duration, span)
        }
        if tokens[0].isWord("use") {
            let parts: [Substring] = line.text.split(separator: " ", maxSplits: 1, omittingEmptySubsequences: true)
            let path: String = parts.count > 1 ? String(parts[1]).trimmingCharacters(in: .whitespaces) : ""
            if path.isEmpty {
                throw LineError(
                    "E001",
                    "Expected a library path after 'use'.",
                    tokens[0].col,
                    tokens[0].endCol,
                    "e.g. 'use girls/fran'"
                )
            }
            return UseLine(path, span)
        }
        if isFormatStart(tokens) {
            return try parseFormat(line, tokens, file)
        }
        return try parseMovement(line, tokens, file, allowReplace)
    } catch let error as LineError {
        diags.add(error.code, error.message, Span(line.number, error.col, error.endCol, file), error.suggestion)
        return nil
    } catch {
        return nil
    }
}
