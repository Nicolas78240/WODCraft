/// The compiled WODCraft document, as described by `spec/workout.schema.json` (SPEC §13).
///
/// These types are the contract between the compiler and an application: decode a document, and
/// `score` tells you what to ask the athlete, `blocks` what to display, `estimate` how long it takes.
import Foundation

// MARK: - Amounts

/// A number, or one number per category when the source wrote a dual such as `95/65 lb`.
public enum Amount: Codable, Equatable, Sendable {
    case single(Double)
    case dual(men: Double, women: Double)

    public enum Category: String, Codable, Sendable {
        case men, women
    }

    public func value(for category: Category = .men) -> Double {
        switch self {
        case let .single(value): return value
        case let .dual(men, women): return category == .men ? men : women
        }
    }

    public var isDual: Bool {
        if case .dual = self { return true }
        return false
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Double.self) {
            self = .single(value)
            return
        }
        let pair = try container.decode([String: Double].self)
        guard let men = pair["men"], let women = pair["women"] else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "an amount is a number or {men, women}")
        }
        self = .dual(men: men, women: women)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case let .single(value): try container.encode(value)
        case let .dual(men, women): try container.encode(["men": men, "women": women])
        }
    }
}

// MARK: - Measures

/// A load, always carried in kilograms and pounds. `value` is set once resolved for an athlete.
public struct Load: Codable, Equatable, Sendable {
    public var kg: Amount
    public var lb: Amount?
    public var unit: String?
    public var written: Amount?
    public var value: Double?
}

/// A box or target height, in centimetres and inches.
public struct Height: Codable, Equatable, Sendable {
    public var cm: Amount
    public var inches: Amount?
    public var unit: String?
    public var written: Amount?
    public var value: Double?

    enum CodingKeys: String, CodingKey {
        case cm, unit, written, value
        case inches = "in"
    }
}

public struct Percent: Codable, Equatable, Sendable {
    public var value: Amount
    /// The movement whose one-rep max the percentage applies to.
    public var of: String?
}

public struct Sets: Codable, Equatable, Sendable {
    /// One entry per set: `5x5` is `[5, 5, 5, 5, 5]`.
    public var reps: [Int]
}

/// What a movement is measured in.
public struct Quantity: Codable, Equatable, Sendable {
    public enum Kind: String, Codable, Sendable {
        case reps, distance, calories, time, max
    }

    public var kind: Kind
    public var reps: Amount?
    public var m: Amount?
    public var cal: Amount?
    public var s: Amount?
    /// `kind == .max`: what is counted.
    public var of: String?
    public var unit: String?
    public var written: Amount?
}

public struct SourceSpan: Codable, Equatable, Sendable {
    public var line: Int
    public var col: Int
}

// MARK: - Items

public struct Movement: Codable, Equatable, Sendable {
    /// Catalog identifier, e.g. `pull_up`.
    public var movement: String
    public var name: String
    public var quantity: Quantity?
    public var load: Load?
    public var height: Height?
    public var distance: Quantity?
    public var calories: Quantity?
    public var percent: Percent?
    public var rpe: Amount?
    public var bodyweight: Amount?
    public var sets: Sets?
    public var modifiers: [String]?
    /// 1.1, resolved workouts only — a movement that takes its reps from a ladder, done `factor` times.
    public var factor: Double?
    /// 1.1 — the other options of an alternative (`10 Ring row | 8 Scapular pull-up`).
    public var or: [Movement]?
    public var source: SourceSpan?

    /// Every option of the line, this movement first (a single element without an alternative).
    public var options: [Movement] {
        var first = self
        first.or = nil
        return [first] + (or ?? [])
    }
}

public struct Rest: Codable, Equatable, Sendable {
    public var seconds: Double
    public var source: SourceSpan?
}

public struct UsedFrom: Codable, Equatable, Sendable {
    public var path: String
    public var title: String?
}

public struct Block: Codable, Equatable, Sendable {
    public enum Kind: String, Codable, Sendable {
        case forTime = "for_time"
        case amrap, emom, every, tabata
        case deathBy = "death_by"
        case maxLoad = "max_load"
        case rounds, ladder, slot
        case buyIn = "buy_in"
        case cashOut = "cash_out"
    }

