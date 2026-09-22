/// Movement catalog and unit equivalences (part of the standard, see SPEC §11).
///
/// The TOML files of the reference implementation are shipped here as one `catalog.json`.
import Foundation

public struct MovementEntry: Sendable, Equatable {
    public let id: String
    public let name: String
    /// M monostructural | G gymnastics | W weightlifting
    public let family: String
    /// reps | distance | calories | time
    public let quantities: [String]
    /// accepted parameter kinds: load, height (empty = none)
    public let params: [String]
    public let equipment: String
    public let aliases: [String]
    public let fr: [String]
    /// French display name; defaults to the first French alias
    public let frName: String?
    /// `["men": 43, "women": 30]` plus `unit`
    public let rx: [String: Double]?
    public let rxUnit: String?
    /// seconds per rep / m / cal
    public let pace: [String: Double]

    public func displayName(lang: String = "en") -> String {
        if lang == "fr" {
            if let frName { return frName }
            if let first = fr.first {
                return first.prefix(1).uppercased() + first.dropFirst()
            }
        }
        return name
    }

    func pace(for kind: String) -> Double? {
        let key: String
        switch kind {
        case "reps": key = "rep"
        case "distance": key = "m"
        case "calories": key = "cal"
        default: key = kind
        }
        return pace[key]
    }
}

public struct Equivalences: Sendable, Equatable {
    /// (kg, lb)
    public let load: [(kg: Double, lb: Double)]
    /// (cm, in)
    public let height: [(cm: Double, inches: Double)]

    public static func == (lhs: Equivalences, rhs: Equivalences) -> Bool {
        lhs.load.map(\.kg) == rhs.load.map(\.kg) && lhs.height.map(\.cm) == rhs.height.map(\.cm)
    }

    static let empty = Equivalences(load: [], height: [])

    func kgToLb(_ kg: Double) -> Double? {
        load.first { abs($0.kg - kg) < 1e-9 }?.lb
    }

    func lbToKg(_ lb: Double) -> Double? {
        load.first { abs($0.lb - lb) < 1e-9 }?.kg
    }

    func cmToIn(_ cm: Double) -> Double? {
        height.first { abs($0.cm - cm) < 1e-9 }?.inches
    }

    func inToCm(_ inches: Double) -> Double? {
        height.first { abs($0.inches - inches) < 1e-9 }?.cm
    }
}

public struct MovementCatalog: Sendable {
    public let movements: [String: MovementEntry]
    /// normalized alias -> movement id
    let index: [String: String]
    /// insertion order of `index`, so suggestions are stable
    let indexOrder: [String]
    public let equivalences: Equivalences

    public var count: Int { movements.count }

    public func get(_ name: String) -> MovementEntry? {
        guard let id = index[MovementCatalog.normalize(name)] else { return nil }
        return movements[id]
    }

    /// Lower-case, collapse spaces/hyphens and drop a trailing plural 's'.
    public static func normalize(_ name: String) -> String {
        var lowered: String = name.lowercased()
        lowered = lowered.replacingOccurrences(of: "-", with: " ")
        lowered = lowered.replacingOccurrences(of: "\u{2019}", with: "'")
        var words: [String] = lowered.split(whereSeparator: { $0 == " " || $0 == "\t" || $0 == "\n" }).map(String.init)
        if var last = words.last, last.count > 2, last.hasSuffix("s"), !last.hasSuffix("ss") {
            last.removeLast()
            words[words.count - 1] = last
        }
        return words.joined(separator: " ")
    }

    public func suggest(_ name: String, _ n: Int = 3) -> [String] {
        let needle: String = MovementCatalog.normalize(name)
        var scored: [(score: Double, alias: String)] = []
        for alias in indexOrder {
            let score: Double = MovementCatalog.ratio(needle, alias)
            if score >= 0.7 {
                scored.append((score, alias))
            }
        }
        scored.sort { $0.score > $1.score }
        var seen: [String] = []
        for entry in scored.prefix(max(n, 0) * 3) {
            guard let id = index[entry.alias], let movement = movements[id] else { continue }
            if !seen.contains(movement.name) {
                seen.append(movement.name)
            }
            if seen.count >= n { break }
        }
        return seen
    }

    /// `difflib.SequenceMatcher.ratio()`: twice the matched characters over the total length.
    static func ratio(_ a: String, _ b: String) -> Double {
        let left: [Character] = Array(a)
        let right: [Character] = Array(b)
        let total: Int = left.count + right.count
        guard total > 0 else { return 1.0 }
        let matched: Int = matchingCount(left, 0, left.count, right, 0, right.count)
        return 2.0 * Double(matched) / Double(total)
    }

