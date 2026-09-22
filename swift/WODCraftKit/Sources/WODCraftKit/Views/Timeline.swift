/// Timeline of a workout: what the clock does, segment by segment.
///
/// A port of `src/wodcraft/emit/timeline.py`, plus the slice of
/// `src/wodcraft/semantics/estimate.py` it needs to size a movement. This is what drives a
/// timer: EMOM, Every and Tabata blocks yield one segment per interval.
import Foundation

// MARK: - Segment

/// One stretch of the clock.
public struct TimelineSegment: Equatable, Sendable, Identifiable {
    /// What the athlete is doing during the segment.
    public enum Kind: String, Codable, Sendable {
        /// Continuous work, possibly open-ended.
        case work
        /// Prescribed rest.
        case rest
        /// One interval of an EMOM, an Every or a Tabata.
        case interval
    }

    /// Seconds from the start of the workout.
    public var at: TimeInterval
    /// Length of the segment in seconds; `0` when nothing bounds it.
    public var duration: TimeInterval
    public var label: String
    public var kind: Kind
    /// The segment runs until the athlete stops, not until the clock does.
    public var openEnded: Bool
    /// The section of the session the segment belongs to, if any.
    public var section: String?

    public var id: String {
        return String(at) + "|" + String(duration) + "|" + label
    }

    public init(
        at: TimeInterval = 0,
        duration: TimeInterval,
        label: String,
        kind: Kind,
        openEnded: Bool = false,
        section: String? = nil
    ) {
        self.at = at
        self.duration = duration
        self.label = label
        self.kind = kind
        self.openEnded = openEnded
        self.section = section
    }

    /// The end of the segment, in seconds from the start.
    public var end: TimeInterval { at + duration }
}

// MARK: - Timeline

public enum Timeline {
    /// Every segment of a document, in clock order.
    public static func segments(of document: Document, catalog: Catalog = .shared) -> [TimelineSegment] {
        switch document {
        case let .workout(workout):
            return segments(of: workout, catalog: catalog)
        case let .session(session):
            var all: [TimelineSegment] = []
            var at: TimeInterval = 0
            for section in session.sections {
                for var segment in segments(of: section.workout, catalog: catalog) {
                    segment.at += at
                    segment.section = section.title
                    all.append(segment)
                }
                if let last = all.last { at = last.at + last.duration }
            }
            return all
        }
    }

    public static func segments(of workout: Workout, catalog: Catalog = .shared) -> [TimelineSegment] {
        var at: TimeInterval = 0
        var all: [TimelineSegment] = []
        for block in workout.blocks {
            for var segment in blockSegments(block, workout: workout, catalog: catalog) {
                segment.at = at
                at += segment.duration
                all.append(segment)
            }
        }
        return all
    }

    // MARK: Blocks

    static func blockSegments(_ item: Item, workout: Workout, catalog: Catalog) -> [TimelineSegment] {
        switch item {
        case let .rest(rest):
            return [TimelineSegment(duration: rest.seconds, label: "Rest", kind: .rest)]
        case let .movement(movement):
            let seconds = Estimation.itemSeconds(movement, catalog: catalog)
            return [
                TimelineSegment(
                    duration: seconds,
                    label: Board.movementText(movement, width: 40),
                    kind: .work,
                    openEnded: seconds == 0
                )
            ]
        case let .block(block):
            return blockSegments(block, workout: workout, catalog: catalog)
        }
    }

