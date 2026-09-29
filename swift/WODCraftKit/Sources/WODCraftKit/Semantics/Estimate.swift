/// Duration estimates and the plausibility warnings that depend on them (SPEC §15).
import Foundation

enum Estimator {
    /// transitions, breathing, set breaks and the reps that fall apart late
    static let fatigue: Double = 1.6
    /// ± around the central estimate: catalog paces describe an average Rx athlete
    static let spread: Double = 0.3
    // Catalog paces describe an average Rx athlete, so the Rx load costs exactly its pace: the
    // factor is 1 there, drops a little when lighter, and climbs steeply when the bar gets heavy.
    static let loadSensitivity: Double = 1.8
    static let maxLoadFactor: Double = 3.5
    static let minLoadFactor: Double = 0.8
    /// a hard cap is a deliberate cut-off; warn only when the volume is wildly past it
    static let capTolerance: Double = 2.5
    static let referenceKg: [String: Double] = [
        "barbell": 50.0,
        "dumbbell": 22.5,
        "kettlebell": 24.0,
        "medicine_ball": 9.0,
        "sandbag": 45.0,
    ]
    static let defaultRepPace: Double = 3.0
    /// strength work: rest between sets unless the source says otherwise
    static let defaultSetRest: Double = 120.0

    private static func pick(_ value: JSONValue?, _ category: String = "men") -> Double {
        guard let value else { return 0 }
        if let object = value.objectValue {
            if let found = object[category]?.doubleValue { return found }
            if let first = object.keys.first { return object[first]?.doubleValue ?? 0 }
            return 0
        }
        return value.doubleValue ?? 0
    }

    private static func type(of block: JSONObject) -> String {
        block["type"]?.stringValue ?? ""
    }

    private static func items(of block: JSONObject) -> [JSONObject] {
        (block["items"]?.arrayValue ?? []).compactMap(\.objectValue)
    }

    /// Heavier than the usual Rx load means slower reps, and far heavier means singles.
    static func loadFactor(_ item: JSONObject, _ entry: MovementEntry?) -> Double {
        guard let load = item["load"]?.objectValue, let entry else { return 1.0 }
        let kg: Double = pick(load["kg"])
        var reference: Double?
        if let rx = entry.rx, (entry.rxUnit ?? "kg") == "kg" {
            let men: Double = rx["men"] ?? 0
            reference = men == 0 ? nil : men
        }
        if reference == nil {
            reference = referenceKg[entry.equipment]
        }
        guard let reference, reference != 0, kg != 0 else { return 1.0 }
        let ratio: Double = kg / reference
        if ratio <= 1 {
            return max(minLoadFactor, 0.8 + 0.2 * ratio)
        }
        return min(maxLoadFactor, 1.0 + loadSensitivity * (ratio - 1))
    }

    /// Work time for one movement item, ignoring rest between sets.
    static func itemSeconds(_ item: JSONObject, _ catalog: MovementCatalog) -> Double {
        let entry: MovementEntry? = catalog.movements[item["movement"]?.stringValue ?? ""]
        let quantity: JSONObject = item["quantity"]?.objectValue ?? JSONObject()
        let kind: String? = quantity["kind"]?.stringValue
        if kind == "max" { return 0.0 }
        if kind == "time" { return pick(quantity["s"]) }
        let pace: Double? = entry?.pace(for: kind ?? "reps")
        if kind == "distance" {
            return pick(quantity["m"]) * (pace ?? 0.3)
        }
        if kind == "calories" {
            return pick(quantity["cal"]) * (pace ?? 3.5)
        }
        var reps: Double = kind == "reps" ? pick(quantity["reps"]) : 0.0
        let perRep: Double = (pace ?? defaultRepPace) * loadFactor(item, entry) + declaredHold(item)
        if let sets = item["sets"]?.objectValue, let list = sets["reps"]?.arrayValue {
            reps = list.reduce(0.0) { $0 + ($1.doubleValue ?? 0) }
            let rest: Double = declaredRest(item) ?? defaultSetRest
            return reps * perRep + rest * Double(max(0, list.count - 1))
        }
        return reps * perRep
    }

    /// A `(rest 2:00)` modifier overrides the default rest between sets.
    static func declaredRest(_ item: JSONObject) -> Double? {
        for value in item["modifiers"]?.arrayValue ?? [] {
            guard let modifier = value.stringValue, modifier.hasPrefix("rest ") else { continue }
            let text: String = String(modifier.dropFirst(5)).trimmingCharacters(in: .whitespaces)
            if text.contains(":") {
                return Units.parseClock(text)
            }
            let trimmed = text.trimmingCharacters(in: CharacterSet(charactersIn: "s "))
            return Double(trimmed)
        }
        return nil
    }

