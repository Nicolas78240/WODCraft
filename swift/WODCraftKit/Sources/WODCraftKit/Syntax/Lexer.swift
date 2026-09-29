/// Line-level lexer: splits a source into logical lines and a line into tokens.
import Foundation

enum TokenKind: String, Sendable {
    case string = "STRING"
    case clock = "CLOCK"
    case sets = "SETS"
    case number = "NUM"
    case ellipsis = "ELLIPSIS"
    case arrow = "ARROW"
    case word = "WORD"
    case symbol = "SYM"
}

struct Token: Equatable, Sendable {
    let kind: TokenKind
    let text: String
    /// 1-based.
    let col: Int
    /// True when not preceded by whitespace.
    let glued: Bool

    var endCol: Int { col + text.count }

    var lower: String { text.lowercased() }

    func isWord(_ words: String...) -> Bool {
        isWord(words)
    }

    func isWord(_ words: [String]) -> Bool {
        kind == .word && words.contains(lower)
    }

    func isSymbol(_ symbol: String) -> Bool {
        kind == .symbol && text == symbol
    }
}

struct SourceLine: Sendable {
    /// 1-based.
    var number: Int
    var indent: Int
    /// Without indentation and comment, right-stripped.
    var text: String
    var raw: String
    /// `// …` text, without the slashes.
    var comment: String?

    init(_ number: Int, _ indent: Int, _ text: String, _ raw: String, _ comment: String? = nil) {
        self.number = number
        self.indent = indent
        self.text = text
        self.raw = raw
        self.comment = comment
    }

    var col0: Int { indent + 1 }
}

enum Lexer {
    private static let symbols: Set<Character> = ["/", "@", "(", ")", ",", ":", "%", "-", "#", "|"]
    private static let wordTail: Set<Character> = ["'", "\u{2019}", "+", "-", "_"]

    /// Split a line into code and its `//` comment. `//` only starts a comment at line start or
    /// after whitespace, and never inside a quoted string, so URLs such as `https://…` survive.
    static func stripComment(_ text: String) -> (code: String, comment: String?) {
        let characters: [Character] = Array(text)
        var inString: Bool = false
        var index: Int = 0
        while index < characters.count {
            let character: Character = characters[index]
            if character == "\"" {
                inString.toggle()
            } else if character == "/", !inString, index + 1 < characters.count, characters[index + 1] == "/",
                      index == 0 || characters[index - 1].isWhitespace {
                let code = String(characters[0..<index])
                let rest = String(characters[(index + 2)...])
                return (code, rest.trimmingCharacters(in: .whitespaces))
            }
            index += 1
        }
        return (text, nil)
    }

    static func splitLines(_ source: String, _ diags: DiagnosticBag, _ file: String?) -> (lines: [SourceLine], raw: [String]) {
        let normalized: String = source.replacingOccurrences(of: "\r\n", with: "\n").replacingOccurrences(of: "\r", with: "\n")
        let rawLines: [String] = normalized.components(separatedBy: "\n")
        var out: [SourceLine] = []
        for (offset, raw) in rawLines.enumerated() {
            let number: Int = offset + 1
            let split = stripComment(raw)
            let body: String = rightStripped(split.code)
            if body.trimmingCharacters(in: .whitespaces).isEmpty {
                if let comment = split.comment, !comment.isEmpty {
                    let indent: Int = raw.count - leftStripped(raw).count
                    out.append(SourceLine(number, indent, "", raw, comment))
                }
                continue
            }
            let characters: [Character] = Array(body)
            var leadCount: Int = 0
            while leadCount < characters.count, characters[leadCount] == " " || characters[leadCount] == "\t" {
                leadCount += 1
            }
            let lead: [Character] = Array(characters[0..<leadCount])
            let stripped = String(characters[leadCount...])
            var indent: Int = lead.count
            if let tabAt = lead.firstIndex(of: "\t") {
                diags.add("E002", "Tab in indentation; use spaces.", Span(number, tabAt + 1, 0, file))
                let tabs: Int = lead.filter { $0 == "\t" }.count
                indent = lead.count + tabs // each tab becomes two spaces
            }
            out.append(SourceLine(number, indent, stripped, raw, split.comment))
        }
        return (out, rawLines)
    }

    static func tokenize(_ line: SourceLine, _ diags: DiagnosticBag, _ file: String?) -> [Token] {
        var tokens: [Token] = []
        let characters: [Character] = Array(line.text)
        var pos: Int = 0
        while pos < characters.count {
            if characters[pos].isWhitespace {
                pos += 1
                continue
            }
            let col: Int = line.indent + pos + 1
            let glued: Bool = pos > 0 && !characters[pos - 1].isWhitespace
            guard let match = self.match(characters, pos) else {
                diags.add("E001", "Unexpected character '\(characters[pos])'.", Span(line.number, col, col + 1, file))
                pos += 1
                continue
            }
            if match.kind == .number, match.text.contains(",") {
                // decimal comma (DCOMMA in the reference lexer)
                let fixed: String = match.text.replacingOccurrences(of: ",", with: ".")
                diags.add(
                    "E003",
                    "Decimal comma in '\(match.text)'.",
                    Span(line.number, col, col + match.text.count, file),
                    "write '\(fixed)'"
                )
                tokens.append(Token(kind: .number, text: fixed, col: col, glued: glued))
                pos = match.end
                continue
            }
            var text: String = match.text
            if match.kind == .sets {
                text = text.replacingOccurrences(of: "X", with: "x").replacingOccurrences(of: "\u{d7}", with: "x")
            }
            tokens.append(Token(kind: match.kind, text: text, col: col, glued: glued))
            pos = match.end
        }
        return tokens
    }

