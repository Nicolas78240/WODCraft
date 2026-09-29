/// The movement catalog and the unit equivalence table (SPEC §11).
///
/// This is a faithful port of `src/wodcraft/catalog/__init__.py`, reading the JSON snapshot
/// embedded in the package instead of the TOML sources. Everything here is immutable and
/// `Sendable`: `Catalog.shared` is a lazily initialized global constant, not mutable state.
import Foundation

// MARK: - Language

/// The languages the catalog can display a movement in.
public enum Language: String, Codable, Sendable, CaseIterable {
    case en
    case fr
}

// MARK: - Family

/// The three CrossFit modalities: metabolic, gymnastics, weightlifting.
public enum MovementFamily: String, Codable, Sendable, CaseIterable {
    case metabolic = "M"
    case gymnastics = "G"
    case weightlifting = "W"
}

/// A shorter spelling for `MovementFamily`, for call sites such as `catalog.search(_:family:)`.
public typealias Family = MovementFamily

// MARK: - Rx prescription

/// The usual Rx load for a movement, as the catalog records it.
public struct MovementRx: Codable, Equatable, Sendable {
    public var men: Double?
    public var women: Double?
    public var unit: String?

    public init(men: Double? = nil, women: Double? = nil, unit: String? = nil) {
        self.men = men
        self.women = women
        self.unit = unit
    }
}

// MARK: - Movement

/// One catalog entry.
public struct CatalogMovement: Codable, Equatable, Sendable, Identifiable {
    /// The catalog identifier, e.g. `pull_up`.
    public let id: String
    /// The English display name.
    public let name: String
    public let family: MovementFamily
    /// Accepted quantity kinds: `reps`, `distance`, `calories`, `time`.
    public let quantities: [String]
    /// Accepted parameter kinds: `load`, `height` (empty means none).
    public let params: [String]
    public let equipment: String
    /// English aliases.
    public let aliases: [String]
    /// French aliases.
    public let fr: [String]
    /// The French display name; defaults to the first French alias, capitalized.
    public let frName: String?
    public let rx: MovementRx?
    /// Seconds per rep / metre / calorie, keyed by `rep`, `m`, `cal`.
    public let pace: [String: Double]

    enum CodingKeys: String, CodingKey {
        case id, name, family, quantities, params, equipment, aliases, fr, rx, pace
        case frName = "fr_name"
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        family = try container.decodeIfPresent(MovementFamily.self, forKey: .family) ?? .gymnastics
        quantities = try container.decodeIfPresent([String].self, forKey: .quantities) ?? ["reps"]
        params = try container.decodeIfPresent([String].self, forKey: .params) ?? []
        equipment = try container.decodeIfPresent(String.self, forKey: .equipment) ?? "other"
        aliases = try container.decodeIfPresent([String].self, forKey: .aliases) ?? []
        fr = try container.decodeIfPresent([String].self, forKey: .fr) ?? []
        frName = try container.decodeIfPresent(String.self, forKey: .frName)
        rx = try container.decodeIfPresent(MovementRx.self, forKey: .rx)
        pace = try container.decodeIfPresent([String: Double].self, forKey: .pace) ?? [:]
    }

    /// The name to show, in English or in French.
    public func displayName(_ language: Language = .en) -> String {
        if language == .fr {
            if let frName = frName, !frName.isEmpty { return frName }
            if let first = fr.first, !first.isEmpty {
                return first.prefix(1).uppercased() + first.dropFirst()
            }
        }
        return name
    }

