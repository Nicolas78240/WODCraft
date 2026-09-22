/// A minimal JSON tree. The compiler builds documents as JSON, exactly like the reference
/// implementation, and the typed `Document` model is decoded from it at the end.
import Foundation

indirect enum JSONValue: Equatable, Sendable {
    case null
    case bool(Bool)
    case number(Double)
    case string(String)
    case array([JSONValue])
    /// Insertion-ordered so the emitted JSON reads like the reference implementation's.
    case object(JSONObject)

    var objectValue: JSONObject? {
        if case let .object(value) = self { return value }
        return nil
    }

    var arrayValue: [JSONValue]? {
        if case let .array(value) = self { return value }
        return nil
    }

    var stringValue: String? {
        if case let .string(value) = self { return value }
        return nil
    }

    var doubleValue: Double? {
        if case let .number(value) = self { return value }
        return nil
    }

    var intValue: Int? {
        if case let .number(value) = self { return Int(value) }
        return nil
    }

    var isNull: Bool {
        if case .null = self { return true }
        return false
    }

    /// Foundation object, ready for `JSONSerialization`.
    var foundation: Any {
        switch self {
        case .null:
            return NSNull()
        case let .bool(value):
            return value
        case let .number(value):
            if value == value.rounded() && abs(value) < 1e15 {
                return NSNumber(value: Int(value))
            }
            return NSNumber(value: value)
        case let .string(value):
            return value
        case let .array(values):
            return values.map(\.foundation)
        case let .object(object):
            var out: [String: Any] = [:]
            for key in object.keys {
                out[key] = object[key]?.foundation ?? NSNull()
            }
            return out
        }
    }

    static func from(_ any: Any) -> JSONValue {
        if any is NSNull { return .null }
        if let number = any as? NSNumber {
            if CFGetTypeID(number) == CFBooleanGetTypeID() { return .bool(number.boolValue) }
            return .number(number.doubleValue)
        }
        if let text = any as? String { return .string(text) }
        if let list = any as? [Any] { return .array(list.map(JSONValue.from)) }
        if let map = any as? [String: Any] {
            var object = JSONObject()
            for key in map.keys.sorted() {
                object[key] = JSONValue.from(map[key] as Any)
            }
            return .object(object)
        }
        return .null
    }
}

/// An insertion-ordered string-keyed map of JSON values.
struct JSONObject: Equatable, Sendable {
    private(set) var keys: [String] = []
    private var storage: [String: JSONValue] = [:]

    init() {}

    init(_ pairs: [(String, JSONValue)]) {
        for pair in pairs {
            self[pair.0] = pair.1
        }
    }

    subscript(key: String) -> JSONValue? {
        get { storage[key] }
        set {
            if let newValue {
                if storage[key] == nil { keys.append(key) }
                storage[key] = newValue
            } else if storage[key] != nil {
                storage[key] = nil
                keys.removeAll { $0 == key }
            }
        }
    }

    func has(_ key: String) -> Bool {
        storage[key] != nil
    }

    var isEmpty: Bool {
        keys.isEmpty
    }

    /// Sets `key` only when it is not there yet (Python's `dict.setdefault`).
    mutating func setDefault(_ key: String, _ value: JSONValue) {
        if storage[key] == nil {
            self[key] = value
        }
    }

    @discardableResult
    mutating func removeValue(forKey key: String) -> JSONValue? {
        let previous = storage[key]
        if previous != nil {
            storage[key] = nil
            keys.removeAll { $0 == key }
        }
        return previous
    }

    /// Merges `other` on top of this object, keeping this object's key order first.
    func merging(_ other: JSONObject) -> JSONObject {
        var out = self
        for key in other.keys {
            out[key] = other[key]
        }
        return out
    }
}
