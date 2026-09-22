/// The standard workout library shipped with the package (Girls, Heroes, Open).
///
/// A port of `src/wodcraft/library.py`, reading the JSON snapshot embedded in the package:
/// every entry carries both its WODCraft source and the already compiled document, so an
/// offline application never needs the compiler to display a benchmark.
import Foundation

/// One workout of the standard library.
public struct LibraryEntry: Decodable, Equatable, Sendable, Identifiable {
    /// The library path, e.g. `girls/fran`.
    public let path: String
    public let title: String
    /// The WODCraft source the entry was compiled from.
    public let source: String
    /// The compiled document.
    public let compiled: Document

    public var id: String { path }

    /// The collection the workout belongs to: `girls`, `heroes`, `open`.
    public var collection: String {
        guard let slash = path.firstIndex(of: "/") else { return "" }
        return String(path[path.startIndex..<slash])
    }

    /// The single workout of the entry, when the document is not a session.
    public var workout: Workout? {
        if case let .workout(workout) = compiled { return workout }
        return nil
    }
}

/// The embedded library.
public struct Library: Sendable {
    /// Every entry, in library order (sorted by path).
    public let entries: [LibraryEntry]
    private let byPath: [String: Int]

    /// The library embedded in the package. Loaded once, on first use.
    public static let shared: Library = {
        do {
            return try Library.embedded()
        } catch {
            return Library(entries: [])
        }
    }()

    public init(entries: [LibraryEntry]) {
        self.entries = entries
        var index: [String: Int] = [:]
        for (position, entry) in entries.enumerated() where index[entry.path] == nil {
            index[entry.path] = position
        }
        self.byPath = index
    }

    /// Decode the library from `Resources/library.json`.
    public static func embedded() throws -> Library {
        return try Library(data: try EmbeddedResource.data(named: "library"))
    }

    public init(data: Data) throws {
        let file = try JSONDecoder.wodcraft.decode(LibraryFile.self, from: data)
        self.init(entries: file.workouts)
    }

    public var count: Int { entries.count }

    /// One workout by library path, e.g. `girls/fran`. A trailing `.wod` is accepted.
    public func entry(path: String) -> LibraryEntry? {
        var key = path
        if key.hasSuffix(".wod") { key = String(key.dropLast(4)) }
        guard let position = byPath[key] else { return nil }
        return entries[position]
    }

    /// Entries whose path or title contains the query, case-insensitively.
    public func search(_ query: String) -> [LibraryEntry] {
        let needle = query.lowercased()
        if needle.isEmpty { return entries }
        var found: [LibraryEntry] = []
        for entry in entries {
            if entry.path.lowercased().contains(needle) || entry.title.lowercased().contains(needle) {
                found.append(entry)
            }
        }
        return found
    }

    /// Entries of one collection, e.g. `girls`.
    public func collection(_ name: String) -> [LibraryEntry] {
        let needle = name.lowercased()
        var found: [LibraryEntry] = []
        for entry in entries where entry.collection.lowercased() == needle {
            found.append(entry)
        }
        return found
    }
}

struct LibraryFile: Decodable {
    let wodcraft: String?
    let workouts: [LibraryEntry]
}
