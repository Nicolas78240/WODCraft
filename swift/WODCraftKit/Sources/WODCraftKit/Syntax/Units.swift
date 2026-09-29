/// Unit vocabulary shared by the parser and the semantic stages (SPEC §2.2).
import Foundation

enum Units {
    static let loadUnits: [String: String] = [
        "kg": "kg", "kgs": "kg",
        "lb": "lb", "lbs": "lb",
        "pood": "pood", "poods": "pood",
    ]

    static let heightUnits: [String: String] = [
        "in": "in", "inch": "in", "inches": "in",
        "cm": "cm", "\"": "in",
    ]

    static let distanceUnits: [String: String] = [
        "m": "m", "km": "km",
        "mi": "mi", "mile": "mi", "miles": "mi",
        "ft": "ft", "foot": "ft", "feet": "ft",
    ]

    static let calorieUnits: [String: String] = [
        "cal": "cal", "cals": "cal",
        "calorie": "cal", "calories": "cal",
    ]

    static let timeUnits: [String: String] = [
        "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s",
        "min": "min", "mins": "min", "minute": "min", "minutes": "min",
    ]

    static let kgPerLb: Double = 0.45359237
    static let kgPerPood: Double = 16.0
    static let cmPerIn: Double = 2.54
    static let metresPer: [String: Double] = ["m": 1.0, "km": 1000.0, "mi": 1609.344, "ft": 0.3048]

    /// `(kind, canonical unit)` for a unit word, or nil.
    static func unitKind(_ word: String) -> (kind: String, unit: String)? {
        let lowered: String = word.lowercased()
        if let unit = loadUnits[lowered] { return ("load", unit) }
        if let unit = heightUnits[lowered] { return ("height", unit) }
        if let unit = distanceUnits[lowered] { return ("distance", unit) }
        if let unit = calorieUnits[lowered] { return ("calories", unit) }
        if let unit = timeUnits[lowered] { return ("time", unit) }
        return nil
    }

    static func seconds(_ value: Double, _ unit: String) -> Double {
        unit == "min" ? value * 60 : value
    }

    static func parseClock(_ text: String) -> Double {
        var total: Int = 0
        for part in text.split(separator: ":") {
            total = total * 60 + (Int(part) ?? 0)
        }
        return Double(total)
    }

    static func formatClock(_ total: Double) -> String {
        let whole: Int = Int(total.rounded())
        let hours: Int = whole / 3600
        let minutes: Int = (whole % 3600) / 60
        let seconds: Int = whole % 60
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, seconds)
        }
        return String(format: "%d:%02d", minutes, seconds)
    }

    static func formatNumber(_ value: Double) -> String {
        if value == value.rounded() { return String(Int(value)) }
        return String(format: "%g", value)
    }
}
