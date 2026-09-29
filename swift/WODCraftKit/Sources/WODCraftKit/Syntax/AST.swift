/// Syntax tree produced by the parser. Values are still in source units; nothing is resolved.
import Foundation

/// A value for the men and women categories. `isDual` is false for a single written value.
struct Dual: Equatable {
    var men: Double
    var women: Double
    var isDual: Bool = false

    init(_ men: Double, _ women: Double, _ isDual: Bool = false) {
        self.men = men
        self.women = women
        self.isDual = isDual
    }

    static func single(_ value: Double) -> Dual {
        Dual(value, value, false)
    }
}

/// Anything the parser can produce for one logical line.
protocol Statement: AnyObject {}

final class QuantityNode {
    /// reps | distance | calories | time | max
    var kind: String
    /// nil for "max"
    var value: Dual?
    /// m, km, mi, cal, s — or, for max: nil/cal/m
    var unit: String?
    var span: Span

    init(_ kind: String, _ value: Dual?, _ unit: String?, _ span: Span) {
        self.kind = kind
        self.value = value
        self.unit = unit
        self.span = span
    }
}

final class ParamNode {
    /// load | height | percent | rpe | bw | distance | calories
    var kind: String
    var value: Dual
    /// kg, lb, pood, in, cm, m, km, mi, cal — nil when omitted
    var unit: String?
    var span: Span
    /// percent: name of the reference lift
    var of: String?
    var ofSpan: Span?

    init(_ kind: String, _ value: Dual, _ unit: String?, _ span: Span, of: String? = nil, ofSpan: Span? = nil) {
        self.kind = kind
        self.value = value
        self.unit = unit
        self.span = span
        self.of = of
        self.ofSpan = ofSpan
    }
}

final class SetsNode {
    /// One entry per set: 5x5 -> [5, 5, 5, 5, 5]
    var reps: [Int]
    var span: Span
    /// "nxm" | "ladder"
    var notation: String

    init(_ reps: [Int], _ span: Span, _ notation: String) {
        self.reps = reps
        self.span = span
        self.notation = notation
    }
}

final class MovementLine: Statement {
    var name: String
    var nameSpan: Span
    var span: Span
    var quantity: QuantityNode?
    var sets: SetsNode?
    var params: [ParamNode] = []
    var modifiers: [String] = []
    /// level blocks: "A -> B"
    var replaceWith: String?
    var replaceSpan: Span?
    /// level blocks: params written before "->"
    var selectorParams: [ParamNode] = []
    /// "10 Ring row | Scapular pull-up": the other options
    var alternatives: [MovementLine] = []
    /// level blocks: "A -> 2x B" multiplies the quantities
    var factor: Double?
    /// level blocks: "A -> 10 B" sets the quantity
    var replaceQuantity: QuantityNode?

    init(_ name: String, _ nameSpan: Span, _ span: Span, _ quantity: QuantityNode? = nil) {
        self.name = name
        self.nameSpan = nameSpan
        self.span = span
        self.quantity = quantity
    }
}

final class RestLine: Statement {
    var seconds: Double
    var span: Span

    init(_ seconds: Double, _ span: Span) {
        self.seconds = seconds
        self.span = span
    }
}

final class UseLine: Statement {
    var path: String
    var span: Span

    init(_ path: String, _ span: Span) {
        self.path = path
        self.span = span
    }
}

final class CommentLine: Statement {
    var text: String
    var span: Span

    init(_ text: String, _ span: Span) {
        self.text = text
        self.span = span
    }
}

final class MetaLine: Statement {
    var key: String
    var value: String
    var span: Span
    var valueSpan: Span

    init(_ key: String, _ value: String, _ span: Span, _ valueSpan: Span) {
        self.key = key
        self.value = value
        self.span = span
        self.valueSpan = valueSpan
    }
}

/// A format block (for_time, amrap…) or a label block (buy_in, odd, scaled…).
final class BlockNode: Statement {
    var kind: String
    var span: Span
    var children: [Statement] = []
    var durationS: Double?
    var intervalS: Double?
    var rounds: Int?
    var reps: [Int]?
    /// ladder written "3-6-9 ..." — continues until the cap
    var repsOpen: Bool = false
    var capS: Double?
    var teams: Int?
    var forTime: Bool = false
    /// "odd" | "even" for a named slot
    var slotName: String?
    /// N for "Min N:"
    var slotMinute: Int?
    var isLabel: Bool = false

    init(_ kind: String, _ span: Span) {
        self.kind = kind
        self.span = span
    }

    var hasSlot: Bool { slotName != nil || slotMinute != nil }
}

let levelLabels: [String] = ["scaled", "intermediate", "foundations"]

final class WorkoutBody {
    var statements: [Statement] = []
    /// kind in `levelLabels`
    var levels: [BlockNode] = []

    init(_ statements: [Statement] = [], _ levels: [BlockNode] = []) {
        self.statements = statements
        self.levels = levels
    }
}

final class SectionNode {
    var title: String
    var span: Span
    var body: WorkoutBody

    init(_ title: String, _ span: Span, _ body: WorkoutBody) {
        self.title = title
        self.span = span
        self.body = body
    }
}

final class DocumentNode {
    var title: String?
    var span: Span
    /// session preamble only
    var meta: [MetaLine] = []
    /// workout
    var body: WorkoutBody?
    /// session
    var sections: [SectionNode]?

    init(_ title: String?, _ span: Span, meta: [MetaLine] = [], body: WorkoutBody? = nil, sections: [SectionNode]? = nil) {
        self.title = title
        self.span = span
        self.meta = meta
        self.body = body
        self.sections = sections
    }

    var isSession: Bool { sections != nil }
}

final class SourceFileNode {
    var documents: [DocumentNode]
    var lines: [String]
    var path: String?

    init(_ documents: [DocumentNode], _ lines: [String], _ path: String? = nil) {
        self.documents = documents
        self.lines = lines
        self.path = path
    }
}