    /// Seconds per unit of work for a quantity kind (`reps`, `distance`, `calories`).
    public func pace(forQuantity kind: String) -> Double? {
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

// MARK: - UnitEquivalences

/// The usage equivalence table: 95 lb is written 43 kg in Europe, not 43.09 kg.
public struct UnitEquivalences: Equatable, Sendable {
    /// Bidirectional (kg, lb) pairs.
    public let load: [(kg: Double, lb: Double)]
    /// Bidirectional (cm, in) pairs.
    public let height: [(cm: Double, inches: Double)]

    public init(load: [(kg: Double, lb: Double)] = [], height: [(cm: Double, inches: Double)] = []) {
        self.load = load
        self.height = height
    }

    public static func == (lhs: UnitEquivalences, rhs: UnitEquivalences) -> Bool {
        guard lhs.load.count == rhs.load.count, lhs.height.count == rhs.height.count else { return false }
        for index in lhs.load.indices where lhs.load[index] != rhs.load[index] { return false }
        for index in lhs.height.indices where lhs.height[index] != rhs.height[index] { return false }
        return true
    }

    /// The tabled pound value for a kilogram value, or `nil` when the table has no entry.
    public func tabledKilogramsToPounds(_ kg: Double) -> Double? {
        for pair in load where abs(pair.kg - kg) < 1e-9 { return pair.lb }
        return nil
    }

    public func tabledPoundsToKilograms(_ lb: Double) -> Double? {
        for pair in load where abs(pair.lb - lb) < 1e-9 { return pair.kg }
        return nil
    }

    public func tabledCentimetresToInches(_ cm: Double) -> Double? {
        for pair in height where abs(pair.cm - cm) < 1e-9 { return pair.inches }
        return nil
    }

    public func tabledInchesToCentimetres(_ inches: Double) -> Double? {
        for pair in height where abs(pair.inches - inches) < 1e-9 { return pair.cm }
        return nil
    }

    /// Kilograms to pounds: the table first, then arithmetic rounded to the pound.
    public func kilogramsToPounds(_ kg: Double) -> Double {
        if let exact = tabledKilogramsToPounds(kg) { return exact }
        return Conversion.pythonRound(kg / Conversion.kilogramsPerPound)
    }

    /// Pounds to kilograms: the table first, then arithmetic rounded to the half kilo.
    public func poundsToKilograms(_ lb: Double) -> Double {
        if let exact = tabledPoundsToKilograms(lb) { return exact }
        return Conversion.pythonRound(lb * Conversion.kilogramsPerPound * 2) / 2
    }

    /// Centimetres to inches: the table first, then arithmetic rounded to the inch.
    public func centimetresToInches(_ cm: Double) -> Double {
        if let exact = tabledCentimetresToInches(cm) { return exact }
        return Conversion.pythonRound(cm / Conversion.centimetresPerInch)
    }

    /// Inches to centimetres: the table first, then arithmetic rounded to the centimetre.
    public func inchesToCentimetres(_ inches: Double) -> Double {
        if let exact = tabledInchesToCentimetres(inches) { return exact }
        return Conversion.pythonRound(inches * Conversion.centimetresPerInch)
    }
}

// MARK: - Conversion

/// Shared conversion constants and the numeric formatting rules the emitters rely on.
public enum Conversion {
    public static let kilogramsPerPound = 0.45359237
    public static let kilogramsPerPood = 16.0
    public static let centimetresPerInch = 2.54

    /// Python's `round()`: ties go to the even neighbour.
    public static func pythonRound(_ value: Double) -> Double {
        return value.rounded(.toNearestOrEven)
    }

    /// Python's `round(value, digits)`.
    public static func pythonRound(_ value: Double, _ digits: Int) -> Double {
        let factor = pow(10.0, Double(digits))
        let scaled = value * factor
        // Guard against the binary representation nudging an exact tie the wrong way.
        let nudged = (scaled * 1e9).rounded() / 1e9
        return nudged.rounded(.toNearestOrEven) / factor
    }
}

// MARK: - Catalog

/// The movement catalog: lookup by identifier, by written name, and unit conversions.
public struct Catalog: Sendable {
    /// Every movement, keyed by identifier.
    public let movements: [String: CatalogMovement]
    /// Identifiers in catalog order, so listings are stable.
    public let identifiers: [String]
    /// Normalized alias -> movement identifier.
    public let index: [String: String]
    /// Accent-folded alias -> movement identifier, used only when the strict index misses.
    private let foldedIndex: [String: String]
    public let equivalences: UnitEquivalences

    /// The catalog embedded in the package. Loaded once, on first use.
    public static let shared: Catalog = {
        do {
            return try Catalog.embedded()
        } catch {
            return Catalog(movements: [:], identifiers: [], index: [:], foldedIndex: [:], equivalences: UnitEquivalences())
        }
    }()

    init(
        movements: [String: CatalogMovement],
        identifiers: [String],
        index: [String: String],
        foldedIndex: [String: String],
        equivalences: UnitEquivalences
    ) {
        self.movements = movements
        self.identifiers = identifiers
        self.index = index
        self.foldedIndex = foldedIndex
        self.equivalences = equivalences
    }

    public var count: Int { movements.count }

    /// All movements, in catalog order.
    public var all: [CatalogMovement] {
        var result: [CatalogMovement] = []
        result.reserveCapacity(identifiers.count)
        for identifier in identifiers {
            if let movement = movements[identifier] { result.append(movement) }
        }
        return result
    }

    // MARK: Loading

    /// Decode the catalog from `Resources/catalog.json`.
    public static func embedded() throws -> Catalog {
        return try Catalog(data: try EmbeddedResource.data(named: "catalog"))
    }

    public init(data: Data) throws {
        let file = try JSONDecoder().decode(CatalogFile.self, from: data)
        var movements: [String: CatalogMovement] = [:]
        var identifiers: [String] = []
        var index: [String: String] = [:]
        var folded: [String: String] = [:]
        for movement in file.movements {
            movements[movement.id] = movement
            identifiers.append(movement.id)
            var keys: [String] = [movement.name, movement.id.replacingOccurrences(of: "_", with: " ")]
            keys.append(contentsOf: movement.aliases)
            keys.append(contentsOf: movement.fr)
            for key in keys {
                let normalized = Catalog.normalize(key)
                if index[normalized] == nil { index[normalized] = movement.id }
                let foldedKey = Catalog.fold(normalized)
                if folded[foldedKey] == nil { folded[foldedKey] = movement.id }
            }
        }
        var loadPairs: [(kg: Double, lb: Double)] = []
        for row in file.equivalences?.load ?? [] {
            loadPairs.append((kg: row.kg, lb: row.lb))
        }
        var heightPairs: [(cm: Double, inches: Double)] = []
        for row in file.equivalences?.height ?? [] {
            heightPairs.append((cm: row.cm, inches: row.inches))
        }
        self.init(
            movements: movements,
            identifiers: identifiers,
            index: index,
            foldedIndex: folded,
            equivalences: UnitEquivalences(load: loadPairs, height: heightPairs)
        )
    }

    // MARK: Normalization

    /// Lower-case, collapse spaces and hyphens, drop a trailing plural `s`.
    ///
    /// The exact rule of `wodcraft.catalog.normalize`, so both implementations index the
    /// same keys.
    public static func normalize(_ name: String) -> String {
        var text = name.lowercased()
        text = text.replacingOccurrences(of: "-", with: " ")
        text = text.replacingOccurrences(of: "\u{2019}", with: "'")
        var words: [String] = []
        for piece in text.split(whereSeparator: { $0 == " " || $0 == "\t" || $0 == "\n" || $0 == "\r" }) {
            words.append(String(piece))
        }
        if var last = words.last, last.count > 2, last.hasSuffix("s"), !last.hasSuffix("ss") {
            last.removeLast()
            words[words.count - 1] = last
        }
        return words.joined(separator: " ")
    }

    /// Strip the accents of an already normalized key, so `soulevé` also answers to `souleve`.
    static func fold(_ normalized: String) -> String {
        return normalized.folding(options: [.diacriticInsensitive], locale: Locale(identifier: "en_US_POSIX"))
    }

    // MARK: Lookup

    /// One movement by catalog identifier.
    public func movement(id: String) -> CatalogMovement? {
        return movements[id]
    }

    /// One movement by written name or alias, English or French.
    public func resolve(name: String) -> CatalogMovement? {
        let key = Catalog.normalize(name)
        if let identifier = index[key] { return movements[identifier] }
        if let identifier = foldedIndex[Catalog.fold(key)] { return movements[identifier] }
        return nil
    }

    /// The display name of a movement, falling back to the identifier when it is unknown.
    public func displayName(for id: String, language: Language = .en) -> String {
        guard let movement = movements[id] else {
            return id.replacingOccurrences(of: "_", with: " ")
        }
        return movement.displayName(language)
    }

    /// Free-text search over identifiers, names and aliases.
    ///
    /// Exact matches come first, then prefixes, then substrings; ties keep catalog order.
    public func search(_ query: String, family: MovementFamily? = nil, limit: Int = 20) -> [CatalogMovement] {
        let needle = Catalog.fold(Catalog.normalize(query))
        var scored: [(rank: Int, position: Int, movement: CatalogMovement)] = []
        for (position, identifier) in identifiers.enumerated() {
            guard let movement = movements[identifier] else { continue }
            if let family = family, movement.family != family { continue }
            if needle.isEmpty {
                scored.append((3, position, movement))
                continue
            }
            var best = Int.max
            var keys: [String] = [movement.name, movement.id.replacingOccurrences(of: "_", with: " ")]
            keys.append(contentsOf: movement.aliases)
            keys.append(contentsOf: movement.fr)
            if let frName = movement.frName { keys.append(frName) }
            for key in keys {
                let candidate = Catalog.fold(Catalog.normalize(key))
                if candidate == needle {
                    best = min(best, 0)
                } else if candidate.hasPrefix(needle) {
                    best = min(best, 1)
                } else if candidate.contains(needle) {
                    best = min(best, 2)
                }
            }
            if best != Int.max { scored.append((best, position, movement)) }
        }
        scored.sort { left, right in
            if left.rank != right.rank { return left.rank < right.rank }
            return left.position < right.position
        }
        var result: [CatalogMovement] = []
        for entry in scored {
            if result.count >= limit { break }
            result.append(entry.movement)
        }
        return result
    }

    /// Close names for an unknown movement, by edit distance over the alias index.
    public func suggestions(for name: String, limit: Int = 3) -> [String] {
        let needle = Catalog.fold(Catalog.normalize(name))
        guard !needle.isEmpty else { return [] }
        var scored: [(score: Double, key: String, identifier: String)] = []
        for (key, identifier) in foldedIndex {
            let similarity = Catalog.similarity(needle, key)
            if similarity >= 0.7 { scored.append((similarity, key, identifier)) }
        }
        scored.sort { left, right in
            if left.score != right.score { return left.score > right.score }
            return left.key < right.key
        }
        var seen: [String] = []
        for entry in scored {
            if seen.count >= limit { break }
            guard let movement = movements[entry.identifier] else { continue }
            if !seen.contains(movement.name) { seen.append(movement.name) }
        }
        return seen
    }

    /// 1 minus the normalized Levenshtein distance.
    static func similarity(_ left: String, _ right: String) -> Double {
        if left == right { return 1.0 }
        let longest = max(left.count, right.count)
        if longest == 0 { return 1.0 }
        let distance = Double(levenshtein(left, right))
        return 1.0 - distance / Double(longest)
    }

    static func levenshtein(_ left: String, _ right: String) -> Int {
        let a = Array(left)
        let b = Array(right)
        if a.isEmpty { return b.count }
        if b.isEmpty { return a.count }
        var previous: [Int] = []
        previous.reserveCapacity(b.count + 1)
        for index in 0...b.count { previous.append(index) }
        var current = previous
        for i in 1...a.count {
            current[0] = i
            for j in 1...b.count {
                let cost = a[i - 1] == b[j - 1] ? 0 : 1
                let deletion = previous[j] + 1
                let insertion = current[j - 1] + 1
                let substitution = previous[j - 1] + cost
                current[j] = min(deletion, min(insertion, substitution))
            }
            previous = current
        }
        return previous[b.count]
    }

    // MARK: Conversions

    public func kilogramsToPounds(_ kg: Double) -> Double { return equivalences.kilogramsToPounds(kg) }
    public func poundsToKilograms(_ lb: Double) -> Double { return equivalences.poundsToKilograms(lb) }
    public func centimetresToInches(_ cm: Double) -> Double { return equivalences.centimetresToInches(cm) }
    public func inchesToCentimetres(_ inches: Double) -> Double { return equivalences.inchesToCentimetres(inches) }
}

// MARK: - Errors and wire format

public enum CatalogError: Error, CustomStringConvertible {
    case resourceMissing(String)

    public var description: String {
        switch self {
        case let .resourceMissing(name): return "the resource \(name) is missing from the bundle"
        }
    }
}

/// Reads a JSON resource from the package bundle, whichever layout the build produced.
enum EmbeddedResource {
    static func data(named name: String) throws -> Data {
        let bundle = Bundle.module
        if let url = bundle.url(forResource: name, withExtension: "json"),
           let data = try? Data(contentsOf: url) {
            return data
        }
        if let url = bundle.url(forResource: name, withExtension: "json", subdirectory: "Resources"),
           let data = try? Data(contentsOf: url) {
            return data
        }
        let direct = bundle.bundleURL.appendingPathComponent("Resources/" + name + ".json")
        if let data = try? Data(contentsOf: direct) { return data }
        throw CatalogError.resourceMissing(name + ".json")
    }
}

struct CatalogFile: Decodable {
    struct LoadPair: Decodable {
        let kg: Double
        let lb: Double
    }

    struct HeightPair: Decodable {
        let cm: Double
        let inches: Double

        enum CodingKeys: String, CodingKey {
            case cm
            case inches = "in"
        }
    }

    struct EquivalenceTable: Decodable {
        let load: [LoadPair]?
        let height: [HeightPair]?
    }

    let wodcraft: String?
    let movements: [CatalogMovement]
    let equivalences: EquivalenceTable?
}
