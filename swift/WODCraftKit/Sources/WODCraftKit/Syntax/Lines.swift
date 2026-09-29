/// Parse one logical line into a statement (format, label, movement, rest, use or meta).
import Foundation

let metaKeys: Set<String> = ["cap", "score", "tiebreak", "units", "vest", "stimulus", "note", "tags", "date", "time"]

let labelNames: [String: String] = [
    "buy-in": "buy_in",
    "buyin": "buy_in",
    "cash-out": "cash_out",
    "cashout": "cash_out",
    "odd": "odd",
    "even": "even",
    "scaled": "scaled",
    "intermediate": "intermediate",
    "foundations": "foundations",
    "adapted": "adapted",
]

let modifierWords: Set<String> = ["sync", "split", "each", "alternating", "unbroken", "strict"]

struct LineError: Error {
    var code: String
    var message: String
    var col: Int
    var endCol: Int = 0
    var suggestion: String?

    init(_ code: String, _ message: String, _ col: Int, _ endCol: Int = 0, _ suggestion: String? = nil) {
        self.code = code
        self.message = message
        self.col = col
        self.endCol = endCol
        self.suggestion = suggestion
    }
}

/// `E2MOM` / `E3MOM`: every *n* minutes.
func enmomMinutes(_ word: String) -> Int? {
    let characters: [Character] = Array(word.lowercased())
    guard characters.count >= 5, characters.first == "e" else { return nil }
    guard characters.suffix(3) == ["m", "o", "m"] else { return nil }
    let digits = String(characters[1..<(characters.count - 3)])
    guard !digits.isEmpty, digits.allSatisfy(\.isNumber) else { return nil }
    return Int(digits)
}

/// `x5` after an `Every 3:00` interval.
func xNumber(_ word: String) -> Int? {
    let characters: [Character] = Array(word.lowercased())
    guard characters.count > 1, characters.first == "x" else { return nil }
    let digits = String(characters[1...])
    guard digits.allSatisfy(\.isNumber) else { return nil }
    return Int(digits)
}

final class Cursor {
    var toks: [Token]
    var i: Int = 0
    var line: SourceLine

    init(_ tokens: [Token], _ line: SourceLine) {
        self.toks = tokens
        self.line = line
    }

    func peek(_ k: Int = 0) -> Token? {
        let j: Int = i + k
        guard j >= 0, j < toks.count else { return nil }
        return toks[j]
    }

    func next() throws -> Token {
        guard let tok = peek() else {
            throw LineError("E001", "Unexpected end of line.", endCol)
        }
        i += 1
        return tok
    }

    var done: Bool { i >= toks.count }

    var endCol: Int { line.indent + line.text.count + 1 }

    func acceptWord(_ words: String...) -> Token? {
        acceptWord(words)
    }

    func acceptWord(_ words: [String]) -> Token? {
        if let tok = peek(), tok.isWord(words) {
            i += 1
            return tok
        }
        return nil
    }

    func acceptSymbol(_ symbol: String) -> Token? {
        if let tok = peek(), tok.isSymbol(symbol) {
            i += 1
            return tok
        }
        return nil
    }

    func expectEnd() throws {
        if let tok = peek() {
            throw LineError("E001", "Unexpected '\(tok.text)'.", tok.col, tok.endCol)
        }
    }

    func span(_ tok: Token, _ file: String?, _ end: Token? = nil) -> Span {
        Span(line.number, tok.col, (end ?? tok).endCol, file)
    }
}

// MARK: - primitives

private func number(_ tok: Token) -> Double {
    Double(tok.text) ?? 0
}

/// `NUM [/ NUM]`
func parseDual(_ cur: Cursor) throws -> Dual {
    let first = try cur.next()
    guard first.kind == .number else {
        throw LineError("E001", "Expected a number, found '\(first.text)'.", first.col, first.endCol)
    }
    if let ahead = cur.peek(), ahead.isSymbol("/") {
        _ = try cur.next()
        let second = try cur.next()
        guard second.kind == .number else {
            throw LineError("E001", "Expected a number after '/'.", second.col, second.endCol)
        }
        return Dual(number(first), number(second), true)
    }
    return Dual.single(number(first))
}