    public var type: Kind
    public var rounds: Int?
    public var reps: [Int]?
    public var repsOpen: Bool?
    public var durationS: Double?
    public var intervalS: Double?
    public var capS: Double?
    public var teams: Int?
    public var slot: Slot?
    /// 1.1 — the items in order, then back to the first one without repeating the last.
    public var thereAndBack: Bool?
    public var used: UsedFrom?
    public var items: [Item]
    public var source: SourceSpan?

    /// `Odd:`, `Even:` or `Min N:`.
    public enum Slot: Codable, Equatable, Sendable {
        case odd, even
        case minute(Int)

        public init(from decoder: Decoder) throws {
            let container = try decoder.singleValueContainer()
            if let number = try? container.decode(Int.self) {
                self = .minute(number)
                return
            }
            switch try container.decode(String.self) {
            case "odd": self = .odd
            case "even": self = .even
            case let other:
                throw DecodingError.dataCorruptedError(in: container, debugDescription: "unknown slot \(other)")
            }
        }

        public func encode(to encoder: Encoder) throws {
            var container = encoder.singleValueContainer()
            switch self {
            case .odd: try container.encode("odd")
            case .even: try container.encode("even")
            case let .minute(number): try container.encode(number)
            }
        }
    }
}

/// One element of a block: a movement, a prescribed rest, or a nested block.
public enum Item: Codable, Equatable, Sendable {
    case movement(Movement)
    case rest(Rest)
    case block(Block)

    private enum TypeKey: String, CodingKey { case type }

    public init(from decoder: Decoder) throws {
        let kind = try decoder.container(keyedBy: TypeKey.self).decode(String.self, forKey: .type)
        switch kind {
        case "movement": self = .movement(try Movement(from: decoder))
        case "rest": self = .rest(try Rest(from: decoder))
        default: self = .block(try Block(from: decoder))
        }
    }

    public func encode(to encoder: Encoder) throws {
        switch self {
        case let .movement(movement):
            try movement.encode(to: encoder)
            try encodeType("movement", to: encoder)
        case let .rest(rest):
            try rest.encode(to: encoder)
            try encodeType("rest", to: encoder)
        case let .block(block):
            try block.encode(to: encoder)
        }
    }

    private func encodeType(_ value: String, to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: TypeKey.self)
        try container.encode(value, forKey: .type)
    }
}

public extension Item {
    /// The block behind this item, when it is one.
    var asBlock: Block? {
        if case let .block(block) = self { return block }
        return nil
    }

    var asMovement: Movement? {
        if case let .movement(movement) = self { return movement }
        return nil
    }

    var asRest: Rest? {
        if case let .rest(rest) = self { return rest }
        return nil
    }

    /// `"movement"`, `"rest"`, or the block kind — what the `type` field of the JSON carries.
    var type: String {
        switch self {
        case .movement: return "movement"
        case .rest: return "rest"
        case let .block(block): return block.type.rawValue
        }
    }

    // Reading a block's fields without unwrapping first: an item that is not a block has none.
    var items: [Item] { asBlock?.items ?? [] }
    var rounds: Int? { asBlock?.rounds }
    var reps: [Int]? { asBlock?.reps }
    var repsOpen: Bool? { asBlock?.repsOpen }
    var durationS: Double? { asBlock?.durationS }
    var intervalS: Double? { asBlock?.intervalS }
    var capS: Double? { asBlock?.capS }
    var teams: Int? { asBlock?.teams }
    var slot: Block.Slot? { asBlock?.slot }
    var used: UsedFrom? { asBlock?.used }
    var source: SourceSpan? {
        switch self {
        case let .movement(movement): return movement.source
        case let .rest(rest): return rest.source
        case let .block(block): return block.source
        }
    }
}

// MARK: - Score, levels, meta

public struct Score: Codable, Equatable, Sendable {
    public enum Kind: String, Codable, Sendable {
        case time
        case roundsAndReps = "rounds+reps"
        case rounds, reps, load, distance, calories, none, multi
    }

    public struct Part: Codable, Equatable, Sendable {
        public var type: Kind
        /// Index of the block this part scores.
        public var block: Int
        /// 1.1 — that block is done there and back.
        public var thereAndBack: Bool?
    }

    public var type: Kind
    /// What an athlete who hits the cap scores instead.
    public var capped: Kind?
    public var tiebreak: String?
    /// 1.1 — the scored block is done there and back: a round is the whole path, and a capped
    /// athlete counts the reps done along it.
    public var thereAndBack: Bool?
    public var parts: [Part]?
}