    /// The items of a block in the order they are done: "there and back" adds the way back,
    /// without repeating the last line (SPEC §5).
    static func path(of block: JSONObject) -> [JSONObject] {
        let list: [JSONObject] = items(of: block)
        guard case .bool(true)? = block["there_and_back"], list.count > 1 else { return list }
        return list + list.dropLast().reversed()
    }

    /// Seconds of the first `hold DURATION` modifier (`hold 10 s`, `hold 0:30`), 0 without one.
    static func holdSeconds(_ modifiers: [String]) -> Double {
        for modifier in modifiers {
            let words: [Substring] = modifier.split(separator: " ", maxSplits: 1)
            guard words.first == "hold", words.count == 2 else { continue }
            let text: String = words[1].trimmingCharacters(in: .whitespaces)
            if text.contains(":") { return Units.parseClock(text) }
            let parts: [Substring] = text.split(separator: " ", maxSplits: 1)
            guard let value = Double(parts.first ?? "") else { return 0 }
            let unit: String = parts.count > 1 ? parts[1].trimmingCharacters(in: .whitespaces) : ""
            return value * (unit == "min" ? 60.0 : 1.0)
        }
        return 0
    }

    /// A `(hold 10 s)` modifier holds every rep: its duration adds to each rep.
    static func declaredHold(_ item: JSONObject) -> Double {
        let modifiers: [String] = (item["modifiers"]?.arrayValue ?? []).compactMap(\.stringValue)
        return holdSeconds(modifiers)
    }

    static func blockSeconds(_ block: JSONObject, _ catalog: MovementCatalog) -> Double {
        let kind: String = type(of: block)
        if kind == "rest" {
            return block["seconds"]?.doubleValue ?? 0
        }
        if kind == "movement" {
            return itemSeconds(block, catalog)
        }
        if kind == "tabata" {
            let movements: [JSONObject] = items(of: block).filter { type(of: $0) != "rest" }
            let count: Int = movements.isEmpty ? 1 : movements.count
            let rounds: Double = block["rounds"]?.doubleValue ?? 8
            return rounds * 30.0 * Double(count)
        }
        if kind == "amrap" || kind == "emom", let duration = block["duration_s"]?.doubleValue, duration != 0 {
            return duration
        }
        if kind == "every", let interval = block["interval_s"]?.doubleValue, interval != 0,
           let rounds = block["rounds"]?.doubleValue, rounds != 0 {
            return interval * rounds
        }

        let children: [JSONObject] = path(of: block)
        // "Rest" as the last item of a repeated block happens between rounds only
        let rounds: Double = block["rounds"]?.doubleValue ?? 1
        let reps: [JSONValue]? = block["reps"]?.arrayValue
        let body: Double = children.reduce(0.0) { $0 + blockSeconds($1, catalog) }
        var trailingRest: Double = 0
        if let last = children.last, type(of: last) == "rest" {
            trailingRest = last["seconds"]?.doubleValue ?? 0
        }

        if let reps, !reps.isEmpty {
            // a rep ladder: movements without their own quantity take each ladder value
            var perRepCost: Double = 0.0
            var fixed: Double = 0.0
            for item in children {
                if type(of: item) == "movement", item["quantity"] == nil {
                    let entry: MovementEntry? = catalog.movements[item["movement"]?.stringValue ?? ""]
                    let pace: Double = entry?.pace(for: "reps") ?? defaultRepPace
                    let factor: Double = item["factor"]?.doubleValue ?? 1
                    perRepCost += (pace * loadFactor(item, entry) + declaredHold(item)) * factor
                } else {
                    fixed += blockSeconds(item, catalog)
                }
            }
            let total: Double = reps.reduce(0.0) { $0 + ($1.doubleValue ?? 0) }
            return total * perRepCost + fixed * Double(reps.count)
        }
        let total: Double = body * (rounds == 0 ? 1 : rounds) - trailingRest
        return max(0.0, total)
    }

