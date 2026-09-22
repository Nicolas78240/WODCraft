/// Public API: compile and check WODCraft sources (SPEC §13).
import Foundation

public struct CompileResult: Sendable {
    public let documents: [Document]
    public let diagnostics: [Diagnostic]

    /// No diagnostic of severity `.error`.
    public var ok: Bool {
        !diagnostics.contains { $0.severity == .error }
    }

    /// The first document, when there is one.
    public var document: Document? {
        documents.first
    }

    public init(documents: [Document], diagnostics: [Diagnostic]) {
        self.documents = documents
        self.diagnostics = diagnostics
    }
}

public enum WODCraft {
    /// Compile a source into one document per `# Title` (SPEC §3).
    ///
    /// `file` names the source for diagnostics; when it is a path on disk, its directory is also
    /// searched by `use` before the embedded standard library.
    public static func compile(_ source: String, file: String? = nil) -> CompileResult {
        let raw: RawCompileResult = compileRaw(source, file: file)
        let documents: [Document] = raw.documents.compactMap(decodeDocument)
        return CompileResult(documents: documents, diagnostics: raw.diagnostics)
    }

    /// The diagnostics of a source, without building the documents.
    public static func check(_ source: String, file: String? = nil) -> [Diagnostic] {
        compileRaw(source, file: file).diagnostics
    }

    /// The pre-compiled standard library (`girls/`, `heroes/`, `open/`), available offline.
    public static var libraryPaths: [String] {
        EmbeddedLibrary.shared.order
    }

    /// The source of one standard-library workout, e.g. `girls/fran`.
    public static func librarySource(_ path: String) -> String? {
        EmbeddedLibrary.shared.get(path)?.source
    }

    /// The movement catalog shipped with the package (SPEC §11).
    public static var catalog: MovementCatalog { .shared }

    static func decodeDocument(_ object: JSONObject) -> Document? {
        guard let data = try? JSONSerialization.data(withJSONObject: JSONValue.object(object).foundation) else {
            return nil
        }
        return try? JSONDecoder.wodcraft.decode(Document.self, from: data)
    }
}

// MARK: - internal entry points

struct RawCompileResult {
    var documents: [JSONObject]
    var diagnostics: [Diagnostic]
    var sourceLines: [String]
}

func compileRaw(_ source: String, file: String?, estimate: Bool = true) -> RawCompileResult {
    var paths: [URL] = []
    if let file, !file.isEmpty {
        let url = URL(fileURLWithPath: file).standardizedFileURL.deletingLastPathComponent()
        paths.append(url)
    }
    let library = WorkoutLibrary(paths: paths)
    return compileWithLibrary(source, file, library, catalog: .shared, estimate: estimate)
}

func compileWithLibrary(
    _ source: String,
    _ file: String?,
    _ library: WorkoutLibrary,
    catalog: MovementCatalog,
    estimate: Bool
) -> RawCompileResult {
    let parsed = parseSource(source, file)
    var options = CompilerOptions()
    options.catalog = catalog
    options.equivalences = catalog.equivalences
    options.library = library
    options.estimate = estimate
    let compiler = Compiler(parsed.diags, options, file)
    let documents: [JSONObject] = parsed.file.documents.map { compiler.document($0) }
    return RawCompileResult(documents: documents, diagnostics: parsed.diags.sorted(), sourceLines: parsed.file.lines)
}