    // ----------------------------------------------------------------- scanning

    private struct Match {
        var kind: TokenKind
        var text: String
        var end: Int
    }

    private static func match(_ characters: [Character], _ start: Int) -> Match? {
        if let found = matchString(characters, start) { return found }
        if let found = matchClock(characters, start) { return found }
        if let found = matchSets(characters, start) { return found }
        if let found = matchDecimalComma(characters, start) { return found }
        if let found = matchNumber(characters, start) { return found }
        if let found = matchEllipsis(characters, start) { return found }
        if let found = matchArrow(characters, start) { return found }
        if let found = matchWord(characters, start) { return found }
        if symbols.contains(characters[start]) {
            return Match(kind: .symbol, text: String(characters[start]), end: start + 1)
        }
        return nil
    }

    private static func matchString(_ characters: [Character], _ start: Int) -> Match? {
        guard characters[start] == "\"" else { return nil }
        var index: Int = start + 1
        while index < characters.count, characters[index] != "\"" {
            index += 1
        }
        guard index < characters.count else { return nil }
        return Match(kind: .string, text: String(characters[start...index]), end: index + 1)
    }

    private static func digitRun(_ characters: [Character], _ start: Int) -> Int {
        var index: Int = start
        while index < characters.count, characters[index].isNumber, characters[index].isASCII {
            index += 1
        }
        return index
    }

    private static func matchClock(_ characters: [Character], _ start: Int) -> Match? {
        let afterFirst: Int = digitRun(characters, start)
        guard afterFirst > start, afterFirst < characters.count, characters[afterFirst] == ":" else { return nil }
        let minutesStart: Int = afterFirst + 1
        guard minutesStart + 1 < characters.count,
              characters[minutesStart].isNumber, characters[minutesStart].isASCII,
              characters[minutesStart + 1].isNumber, characters[minutesStart + 1].isASCII
        else { return nil }
        var end: Int = minutesStart + 2
        if end + 2 < characters.count, characters[end] == ":",
           characters[end + 1].isNumber, characters[end + 1].isASCII,
           characters[end + 2].isNumber, characters[end + 2].isASCII {
            end += 3
        }
        return Match(kind: .clock, text: String(characters[start..<end]), end: end)
    }

    private static func matchSets(_ characters: [Character], _ start: Int) -> Match? {
        let afterFirst: Int = digitRun(characters, start)
        guard afterFirst > start, afterFirst < characters.count else { return nil }
        let separator: Character = characters[afterFirst]
        guard separator == "x" || separator == "X" || separator == "\u{d7}" else { return nil }
        let afterSecond: Int = digitRun(characters, afterFirst + 1)
        guard afterSecond > afterFirst + 1 else { return nil }
        if afterSecond < characters.count, characters[afterSecond] == "." { return nil }
        return Match(kind: .sets, text: String(characters[start..<afterSecond]), end: afterSecond)
    }

    private static func matchDecimalComma(_ characters: [Character], _ start: Int) -> Match? {
        let afterFirst: Int = digitRun(characters, start)
        guard afterFirst > start, afterFirst < characters.count, characters[afterFirst] == "," else { return nil }
        let afterSecond: Int = digitRun(characters, afterFirst + 1)
        guard afterSecond > afterFirst + 1 else { return nil }
        return Match(kind: .number, text: String(characters[start..<afterSecond]), end: afterSecond)
    }

    private static func matchNumber(_ characters: [Character], _ start: Int) -> Match? {
        let afterFirst: Int = digitRun(characters, start)
        guard afterFirst > start else { return nil }
        var end: Int = afterFirst
        if end < characters.count, characters[end] == "." {
            let afterDot: Int = digitRun(characters, end + 1)
            if afterDot > end + 1 { end = afterDot }
        }
        return Match(kind: .number, text: String(characters[start..<end]), end: end)
    }

    private static func matchEllipsis(_ characters: [Character], _ start: Int) -> Match? {
        if characters[start] == "\u{2026}" {
            return Match(kind: .ellipsis, text: "\u{2026}", end: start + 1)
        }
        guard start + 2 < characters.count,
              characters[start] == ".", characters[start + 1] == ".", characters[start + 2] == "."
        else { return nil }
        return Match(kind: .ellipsis, text: "...", end: start + 3)
    }

    private static func matchArrow(_ characters: [Character], _ start: Int) -> Match? {
        if characters[start] == "\u{2192}" {
            return Match(kind: .arrow, text: "\u{2192}", end: start + 1)
        }
        guard start + 1 < characters.count, characters[start] == "-", characters[start + 1] == ">" else { return nil }
        return Match(kind: .arrow, text: "->", end: start + 2)
    }

    private static func matchWord(_ characters: [Character], _ start: Int) -> Match? {
        guard characters[start].isLetter else { return nil }
        var end: Int = start + 1
        while end < characters.count {
            let character: Character = characters[end]
            if character.isLetter || character.isNumber || wordTail.contains(character) {
                end += 1
            } else {
                break
            }
        }
        return Match(kind: .word, text: String(characters[start..<end]), end: end)
    }

    // ----------------------------------------------------------------- helpers

    static func rightStripped(_ text: String) -> String {
        var characters: [Character] = Array(text)
        while let last = characters.last, last.isWhitespace {
            characters.removeLast()
        }
        return String(characters)
    }

    static func leftStripped(_ text: String) -> String {
        var characters: [Character] = Array(text)
        var index: Int = 0
        while index < characters.count, characters[index].isWhitespace {
            index += 1
        }
        characters.removeFirst(index)
        return String(characters)
    }
}