/// `CLOCK | NUM unit | NUM` (minutes, format lines only).
func parseDuration(_ cur: Cursor, bareMinutes: Bool) throws -> Double {
    let tok = try cur.next()
    if tok.kind == .clock {
        return Units.parseClock(tok.text)
    }
    if tok.kind == .number {
        let unitTok: Token? = cur.peek()
        var kind: (kind: String, unit: String)?
        if let unitTok, unitTok.kind == .word {
            kind = Units.unitKind(unitTok.text)
        }
        if let kind, kind.kind == "time" {
            _ = try cur.next()
            return Units.seconds(number(tok), kind.unit)
        }
        if let kind, kind.unit == "m", let unitTok {
            throw LineError(
                "E001",
                "'m' means metres, not minutes.",
                unitTok.col,
                unitTok.endCol,
                "write '\(tok.text) min' or '\(tok.text):00'"
            )
        }
        if bareMinutes {
            return number(tok) * 60
        }
        throw LineError(
            "E001",
            "Duration '\(tok.text)' needs a unit.",
            tok.col,
            tok.endCol,
            "write '\(tok.text):00' or '\(tok.text) s'"
        )
    }
    throw LineError("E001", "Expected a duration, found '\(tok.text)'.", tok.col, tok.endCol)
}

func looksLikeDuration(_ cur: Cursor) -> Bool {
    guard let tok = cur.peek() else { return false }
    return tok.kind == .clock || tok.kind == .number
}

// MARK: - format lines

let formatStarters: Set<String> = ["for", "amrap", "emom", "every", "tabata", "death", "max", "teams"]

func isFormatStart(_ tokens: [Token]) -> Bool {
    guard let first = tokens.first else { return false }
    if first.kind == .word {
        let word: String = first.lower
        if word == "for" {
            return tokens.count > 1 && tokens[1].isWord("time")
        }
        if word == "max" {
            return tokens.count > 1 && tokens[1].isWord("load")
        }
        if word == "death" {
            return tokens.count > 1 && tokens[1].isWord("by")
        }
        if word == "teams" {
            return tokens.count > 1 && tokens[1].isWord("of")
        }
        return formatStarters.contains(word) || enmomMinutes(word) != nil
    }
    if first.kind == .number {
        // "3 rounds …" or a rep ladder "21-15-9" (a ladder has at least one '-' and nothing else)
        if tokens.count > 1 && tokens[1].isWord("rounds", "round", "rft") {
            return true
        }
        if tokens.count >= 3 && tokens[1].isSymbol("-") && tokens[2].kind == .number {
            return true
        }
    }
    return false
}

let timedStarters: Set<String> = ["for", "amrap", "emom", "every", "tabata", "death", "max"]

/// A format line that puts the athlete on the clock (SPEC §4.1 rule 2).
func formatIsTimed(_ tokens: [Token]) -> Bool {
    tokens.contains { tok in
        guard tok.kind == .word else { return false }
        return timedStarters.contains(tok.lower) || enmomMinutes(tok.text) != nil || tok.lower == "rft"
    }
}

private func splitSegments(_ tokens: [Token]) -> [[Token]] {
    var segments: [[Token]] = [[]]
    for tok in tokens {
        if tok.isSymbol(",") {
            segments.append([])
        } else {
            segments[segments.count - 1].append(tok)
        }
    }
    return segments
}

func parseFormat(_ line: SourceLine, _ tokens: [Token], _ file: String?) throws -> BlockNode {
    let span = Span(line.number, line.col0, line.indent + line.text.count + 1, file)
    var block: BlockNode?
    var options: [[Token]] = []
    for segment in splitSegments(tokens) {
        if segment.isEmpty {
            throw LineError("E001", "Empty element between commas.", span.col, span.endCol)
        }
        if block == nil, isFormatStart(segment), !segment[0].isWord("teams") {
            block = try parseFormatCore(Cursor(segment, line), span)
        } else {
            options.append(segment)
        }
    }
    guard let block else {
        throw LineError("E010", "A format line needs a format (For time, AMRAP, EMOM, N rounds…).", span.col, span.endCol)
    }
    for segment in options {
        let cur = Cursor(segment, line)
        if cur.acceptWord("cap") != nil {
            block.capS = try parseDuration(cur, bareMinutes: true)
        } else if cur.acceptWord("teams") != nil {
            guard cur.acceptWord("of") != nil else {
                throw LineError("E001", "Expected 'Teams of N'.", segment[0].col, segment[segment.count - 1].endCol)
            }
            let size = try cur.next()
            guard size.kind == .number else {
                throw LineError("E001", "Expected the team size.", size.col, size.endCol)
            }
            block.teams = Int(number(size))
        } else if cur.acceptWord("for") != nil {
            guard cur.acceptWord("time") != nil else {
                throw LineError("E001", "Expected 'for time'.", segment[0].col, segment[segment.count - 1].endCol)
            }
            block.forTime = true
        } else if cur.acceptWord("there") != nil {
            guard cur.acceptWord("and") != nil, cur.acceptWord("back") != nil else {
                throw LineError("E001", "Expected 'there and back'.", segment[0].col, segment[segment.count - 1].endCol)
            }
            block.thereAndBack = true
        } else if cur.acceptWord("aller-retour") != nil {
            block.thereAndBack = true
        } else {
            throw LineError(
                "E001",
                "Unknown option '\(segment[0].text)'.",
                segment[0].col,
                segment[segment.count - 1].endCol,
                "options are: cap, teams of N, for time, there and back"
            )
        }
        try cur.expectEnd()
    }
    return block
}

