/// Diagnostics: coded, located messages produced by every compiler stage (SPEC §15).
import Foundation

public enum Severity: String, Codable, Sendable {
    case error
    case warning
    case info
}

/// A 1-based source location. `endCol` is exclusive; `nil` means "end of line".
public struct Diagnostic: Sendable, Equatable {
    public let code: String
    public let severity: Severity
    public let message: String
    public let line: Int
    public let col: Int
    public let endCol: Int?
    public let file: String?
    public let suggestion: String?

    public init(
        code: String,
        message: String,
        line: Int,
        col: Int = 1,
        endCol: Int? = nil,
        file: String? = nil,
        suggestion: String? = nil
    ) {
        self.code = code
        self.severity = Diagnostic.severity(of: code)
        self.message = message
        self.line = line
        self.col = col
        self.endCol = endCol
        self.file = file
        self.suggestion = suggestion
    }

    static func severity(of code: String) -> Severity {
        switch code.first {
        case "E": return .error
        case "W": return .warning
        default: return .info
        }
    }

    /// `file:line:col: severity CODE: message`, with the offending line underlined when given.
    public func format(sourceLines: [String]? = nil) -> String {
        let where_: String = file.map { "\($0):" } ?? ""
        let head: String = "\(where_)\(line):\(col): \(severity.rawValue) \(code): \(message)"
        var parts: [String] = [head]
        if let lines = sourceLines, line > 0, line <= lines.count {
            let text: String = lines[line - 1]
            let width: Int
            if let end = endCol, end > col {
                width = end - col
            } else {
                width = 1
            }
            parts.append("    " + text)
            let pad: String = String(repeating: " ", count: max(0, col - 1))
            let carets: String = String(repeating: "^", count: max(1, width))
            parts.append("    " + pad + carets)
        }
        if let suggestion {
            parts.append("    help: \(suggestion)")
        }
        return parts.joined(separator: "\n")
    }
}

/// A source span carried around by the syntax stages.
struct Span: Equatable, Sendable {
    var line: Int
    var col: Int = 1
    /// Exclusive; 0 means "end of line".
    var endCol: Int = 0
    var file: String?

    init(_ line: Int, _ col: Int = 1, _ endCol: Int = 0, _ file: String? = nil) {
        self.line = line
        self.col = col
        self.endCol = endCol
        self.file = file
    }
}

/// Collects diagnostics across every stage of one compilation.
final class DiagnosticBag {
    private(set) var items: [Diagnostic] = []

    init(_ items: [Diagnostic] = []) {
        self.items = items
    }

    func add(_ code: String, _ message: String, _ span: Span, _ suggestion: String? = nil) {
        let end: Int? = span.endCol > 0 ? span.endCol : nil
        let diagnostic = Diagnostic(
            code: code,
            message: message,
            line: span.line,
            col: span.col,
            endCol: end,
            file: span.file,
            suggestion: suggestion
        )
        items.append(diagnostic)
    }

    func extend(_ other: [Diagnostic]) {
        items.append(contentsOf: other)
    }

    func extend(_ other: DiagnosticBag) {
        items.append(contentsOf: other.items)
    }

    var hasErrors: Bool {
        items.contains { $0.severity == .error }
    }

    /// Sorted, and without the duplicates a workout used several times would produce.
    func sorted() -> [Diagnostic] {
        var seen = Set<String>()
        var unique: [Diagnostic] = []
        for diagnostic in items {
            let file: String = diagnostic.file ?? ""
            let key: String = "\(file)\u{1}\(diagnostic.line)\u{1}\(diagnostic.col)\u{1}\(diagnostic.code)\u{1}\(diagnostic.message)"
            if seen.insert(key).inserted {
                unique.append(diagnostic)
            }
        }
        return unique.sorted { lhs, rhs in
            let lf: String = lhs.file ?? ""
            let rf: String = rhs.file ?? ""
            if lf != rf { return lf < rf }
            if lhs.line != rhs.line { return lhs.line < rhs.line }
            if lhs.col != rhs.col { return lhs.col < rhs.col }
            return lhs.code < rhs.code
        }
    }
}
