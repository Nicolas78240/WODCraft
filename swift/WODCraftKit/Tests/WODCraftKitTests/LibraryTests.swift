import Foundation
import Testing

@testable import WODCraftKit

@Suite("Library")
struct LibraryTests {
    let library = Library.shared

    @Test("the embedded library holds the 83 standard workouts")
    func loadsEveryEntry() {
        #expect(library.count == 83)
        #expect(library.entries.count == 83)
    }

    @Test("every entry carries its source and a compiled document")
    func entriesAreComplete() {
        for entry in library.entries {
            #expect(!entry.path.isEmpty)
            #expect(!entry.title.isEmpty)
            #expect(!entry.source.isEmpty)
            #expect(!entry.compiled.workouts.isEmpty)
        }
    }

    @Test("a workout is found by library path")
    func findsByPath() throws {
        let fran = try #require(library.entry(path: "girls/fran"))
        #expect(fran.title == "Fran")
        #expect(fran.collection == "girls")
        #expect(fran.workout?.title == "Fran")
        // A trailing .wod is tolerated, as in the Python library.
        #expect(library.entry(path: "girls/fran.wod")?.path == "girls/fran")
        #expect(library.entry(path: "girls/nobody") == nil)
    }

    @Test("search matches paths and titles, case-insensitively")
    func searches() {
        #expect(library.search("fran").map(\.path) == ["girls/fran", "heroes/war_frank"])
        #expect(library.search("GIRLS/FRAN").map(\.path) == ["girls/fran"])
        #expect(library.search("heroes").count == 51)
        #expect(library.search("").count == 83)
        #expect(library.search("no such workout").isEmpty)
    }

    @Test("the standard collections are present")
    func collections() {
        #expect(library.collection("benchmarks").count == 1)
        #expect(library.collection("girls").count == 22)
        #expect(library.collection("heroes").count == 51)
        #expect(library.collection("open").count == 9)
    }

    @Test("Fran decodes into the expected shape")
    func franShape() throws {
        let fran = try #require(library.entry(path: "girls/fran")?.workout)
        #expect(fran.score.type == .time)
        #expect(fran.score.capped == .reps)
        #expect(fran.blocks.count == 1)
        #expect(fran.blocks[0].asBlock?.type == .forTime)
        #expect(fran.blocks[0].reps == [21, 15, 9])
        #expect(fran.blocks[0].capS == 600)
        #expect(fran.levels?["scaled"] != nil)
        guard case let .movement(thruster) = fran.blocks[0].items[0] else {
            Issue.record("the first item of Fran should be a movement")
            return
        }
        #expect(thruster.movement == "thruster")
        #expect(thruster.load?.kg == .dual(men: 43, women: 30))
        #expect(thruster.load?.written == .dual(men: 95, women: 65))
    }

    @Test("everything the library carries works offline")
    func isOffline() throws {
        // Round-tripping a compiled document through the codec must not lose anything.
        let entry = try #require(library.entry(path: "heroes/murph"))
        let data = try JSONEncoder.wodcraft.encode(entry.compiled)
        let again = try JSONDecoder.wodcraft.decode(Document.self, from: data)
        #expect(again.title == entry.compiled.title)
        #expect(again.workouts.count == entry.compiled.workouts.count)
    }
}