    static func blockSegments(_ block: Block, workout: Workout, catalog: Catalog) -> [TimelineSegment] {
        var label = Board.headText(block)
        if label.isEmpty { label = block.type.rawValue }

        switch block.type {
        case .emom, .every:
            var interval = block.intervalS ?? 60
            if interval == 0 { interval = 60 }
            var total = block.durationS ?? 0
            if total == 0 {
                total = interval * Double(block.rounds ?? 0)
            }
            let count = interval == 0 ? 0 : Int(floor(total / interval))
            var slots: [Block] = []
            for item in block.items {
                if case let .block(nested) = item, nested.type == .slot { slots.append(nested) }
            }
            var out: [TimelineSegment] = []
            var index = 0
            while index < count {
                let content = slots.isEmpty ? itemsLabel(block.items) : slotLabel(slots, index: index)
                let text = label + " · " + String(index + 1) + "/" + String(count) + ": " + content
                out.append(TimelineSegment(duration: interval, label: text, kind: .interval))
                index += 1
            }
            return out

        case .tabata:
            let rounds = block.rounds ?? 8
            var movements: [Item] = []
            for item in block.items {
                if case .rest = item { continue }
                movements.append(item)
            }
            var out: [TimelineSegment] = []
            if movements.isEmpty {
                var index = 0
                while index < rounds {
                    let text = label + " · " + String(index + 1) + "/" + String(rounds) + ": "
                    out.append(TimelineSegment(duration: 30.0, label: text, kind: .interval))
                    index += 1
                }
                return out
            }
            for item in movements {
                let name = itemsLabel([item])
                var index = 0
                while index < rounds {
                    let text = label + " · " + String(index + 1) + "/" + String(rounds) + ": " + name
                    out.append(TimelineSegment(duration: 30.0, label: text, kind: .interval))
                    index += 1
                }
            }
            return out

        case .amrap:
            if let duration = block.durationS, duration != 0 {
                let text = label + ": " + itemsLabel(block.items)
                return [TimelineSegment(duration: duration, label: text, kind: .work)]
            }
            return [defaultSegment(block, label: label, workout: workout)]

        default:
            return [defaultSegment(block, label: label, workout: workout)]
        }
    }

    static func defaultSegment(_ block: Block, label: String, workout: Workout) -> TimelineSegment {
        var duration: TimeInterval = 0
        if let cap = block.capS, cap != 0 {
            duration = cap
        } else if let estimate = workout.estimate {
            duration = estimate.maxS
        }
        let capped = (block.capS ?? 0) != 0
        let text = label + ": " + itemsLabel(block.items)
        return TimelineSegment(duration: duration, label: text, kind: .work, openEnded: !capped)
    }

    // MARK: Labels

    static func slotLabel(_ slots: [Block], index: Int) -> String {
        for slot in slots {
            switch slot.slot {
            case .some(.odd):
                if index % 2 == 0 { return itemsLabel(slot.items) }
            case .some(.even):
                if index % 2 == 1 { return itemsLabel(slot.items) }
            case let .some(.minute(number)):
                var cycle = 1
                for other in slots {
                    if case let .some(.minute(value)) = other.slot { cycle = max(cycle, value) }
                }
                if cycle != 0 && index % cycle == number - 1 { return itemsLabel(slot.items) }
            case .none:
                continue
            }
        }
        return ""
    }

    static func itemsLabel(_ items: [Item]) -> String {
        var labels: [String] = []
        for item in items {
            switch item {
            case let .movement(movement):
                labels.append(Board.movementText(movement, width: 0, dots: false))
            case let .rest(rest):
                labels.append("Rest " + formatClock(rest.seconds))
            case let .block(block):
                let head = Board.headText(block)
                let inner = itemsLabel(block.items)
                var text = head + " " + inner
                text = text.trimmingCharacters(in: .whitespaces)
                labels.append(text)
            }
        }
        var kept: [String] = []
        for label in labels where !label.isEmpty { kept.append(label) }
        return kept.joined(separator: " + ")
    }

    // MARK: Text rendering

    /// The text form the CLI prints: start, duration, then the label.
    public static func render(_ segments: [TimelineSegment]) -> String {
        var lines: [String] = []
        var total: TimeInterval = 0
        for segment in segments {
            let start = pad(formatClock(segment.at), to: 8)
            let duration = pad(segment.duration == 0 ? "\u{2014}" : formatClock(segment.duration), to: 6)
            let mark = segment.openEnded ? "~" : " "
            lines.append(start + "  " + duration + mark + " " + segment.label)
            total += segment.duration
        }
        lines.append(pad("", to: 8) + "  " + pad(formatClock(total), to: 6) + "  total")
        return lines.joined(separator: "\n")
    }

    static func pad(_ text: String, to width: Int) -> String {
        if text.count >= width { return text }
        var spaces = ""
        for _ in 0..<(width - text.count) { spaces += " " }
        return spaces + text
    }
}

// MARK: - Sugar

public extension Workout {
    /// The timeline of this workout: one segment per stretch of the clock.
    func timeline(catalog: Catalog = .shared) -> [TimelineSegment] {
        return Timeline.segments(of: self, catalog: catalog)
    }
}

public extension Session {
    func timeline(catalog: Catalog = .shared) -> [TimelineSegment] {
        return Timeline.segments(of: .session(self), catalog: catalog)
    }
}

