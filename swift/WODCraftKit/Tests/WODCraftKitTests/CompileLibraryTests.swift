/// The 40 workouts of the standard library compile, without errors, to the document they ship with.
import Foundation
import Testing
@testable import WODCraftKit

@Suite("Compile: standard library")
struct CompileLibraryTests {
    static let entries: [LibraryWorkout] = EmbeddedLibrary.shared.order.compactMap { EmbeddedLibrary.shared.get($0) }

    @Test("the library ships 40 workouts")
    func libraryIsComplete() {
        #expect(CompileLibraryTests.entries.count == 40)
        #expect(EmbeddedLibrary.shared.get("girls/fran") != nil)
    }

    @Test("every library workout compiles without an error", arguments: entries.map(\.path))
    func compilesCleanly(_ path: String) throws {
        let entry: LibraryWorkout = try #require(EmbeddedLibrary.shared.get(path))
        let result: CompileResult = WODCraft.compile(entry.source)
        let errors: [Diagnostic] = result.diagnostics.filter { $0.severity == .error }
        #expect(errors.isEmpty, "\(path): \(errors.map(\.code))")
        #expect(result.ok)
        #expect(result.document != nil)
    }

    @Test("every library workout compiles to its shipped document", arguments: entries.map(\.path))
    func matchesShippedDocument(_ path: String) throws {
        let entry: LibraryWorkout = try #require(EmbeddedLibrary.shared.get(path))
        let documents: [[String: Any]] = Conformance.compiledJSON(entry.source, file: nil)
        let got: Any = Conformance.withoutEstimate(documents.first ?? [:])
        let want: Any = Conformance.withoutEstimate(JSONValue.object(entry.compiled).foundation)
        let difference: String? = Conformance.firstDifference(got, want)
        #expect(difference == nil, "\(path): \(difference ?? "")")
    }

    @Test("`use girls/fran` resolves offline from the embedded library")
    func useResolvesOffline() throws {
        let result: CompileResult = WODCraft.compile("# Fran again\nuse girls/fran\n")
        #expect(result.ok)
        let document: Document = try #require(result.document)
        guard case let .workout(workout) = document else {
            Issue.record("expected a workout")
            return
        }
        #expect(workout.title == "Fran again")
        #expect(workout.blocks.count == 1)
        #expect(workout.blocks[0].used?.path == "girls/fran")
        #expect(workout.blocks[0].used?.title == "Fran")
        // the adopted workout keeps the levels and the score of the one it points at
        #expect(workout.score.type == .time)
        #expect(workout.levels?["scaled"] != nil)
    }

    @Test("an unknown library path is E050")
    func unknownPath() {
        let diagnostics: [Diagnostic] = WODCraft.check("use girls/nowhere\n")
        #expect(diagnostics.map(\.code) == ["E050"])
    }

    @Test("a `use` inside a block must be allowed there")
    func useInsideABlock() {
        let result: CompileResult = WODCraft.compile("3 rounds\n  use girls/fran\n")
        // Fran is a for_time workout, which a rounds block accepts
        #expect(result.ok)
        let diagnostics: [Diagnostic] = WODCraft.check("Death by Burpee\n  use girls/fran\n")
        #expect(diagnostics.contains { $0.code == "E015" })
    }
}