private func parseFormatCore(_ cur: Cursor, _ span: Span) throws -> BlockNode {
    let tok = try cur.next()
    let word: String = tok.kind == .word ? tok.lower : ""
    let block: BlockNode
    if word == "for" {
        _ = try cur.next() // "time"
        block = BlockNode("for_time", span)
        block.forTime = true
    } else if word == "amrap" {
        block = BlockNode("amrap", span)
        if looksLikeDuration(cur) {
            block.durationS = try parseDuration(cur, bareMinutes: true)
        }
    } else if word == "emom" || enmomMinutes(word) != nil {
        block = BlockNode("emom", span)
        block.intervalS = 60.0 * Double(enmomMinutes(word) ?? 1)
        if looksLikeDuration(cur) {
            block.durationS = try parseDuration(cur, bareMinutes: true)
        }
    } else if word == "every" {
        block = BlockNode("every", span)
        if looksLikeDuration(cur) {
            block.intervalS = try parseDuration(cur, bareMinutes: true)
        }
        if let ahead = cur.peek(), ahead.kind == .word, let count = xNumber(ahead.text) {
            _ = try cur.next()
            block.rounds = count
        } else if cur.acceptWord("x", "for") != nil {
            let count = try cur.next()
            guard count.kind == .number else {
                throw LineError("E001", "Expected the number of intervals.", count.col, count.endCol)
            }
            block.rounds = Int(number(count))
            _ = cur.acceptWord("rounds", "intervals", "sets")
        }
    } else if word == "tabata" {
        block = BlockNode("tabata", span)
        block.rounds = 8
        block.intervalS = 30.0
        if let ahead = cur.peek(), ahead.kind == .number {
            _ = try cur.next()
            block.rounds = Int(number(ahead))
        }
    } else if word == "death" {
        _ = try cur.next() // "by"
        block = BlockNode("death_by", span)
        block.intervalS = 60.0
        if !cur.done { // "Death by Burpee" — the rest of the line is the movement
            let rest: [Token] = Array(cur.toks[cur.i...])
            cur.i = cur.toks.count
            block.children.append(try parseMovement(cur.line, rest, span.file))
        }
    } else if word == "max" {
        _ = try cur.next() // "load"
        block = BlockNode("max_load", span)
    } else if tok.kind == .number, let ahead = cur.peek(), ahead.isWord("rounds", "round", "rft") {
        let keyword = try cur.next()
        block = BlockNode("rounds", span)
        block.rounds = Int(number(tok))
        if keyword.isWord("rft") {
            block.forTime = true
        }
    } else if tok.kind == .number {
        var reps: [Int] = [Int(number(tok))]
        while cur.acceptSymbol("-") != nil {
            let value = try cur.next()
            guard value.kind == .number else {
                throw LineError("E001", "Expected a number in the rep ladder.", value.col, value.endCol)
            }
            reps.append(Int(number(value)))
        }
        block = BlockNode("ladder", span)
        block.reps = reps
        if let ahead = cur.peek(), ahead.kind == .ellipsis {
            _ = try cur.next()
            var steps = Set<Int>()
            for index in 0..<max(0, reps.count - 1) {
                steps.insert(reps[index + 1] - reps[index])
            }
            if reps.count < 2 || steps.count != 1 {
                throw LineError("E035", "An open ladder needs a constant step, e.g. '3-6-9 ...'.", span.col, span.endCol)
            }
            block.repsOpen = true
        }
    } else {
        throw LineError("E010", "Unknown format '\(tok.text)'.", tok.col, tok.endCol)
    }
    if cur.acceptWord("for") != nil {
        guard cur.acceptWord("time") != nil else {
            throw LineError("E001", "Expected 'for time'.", span.col, span.endCol)
        }
        block.forTime = true
    }
    try cur.expectEnd()
    return block
}