public struct LevelOperation: Codable, Equatable, Sendable {
    public var movement: String?
    public var replaceWith: String?
    public var name: String?
    public var when: When?
    public var load: Load?
    public var height: Height?
    public var percent: Percent?
    public var rpe: Amount?
    public var bodyweight: Amount?
    /// 1.1 — `A -> 2x B`: the quantities of every occurrence are multiplied.
    public var factor: Double?
    /// 1.1 — `A -> 10 B`: the quantity of every occurrence is replaced.
    public var quantity: Quantity?
    public var meta: [String: MetaValue]?
    public var source: SourceSpan?

    public struct When: Codable, Equatable, Sendable {
        public var load: Load?
        public var height: Height?
    }
}

/// A meta value: free text, a list of words, a load, or nothing (`vest: none`).
public enum MetaValue: Codable, Equatable, Sendable {
    case text(String)
    case list([String])
    case load(Load)
    case none

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .none
        } else if let text = try? container.decode(String.self) {
            self = .text(text)
        } else if let list = try? container.decode([String].self) {
            self = .list(list)
        } else {
            self = .load(try container.decode(Load.self))
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .none: try container.encodeNil()
        case let .text(text): try container.encode(text)
        case let .list(list): try container.encode(list)
        case let .load(load): try container.encode(load)
        }
    }
}

public struct Meta: Codable, Equatable, Sendable {
    public var tags: [String]?
    public var notes: [String]?
    public var stimulus: [String]?
    public var vest: Load?
    public var tiebreak: String?
    public var date: String?
    public var time: String?
}

public struct Estimate: Codable, Equatable, Sendable {
    public var minS: Double
    public var maxS: Double
    public var cappedS: Double?

    public var range: ClosedRange<Double> { minS...maxS }
}

public struct Team: Codable, Equatable, Sendable {
    public var size: Int
}

public struct Resolved: Codable, Equatable, Sendable {
    public var category: Amount.Category
    public var level: String
    public var units: String
}

// MARK: - Documents

public struct Workout: Codable, Equatable, Sendable {
    public var wodcraft: String
    public var kind: String
    public var title: String?
    /// The body: blocks, plus any movement or rest line written at the top level (a strength piece).
    public var blocks: [Item]
    public var score: Score
    public var team: Team?
    public var levels: [String: [LevelOperation]]?
    public var meta: Meta?
    public var estimate: Estimate?
    public var resolved: Resolved?
}

public struct Section: Codable, Equatable, Sendable {
    public var title: String
    public var workout: Workout
    public var source: SourceSpan?
}

public struct Session: Codable, Equatable, Sendable {
    public var wodcraft: String
    public var kind: String
    public var title: String?
    public var date: String?
    public var time: String?
    public var units: String?
    public var tags: [String]?
    public var notes: [String]?
    public var stimulus: [String]?
    public var sections: [Section]
    public var estimate: Estimate?
}

/// A compiled document: a single workout, or a session made of sections.
public enum Document: Codable, Equatable, Sendable {
    case workout(Workout)
    case session(Session)

    private enum KindKey: String, CodingKey { case kind }

    public init(from decoder: Decoder) throws {
        let kind = try decoder.container(keyedBy: KindKey.self).decode(String.self, forKey: .kind)
        self = kind == "session" ? .session(try Session(from: decoder)) : .workout(try Workout(from: decoder))
    }

    public func encode(to encoder: Encoder) throws {
        switch self {
        case let .workout(workout): try workout.encode(to: encoder)
        case let .session(session): try session.encode(to: encoder)
        }
    }

    public var title: String? {
        switch self {
        case let .workout(workout): return workout.title
        case let .session(session): return session.title
        }
    }

    /// Every workout of the document: one for a workout, one per section for a session.
    public var workouts: [Workout] {
        switch self {
        case let .workout(workout): return [workout]
        case let .session(session): return session.sections.map(\.workout)
        }
    }
}

// MARK: - Coding

public extension JSONDecoder {
    /// A decoder configured for WODCraft documents (`duration_s` → `durationS`).
    static var wodcraft: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }
}

public extension JSONEncoder {
    static var wodcraft: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }
}
