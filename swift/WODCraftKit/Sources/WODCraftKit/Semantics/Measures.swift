/// Normalization of written values into the compiled JSON representation (SPEC §13).
import Foundation

enum Measures {
    /// A single number, or `{"men": …, "women": …}` when the value was written as a dual.
    static func amount(_ value: Dual) -> JSONValue {
        if value.isDual {
            var object = JSONObject()
            object["men"] = .number(round3(value.men))
            object["women"] = .number(round3(value.women))
            return .object(object)
        }
        return .number(round3(value.men))
    }

    static func mapAmount(_ value: JSONValue, _ transform: (Double) -> Double) -> JSONValue {
        if let object = value.objectValue {
            var out = JSONObject()
            for key in object.keys {
                let number: Double = object[key]?.doubleValue ?? 0
                out[key] = .number(round3(transform(number)))
            }
            return .object(out)
        }
        return .number(round3(transform(value.doubleValue ?? 0)))
    }

    static func pick(_ value: JSONValue, _ category: String) -> Double {
        if let object = value.objectValue {
            return object[category]?.doubleValue ?? 0
        }
        return value.doubleValue ?? 0
    }

    static func round3(_ value: Double) -> Double {
        (value * 1000).rounded(.toNearestOrEven) / 1000
    }

    /// Loads are exposed in kg and lb, using the equivalence table first.
    static func loadToJSON(_ value: Dual, _ unit: String, _ eq: Equivalences) -> JSONObject {
        let written: JSONValue = amount(value)
        var out = JSONObject()
        if unit == "pood" {
            let kg: JSONValue = mapAmount(written) { $0 * Units.kgPerPood }
            out["kg"] = kg
            out["lb"] = mapAmount(kg) { kgToLb($0, eq) }
            out["unit"] = .string("pood")
            out["written"] = written
            return out
        }
        if unit == "lb" {
            out["kg"] = mapAmount(written) { lbToKg($0, eq) }
            out["lb"] = written
            out["unit"] = .string("lb")
            out["written"] = written
            return out
        }
        out["kg"] = written
        out["lb"] = mapAmount(written) { kgToLb($0, eq) }
        out["unit"] = .string("kg")
        out["written"] = written
        return out
    }

    static func heightToJSON(_ value: Dual, _ unit: String, _ eq: Equivalences) -> JSONObject {
        let written: JSONValue = amount(value)
        var out = JSONObject()
        if unit == "in" {
            out["cm"] = mapAmount(written) { eq.inToCm($0) ?? ($0 * Units.cmPerIn).rounded(.toNearestOrEven) }
            out["in"] = written
            out["unit"] = .string("in")
            out["written"] = written
            return out
        }
        out["cm"] = written
        out["in"] = mapAmount(written) { eq.cmToIn($0) ?? ($0 / Units.cmPerIn).rounded(.toNearestOrEven) }
        out["unit"] = .string("cm")
        out["written"] = written
        return out
    }

    static func distanceToJSON(_ value: Dual, _ unit: String) -> JSONObject {
        let factor: Double = Units.metresPer[unit] ?? 1.0
        let written: JSONValue = amount(value)
        var out = JSONObject()
        out["m"] = mapAmount(written) { $0 * factor }
        out["unit"] = .string(unit)
        out["written"] = written
        return out
    }

    private static func kgToLb(_ kg: Double, _ eq: Equivalences) -> Double {
        if let exact = eq.kgToLb(kg) { return exact }
        return (kg / Units.kgPerLb).rounded(.toNearestOrEven)
    }

    private static func lbToKg(_ lb: Double, _ eq: Equivalences) -> Double {
        if let exact = eq.lbToKg(lb) { return exact }
        return (lb * Units.kgPerLb * 2).rounded(.toNearestOrEven) / 2
    }
}
