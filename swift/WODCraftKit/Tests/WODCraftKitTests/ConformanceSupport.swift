/// Shared helpers for the conformance suite (SPEC §16).
import Foundation
@testable import WODCraftKit

enum Conformance {
    /// The directory holding `NAME.wod` with its `NAME.json` or `NAME.diag`.
    static let directory: URL = {
        let bundle: Bundle = .module
        if let url = bundle.url(forResource: "conformance", withExtension: nil) {
            return url
        }
        return bundle.bundleURL.appendingPathComponent("conformance")
    }()

    struct Case: Sendable, CustomStringConvertible {
        let name: String
        let wod: URL
        let expectation: URL
        let isDiagnostics: Bool

        var description: String { name }
    }

    static let cases: [Case] = {
        let manager = FileManager.default
        let entries: [URL] = (try? manager.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []
        var found: [Case] = []
        for url in entries where url.pathExtension == "wod" {
            let name: String = url.deletingPathExtension().lastPathComponent
            let json: URL = url.deletingPathExtension().appendingPathExtension("json")
            let diag: URL = url.deletingPathExtension().appendingPathExtension("diag")
            if manager.fileExists(atPath: json.path) {
                found.append(Case(name: name, wod: url, expectation: json, isDiagnostics: false))
            } else if manager.fileExists(atPath: diag.path) {
                found.append(Case(name: name, wod: url, expectation: diag, isDiagnostics: true))
            }
        }
        return found.sorted { $0.name < $1.name }
    }()

    /// Every key but `estimate`, so indicative durations stay out of conformance (SPEC §15).
    static func withoutEstimate(_ value: Any) -> Any {
        if let map = value as? [String: Any] {
            var out: [String: Any] = [:]
            for (key, inner) in map where key != "estimate" {
                out[key] = withoutEstimate(inner)
            }
            return out
        }
        if let list = value as? [Any] {
            return list.map(withoutEstimate)
        }
        if let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() {
            // 600 and 600.0 are the same compiled value
            return NSNumber(value: number.doubleValue)
        }
        return value
    }

    static func compiledJSON(_ source: String, file: String?) -> [[String: Any]] {
        let raw = compileRaw(source, file: file)
        return raw.documents.compactMap { JSONValue.object($0).foundation as? [String: Any] }
    }

    /// `CODE LINE` per line, in source order.
    static func expectedDiagnostics(_ url: URL) -> [String] {
        let text: String = (try? String(contentsOf: url, encoding: .utf8)) ?? ""
        return text
            .components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
    }

    static func actualDiagnostics(_ diagnostics: [Diagnostic]) -> [String] {
        diagnostics.map { "\($0.code) \($0.line)" }
    }

    static func describe(_ value: Any) -> String {
        let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .prettyPrinted])
        return data.flatMap { String(data: $0, encoding: .utf8) } ?? "\(value)"
    }

    /// The first path where two JSON trees differ, for a readable failure message.
    static func firstDifference(_ left: Any, _ right: Any, path: String = "") -> String? {
        if let a = left as? [String: Any], let b = right as? [String: Any] {
            for key in Set(a.keys).union(b.keys).sorted() {
                switch (a[key], b[key]) {
                case let (lhs?, rhs?):
                    if let found = firstDifference(lhs, rhs, path: path + "/" + key) { return found }
                case (nil, _?):
                    return "\(path)/\(key): missing on the left"
                case (_?, nil):
                    return "\(path)/\(key): unexpected on the left"
                default:
                    break
                }
            }
            return nil
        }
        if let a = left as? [Any], let b = right as? [Any] {
            if a.count != b.count {
                return "\(path): \(a.count) items vs \(b.count)"
            }
            for (index, pair) in zip(a, b).enumerated() {
                if let found = firstDifference(pair.0, pair.1, path: "\(path)[\(index)]") { return found }
            }
            return nil
        }
        if (left as AnyObject).isEqual(right) { return nil }
        return "\(path): \(left) vs \(right)"
    }
}