    private static func matchingCount(
        _ a: [Character], _ aLow: Int, _ aHigh: Int,
        _ b: [Character], _ bLow: Int, _ bHigh: Int
    ) -> Int {
        guard aLow < aHigh, bLow < bHigh else { return 0 }
        var bestI: Int = aLow
        var bestJ: Int = bLow
        var bestSize: Int = 0
        var lengths: [Int: Int] = [:]
        for i in aLow..<aHigh {
            var next: [Int: Int] = [:]
            for j in bLow..<bHigh where a[i] == b[j] {
                let length: Int = (lengths[j - 1] ?? 0) + 1
                next[j] = length
                if length > bestSize {
                    bestI = i - length + 1
                    bestJ = j - length + 1
                    bestSize = length
                }
            }
            lengths = next
        }
        guard bestSize > 0 else { return 0 }
        let before: Int = matchingCount(a, aLow, bestI, b, bLow, bestJ)
        let after: Int = matchingCount(a, bestI + bestSize, aHigh, b, bestJ + bestSize, bHigh)
        return before + bestSize + after
    }
}

// MARK: - loading

extension MovementCatalog {
    public static let shared: MovementCatalog = load()

    static func load() -> MovementCatalog {
        guard let data = ResourceLoader.data(named: "catalog") else {
            return MovementCatalog(movements: [:], index: [:], indexOrder: [], equivalences: .empty)
        }
        return decode(data)
    }

    static func decode(_ data: Data) -> MovementCatalog {
        let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        var movements: [String: MovementEntry] = [:]
        var index: [String: String] = [:]
        var order: [String] = []
        let rawMovements: [[String: Any]] = root["movements"] as? [[String: Any]] ?? []
        for raw in rawMovements {
            guard let id = raw["id"] as? String else { continue }
            let entry = decodeMovement(id: id, raw: raw)
            movements[id] = entry
            var aliases: [String] = [entry.name, id.replacingOccurrences(of: "_", with: " ")]
            aliases.append(contentsOf: entry.aliases)
            aliases.append(contentsOf: entry.fr)
            for alias in aliases {
                let key: String = normalize(alias)
                if index[key] == nil {
                    index[key] = id
                    order.append(key)
                }
            }
        }
        let equivalences = decodeEquivalences(root["equivalences"] as? [String: Any] ?? [:])
        return MovementCatalog(movements: movements, index: index, indexOrder: order, equivalences: equivalences)
    }

    private static func decodeMovement(id: String, raw: [String: Any]) -> MovementEntry {
        let name: String = raw["name"] as? String ?? id
        let family: String = raw["family"] as? String ?? "G"
        let quantities: [String] = raw["quantities"] as? [String] ?? ["reps"]
        let params: [String] = (raw["params"] as? [String] ?? []).filter { $0 != "none" }
        let equipment: String = raw["equipment"] as? String ?? "other"
        let aliases: [String] = raw["aliases"] as? [String] ?? []
        let french: [String] = raw["fr"] as? [String] ?? []
        let frName: String? = raw["fr_name"] as? String
        var rx: [String: Double]?
        var rxUnit: String?
        if let rawRx = raw["rx"] as? [String: Any] {
            var values: [String: Double] = [:]
            for key in ["men", "women"] {
                if let number = rawRx[key] as? NSNumber { values[key] = number.doubleValue }
            }
            rx = values
            rxUnit = rawRx["unit"] as? String
        }
        var pace: [String: Double] = [:]
        if let rawPace = raw["pace"] as? [String: Any] {
            for (key, value) in rawPace {
                if let number = value as? NSNumber { pace[key] = number.doubleValue }
            }
        }
        return MovementEntry(
            id: id,
            name: name,
            family: family,
            quantities: quantities,
            params: params,
            equipment: equipment,
            aliases: aliases,
            fr: french,
            frName: frName,
            rx: rx,
            rxUnit: rxUnit,
            pace: pace
        )
    }

    private static func decodeEquivalences(_ raw: [String: Any]) -> Equivalences {
        var load: [(kg: Double, lb: Double)] = []
        for row in raw["load"] as? [[String: Any]] ?? [] {
            guard let kg = (row["kg"] as? NSNumber)?.doubleValue, let lb = (row["lb"] as? NSNumber)?.doubleValue else { continue }
            load.append((kg, lb))
        }
        var height: [(cm: Double, inches: Double)] = []
        for row in raw["height"] as? [[String: Any]] ?? [] {
            guard let cm = (row["cm"] as? NSNumber)?.doubleValue, let inches = (row["in"] as? NSNumber)?.doubleValue else { continue }
            height.append((cm, inches))
        }
        return Equivalences(load: load, height: height)
    }
}

/// Finds a JSON resource in the package bundle, whichever layout SwiftPM produced.
enum ResourceLoader {
    static func data(named name: String) -> Data? {
        let bundle: Bundle = .module
        if let url = bundle.url(forResource: name, withExtension: "json") {
            return try? Data(contentsOf: url)
        }
        if let url = bundle.url(forResource: name, withExtension: "json", subdirectory: "Resources") {
            return try? Data(contentsOf: url)
        }
        let direct = bundle.bundleURL.appendingPathComponent("Resources/\(name).json")
        return try? Data(contentsOf: direct)
    }
}