public extension Document {
    func timeline(catalog: Catalog = .shared) -> [TimelineSegment] {
        return Timeline.segments(of: self, catalog: catalog)
    }
}

public extension Array where Element == TimelineSegment {
    /// The text form the CLI prints.
    func rendered() -> String {
        return Timeline.render(self)
    }

    /// Total clock time, ignoring open-ended segments' unknown length.
    var totalDuration: TimeInterval {
        var total: TimeInterval = 0
        for segment in self { total += segment.duration }
        return total
    }
}

// MARK: - Estimation

/// The duration model of SPEC §15, as far as the timeline needs it.
enum Estimation {
    static let fatigue = 1.6
    static let defaultRepPace = 3.0
    static let defaultSetRest = 120.0
    static let loadSensitivity = 1.8
    static let maxLoadFactor = 3.5
    static let minLoadFactor = 0.8
    static let referenceKilograms: [String: Double] = [
        "barbell": 50.0,
        "dumbbell": 22.5,
        "kettlebell": 24.0,
        "medicine_ball": 9.0,
        "sandbag": 45.0,
    ]

    /// Heavier than the usual Rx load means slower reps, and far heavier means singles.
    static func loadFactor(_ item: Movement, entry: CatalogMovement?) -> Double {
        guard let load = item.load, let entry = entry else { return 1.0 }
        let kg = load.kg.value(for: .men)
        var reference: Double?
        if let rx = entry.rx, (rx.unit ?? "kg") == "kg" {
            let men = rx.men ?? 0
            reference = men != 0 ? men : nil
        }
        if reference == nil { reference = referenceKilograms[entry.equipment] }
        guard let base = reference, base != 0, kg != 0 else { return 1.0 }
        let ratio = kg / base
        if ratio <= 1 { return max(minLoadFactor, 0.8 + 0.2 * ratio) }
        return min(maxLoadFactor, 1.0 + loadSensitivity * (ratio - 1))
    }

    /// Work time for one movement item, ignoring rest between sets.
    static func itemSeconds(_ item: Movement, catalog: Catalog) -> Double {
        let entry = catalog.movement(id: item.movement)
        let quantity = item.quantity
        let kind = quantity?.kind

        if kind == .max { return 0.0 }
        if kind == .time {
            guard let seconds = quantity?.s else { return 0.0 }
            return seconds.value(for: .men)
        }

        var pace: Double?
        if let entry = entry {
            let key: String
            switch kind {
            case .some(.distance): key = "distance"
            case .some(.calories): key = "calories"
            default: key = "reps"
            }
            pace = entry.pace(forQuantity: key)
        }

        if kind == .distance {
            let metres = quantity?.m?.value(for: .men) ?? 0
            let perMetre = (pace ?? 0) != 0 ? (pace ?? 0.3) : 0.3
            return metres * perMetre
        }
        if kind == .calories {
            let calories = quantity?.cal?.value(for: .men) ?? 0
            let perCalorie = (pace ?? 0) != 0 ? (pace ?? 3.5) : 3.5
            return calories * perCalorie
        }

        var reps: Double = 0
        if kind == .reps { reps = quantity?.reps?.value(for: .men) ?? 0 }
        let base = (pace ?? 0) != 0 ? (pace ?? defaultRepPace) : defaultRepPace
        let perRep = base * loadFactor(item, entry: entry)

        if let sets = item.sets, !sets.reps.isEmpty {
            var total: Double = 0
            for rep in sets.reps { total += Double(rep) }
            let rest = declaredRest(item) ?? defaultSetRest
            return total * perRep + rest * Double(max(0, sets.reps.count - 1))
        }
        return reps * perRep
    }

    /// A `(rest 2:00)` modifier overrides the default rest between sets.
    static func declaredRest(_ item: Movement) -> Double? {
        for modifier in item.modifiers ?? [] where modifier.hasPrefix("rest ") {
            var text = String(modifier.dropFirst(5))
            text = text.trimmingCharacters(in: .whitespaces)
            if text.contains(":") { return parseClock(text) }
            while let last = text.last, last == "s" || last == " " { text.removeLast() }
            return Double(text)
        }
        return nil
    }

    /// `1:30` and `1:00:00` into seconds.
    static func parseClock(_ text: String) -> Double? {
        var total = 0
        for piece in text.split(separator: ":") {
            guard let value = Int(piece) else { return nil }
            total = total * 60 + value
        }
        return Double(total)
    }
}
