/// The athlete profile: category, level, preferred units and one-rep maxes (SPEC §14).
///
/// A port of `src/wodcraft/profile.py`.
import Foundation

/// The unit system the athlete reads loads in.
public enum UnitSystem: String, Codable, Sendable, CaseIterable {
    case kg
    case lb

    /// The height unit that goes with the system.
    public var heightUnit: String { self == .lb ? "in" : "cm" }
}

/// The scaling levels of the standard, from hardest to easiest (SPEC §14).
public enum AthleteLevel: String, Codable, Sendable, CaseIterable {
    case rx
    case intermediate
    case scaled
    case foundations
}

/// One athlete: how a workout should be read for them.
public struct AthleteProfile: Codable, Equatable, Sendable {
    /// `men` or `women`: which side of a dual such as `95/65 lb` applies.
    public var category: Amount.Category
    public var level: AthleteLevel
    public var units: UnitSystem
    public var bodyweightKg: Double?
    /// One-rep maxes in kilograms, keyed by movement identifier (lower-cased).
    public var oneRepMax: [String: Double]
    public var name: String?

    public init(
        category: Amount.Category = .men,
        level: AthleteLevel = .rx,
        units: UnitSystem = .kg,
        bodyweightKg: Double? = nil,
        oneRepMax: [String: Double] = [:],
        name: String? = nil
    ) {
        self.category = category
        self.level = level
        self.units = units
        self.bodyweightKg = bodyweightKg
        self.oneRepMax = [:]
        for (key, value) in oneRepMax { self.oneRepMax[key.lowercased()] = value }
        self.name = name
    }

    /// The default profile: an Rx man reading kilograms.
    public static let `default` = AthleteProfile()

    /// A copy with the given fields replaced — what a CLI flag or a picker does.
    public func with(
        category: Amount.Category? = nil,
        level: AthleteLevel? = nil,
        units: UnitSystem? = nil
    ) -> AthleteProfile {
        var copy = self
        if let category = category { copy.category = category }
        if let level = level { copy.level = level }
        if let units = units { copy.units = units }
        return copy
    }

    /// The one-rep max of a movement, in kilograms.
    public func oneRepMax(of movement: String) -> Double? {
        return oneRepMax[movement.lowercased()]
    }

    /// The asked level, then the closest ones, ending with Rx (SPEC §14).
    ///
    /// `scaled` yields `scaled, foundations, intermediate, rx`: go easier first, then walk
    /// back up.
    public func levelsToTry() -> [AthleteLevel] {
        let order = AthleteLevel.allCases
        guard let index = order.firstIndex(of: level) else { return [level, .rx] }
        var result: [AthleteLevel] = []
        for position in index..<order.count { result.append(order[position]) }
        var position = index - 1
        while position >= 0 {
            result.append(order[position])
            position -= 1
        }
        return result
    }
}