    /// Prescribed rest inside a block: it is wall-clock time, so fatigue does not stretch it.
    static func restSeconds(_ block: JSONObject) -> Double {
        let kind: String = type(of: block)
        if kind == "rest" {
            return block["seconds"]?.doubleValue ?? 0
        }
        if kind == "movement" {
            if let sets = block["sets"]?.objectValue, let list = sets["reps"]?.arrayValue {
                let rest: Double = declaredRest(block) ?? defaultSetRest
                return rest * Double(max(0, list.count - 1))
            }
            return 0.0
        }
        let children: [JSONObject] = path(of: block)
        let inner: Double = children.reduce(0.0) { $0 + restSeconds($1) }
        let rounds: Double = block["rounds"]?.doubleValue ?? 1
        if let reps = block["reps"]?.arrayValue, !reps.isEmpty {
            return inner * Double(reps.count)
        }
        var trailing: Double = 0
        if let last = children.last, type(of: last) == "rest" {
            trailing = last["seconds"]?.doubleValue ?? 0
        }
        return max(0.0, inner * (rounds == 0 ? 1 : rounds) - trailing)
    }

    static func estimateWorkout(
        _ workout: JSONObject,
        _ catalog: MovementCatalog,
        _ diags: DiagnosticBag,
        _ file: String?
    ) -> JSONObject? {
        let blocks: [JSONObject] = (workout["blocks"]?.arrayValue ?? []).compactMap(\.objectValue)
        if blocks.isEmpty { return nil }
        var total: Double = 0.0
        var fixed: Bool = false
        for block in blocks {
            let kind: String = type(of: block)
            let seconds: Double = blockSeconds(block, catalog)
            if case .bool(true)? = block["reps_open"], let cap = block["cap_s"]?.doubleValue, cap != 0 {
                // an open ladder runs until the cap: the clock, not the volume, sets the duration
                fixed = true
                total += cap
                continue
            }
            if ["amrap", "emom", "every", "tabata", "rest"].contains(kind) {
                fixed = true
                total += seconds
            } else {
                let rest: Double = restSeconds(block)
                total += max(0.0, seconds - rest) * fatigue + rest
            }
            intervalWarning(block, catalog, diags, file)
        }
        if total <= 0 { return nil }
        let low: Double
        let high: Double
        if fixed, blocks.count == 1 {
            low = total
            high = total
        } else {
            low = total * (1 - spread)
            high = total * (1 + spread)
        }
        let cap: Double? = blocks[0]["cap_s"]?.doubleValue
        // a cap is a cut-off, not a target: only warn when the work is far beyond it
        if let cap, cap != 0, low > cap * capTolerance {
            let source: JSONObject = blocks[0]["source"]?.objectValue ?? JSONObject()
            let line: Int = source["line"]?.intValue ?? 1
            let col: Int = source["col"]?.intValue ?? 1
            let message: String = "Estimated duration (\(mmss(low))–\(mmss(high))) is longer than the cap (\(mmss(cap)))."
            diags.add("W103", message, Span(line, col, 0, file), "raise the cap or cut volume")
        }
        var out = JSONObject()
        out["min_s"] = .number(low.rounded(.toNearestOrEven))
        out["max_s"] = .number(high.rounded(.toNearestOrEven))
        out["capped_s"] = cap.map { JSONValue.number($0) } ?? .null
        return out
    }

    private static func intervalWarning(
        _ block: JSONObject,
        _ catalog: MovementCatalog,
        _ diags: DiagnosticBag,
        _ file: String?
    ) {
        let kind: String = type(of: block)
        guard kind == "emom" || kind == "every" else {
            for child in items(of: block) {
                intervalWarning(child, catalog, diags, file)
            }
            return
        }
        let interval: Double = block["interval_s"]?.doubleValue ?? 60
        let slots: [JSONObject] = items(of: block).filter { type(of: $0) == "slot" }
        let groups: [[JSONObject]]
        if slots.isEmpty {
            groups = [items(of: block).filter { type(of: $0) != "slot" }]
        } else {
            groups = slots.map { items(of: $0) }
        }
        for group in groups {
            let work: Double = group
                .filter { type(of: $0) != "rest" }
                .reduce(0.0) { $0 + blockSeconds($1, catalog) }
            if work > interval * 0.9 {
                let holder: JSONObject = group.first ?? block
                let source: JSONObject = holder["source"]?.objectValue ?? JSONObject()
                let line: Int = source["line"]?.intValue ?? 1
                let col: Int = source["col"]?.intValue ?? 1
                let message: String = "About \(Int(work.rounded(.toNearestOrEven))) s of work in a \(Int(interval.rounded(.toNearestOrEven))) s interval."
                diags.add("W102", message, Span(line, col, 0, file), "lower the reps or lengthen the interval")
            }
        }
        for child in items(of: block) {
            intervalWarning(child, catalog, diags, file)
        }
    }

    private static func mmss(_ seconds: Double) -> String {
        let whole: Int = Int(seconds.rounded(.toNearestOrEven))
        return String(format: "%d:%02d", whole / 60, whole % 60)
    }
}
