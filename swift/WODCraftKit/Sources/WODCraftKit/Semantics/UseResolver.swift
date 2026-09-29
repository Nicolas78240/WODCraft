/// Resolves `use PATH` against the local directory, extra paths and the standard library (SPEC §10).
///
/// The standard library ships pre-compiled in `Resources/library.json`, so `use girls/fran`
/// works offline with no file system at all.
import Foundation

enum LibraryLookup {
    case found(JSONObject, [Diagnostic])
    case cycle
    case notFound
}

/// One entry of the embedded standard library.
public struct LibraryWorkout: Sendable {
    public let path: String
    public let title: String
    public let source: String
    let compiled: JSONObject
}

struct EmbeddedLibrary: Sendable {
    let workouts: [String: LibraryWorkout]
    let order: [String]

    static let shared: EmbeddedLibrary = load()

    static func load() -> EmbeddedLibrary {
        guard let data = ResourceLoader.data(named: "library") else {
            return EmbeddedLibrary(workouts: [:], order: [])
        }
        return decode(data)
    }

    static func decode(_ data: Data) -> EmbeddedLibrary {
        let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        var workouts: [String: LibraryWorkout] = [:]
        var order: [String] = []
        for raw in root["workouts"] as? [[String: Any]] ?? [] {
            guard let path = raw["path"] as? String else { continue }
            let title: String = raw["title"] as? String ?? path
            let source: String = raw["source"] as? String ?? ""
            let compiled: JSONObject = JSONValue.from(raw["compiled"] ?? [:]).objectValue ?? JSONObject()
            workouts[path] = LibraryWorkout(path: path, title: title, source: source, compiled: compiled)
            order.append(path)
        }
        return EmbeddedLibrary(workouts: workouts, order: order)
    }

    func get(_ path: String) -> LibraryWorkout? {
        var key: String = path
        if key.hasSuffix(".wod") {
            key = String(key.dropLast(4))
        }
        return workouts[key]
    }
}

final class WorkoutLibrary {
    /// Directories searched before the standard library.
    var paths: [URL]
    private var stack: [String] = []
    private var cache: [String: (JSONObject, [Diagnostic])] = [:]
    private let catalog: MovementCatalog

    init(paths: [URL] = [], catalog: MovementCatalog = .shared) {
        self.paths = paths
        self.catalog = catalog
    }

    func find(_ path: String) -> URL? {
        let name: String = path.hasSuffix(".wod") ? path : path + ".wod"
        for base in paths {
            let candidate: URL = base.appendingPathComponent(name).standardizedFileURL
            if FileManager.default.fileExists(atPath: candidate.path) {
                return candidate
            }
        }
        return nil
    }

    /// The document and its diagnostics, `.notFound` when unknown, or `.cycle`.
    func load(_ path: String) -> LibraryLookup {
        guard let found = find(path) else {
            if let embedded = EmbeddedLibrary.shared.get(path) {
                return .found(embedded.compiled, [])
            }
            return .notFound
        }
        // cycles and caching follow the file, not the way it was written
        let key: String = found.path
        if stack.contains(key) { return .cycle }
        if let cached = cache[key] { return .found(cached.0, cached.1) }
        guard let text = try? String(contentsOf: found, encoding: .utf8) else { return .notFound }
        stack.append(key)
        let saved: [URL] = paths
        // a used file resolves its own 'use' lines first
        paths = [found.deletingLastPathComponent()] + paths
        let result = compileWithLibrary(text, key, self, catalog: catalog, estimate: true)
        paths = saved
        stack.removeLast()
        let document: JSONObject = result.documents.first ?? JSONObject()
        cache[key] = (document, result.diagnostics)
        return .found(document, result.diagnostics)
    }
}
