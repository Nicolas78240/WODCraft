import Foundation
import Testing

@testable import WODCraftKit

/// One workout of the library, rendered by the Python reference implementation.
struct ViewExpectation: Decodable, Sendable, CustomTestStringConvertible {
    struct Segment: Decodable, Equatable, Sendable {
        var at: Double
        var duration: Double
        var label: String
        var kind: String
        var openEnded: Bool
    }

    var path: String
    var board: String
    var boardFr: String
    var markdown: String
    var timer: String
    var segments: [Segment]

    var testDescription: String { path }
}

enum ViewExpectations {
    /// The 82 workouts of the standard library.
    static let all: [ViewExpectation] = decode(ViewsFixtures.libraryJSON)

    /// Every compiled document of the conformance corpus: sessions, slots, ladders, teams…
    static let conformance: [ViewExpectation] = decode(ViewsFixtures.conformanceJSON)

    static func decode(_ json: String) -> [ViewExpectation] {
        do {
            return try JSONDecoder().decode([ViewExpectation].self, from: Data(json.utf8))
        } catch {
            return []
        }
    }
}

/// The compiled documents of `Tests/WODCraftKitTests/Resources/conformance`, by fixture name.
///
/// A file holding a list of documents contributes one entry per document, named `file[index]`.
enum ConformanceDocuments {
    static let all: [String: Document] = {
        var found: [String: Document] = [:]
        guard let directory = Bundle.module.url(forResource: "conformance", withExtension: nil) else {
            return found
        }
        let urls = (try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []
        for url in urls where url.pathExtension == "json" {
            guard let data = try? Data(contentsOf: url) else { continue }
            let name = url.deletingPathExtension().lastPathComponent
            if let document = try? JSONDecoder.wodcraft.decode(Document.self, from: data) {
                found[name] = document
                continue
            }
            if let list = try? JSONDecoder.wodcraft.decode([Document].self, from: data) {
                for (index, document) in list.enumerated() {
                    found[name + "[" + String(index) + "]"] = document
                }
            }
        }
        return found
    }()
}

/// The first difference between two texts, as a readable message.
func firstDifference(_ produced: String, _ expected: String) -> String {
    let left = produced.components(separatedBy: "\n")
    let right = expected.components(separatedBy: "\n")
    let count = max(left.count, right.count)
    var line = 0
    while line < count {
        let a: String? = line < left.count ? left[line] : nil
        let b: String? = line < right.count ? right[line] : nil
        if a != b {
            return "line \(line + 1)\n  swift:  \(a.map { "\"\($0)\"" } ?? "<missing>")\n  python: \(b.map { "\"\($0)\"" } ?? "<missing>")"
        }
        line += 1
    }
    return "no line differs"
}

@Suite("Views")
struct ViewsTests {
    let library = Library.shared

    @Test("the fixtures cover the whole library")
    func fixturesAreComplete() {
        #expect(ViewExpectations.all.count == 82)
        var paths: [String] = []
        for entry in library.entries { paths.append(entry.path) }
        var expected: [String] = []
        for row in ViewExpectations.all { expected.append(row.path) }
        #expect(paths.sorted() == expected.sorted())
    }

    @Test("the whiteboard matches Python for every library workout", arguments: ViewExpectations.all)
    func boardMatchesPython(_ expectation: ViewExpectation) throws {
        let entry = try #require(library.entry(path: expectation.path))
        let produced = entry.compiled.whiteboard()
        #expect(produced == expectation.board, "\(expectation.path): \(firstDifference(produced, expectation.board))")
    }

    @Test("the French whiteboard matches Python for every library workout", arguments: ViewExpectations.all)
    func frenchBoardMatchesPython(_ expectation: ViewExpectation) throws {
        let entry = try #require(library.entry(path: expectation.path))
        let produced = entry.compiled.whiteboard(language: .fr)
        #expect(produced == expectation.boardFr, "\(expectation.path): \(firstDifference(produced, expectation.boardFr))")
    }

    @Test("the Markdown export matches Python for every library workout", arguments: ViewExpectations.all)
    func markdownMatchesPython(_ expectation: ViewExpectation) throws {
        let entry = try #require(library.entry(path: expectation.path))
        let produced = entry.compiled.markdown()
        #expect(produced == expectation.markdown, "\(expectation.path): \(firstDifference(produced, expectation.markdown))")
    }

    @Test("the timeline matches Python segment by segment", arguments: ViewExpectations.all)
    func timelineMatchesPython(_ expectation: ViewExpectation) throws {
        let entry = try #require(library.entry(path: expectation.path))
        let produced = entry.compiled.timeline()
        #expect(produced.count == expectation.segments.count, "\(expectation.path): segment count")
        let count = min(produced.count, expectation.segments.count)
        var index = 0
        while index < count {
            let mine = produced[index]
            let theirs = expectation.segments[index]
            #expect(mine.label == theirs.label, "\(expectation.path) #\(index): label")
            #expect(abs(mine.at - theirs.at) < 1e-6, "\(expectation.path) #\(index): at")
            #expect(abs(mine.duration - theirs.duration) < 1e-6, "\(expectation.path) #\(index): duration")
            #expect(mine.kind.rawValue == theirs.kind, "\(expectation.path) #\(index): kind")
            #expect(mine.openEnded == theirs.openEnded, "\(expectation.path) #\(index): openEnded")
            index += 1
        }
    }

    @Test("the printed timer matches Python for every library workout", arguments: ViewExpectations.all)
    func timerTextMatchesPython(_ expectation: ViewExpectation) throws {
        let entry = try #require(library.entry(path: expectation.path))
        let produced = entry.compiled.timeline().rendered()
        #expect(produced == expectation.timer, "\(expectation.path): \(firstDifference(produced, expectation.timer))")
    }

    // MARK: The conformance corpus (sessions, slots, ladders, teams, buy-in…)

    @Test("the conformance corpus is loaded")
    func conformanceIsLoaded() {
        // the corpus grows: what matters is that every case has an expectation
        #expect(ViewExpectations.conformance.count >= 37)
        #expect(ConformanceDocuments.all.count == ViewExpectations.conformance.count)
    }

    @Test("every conformance document renders like Python", arguments: ViewExpectations.conformance)
    func conformanceMatchesPython(_ expectation: ViewExpectation) throws {
        let document = try #require(ConformanceDocuments.all[expectation.path])
        let board = document.whiteboard()
        #expect(board == expectation.board, "\(expectation.path): \(firstDifference(board, expectation.board))")
        let french = document.whiteboard(language: .fr)
        #expect(french == expectation.boardFr, "\(expectation.path): \(firstDifference(french, expectation.boardFr))")
        let markdown = document.markdown()
        #expect(markdown == expectation.markdown, "\(expectation.path): \(firstDifference(markdown, expectation.markdown))")
        let timer = document.timeline().rendered()
        #expect(timer == expectation.timer, "\(expectation.path): \(firstDifference(timer, expectation.timer))")

        let segments = document.timeline()
        #expect(segments.count == expectation.segments.count, "\(expectation.path): segment count")
        let count = min(segments.count, expectation.segments.count)
        var index = 0
        while index < count {
            #expect(segments[index].label == expectation.segments[index].label, "\(expectation.path) #\(index)")
            #expect(segments[index].kind.rawValue == expectation.segments[index].kind, "\(expectation.path) #\(index)")
            #expect(segments[index].openEnded == expectation.segments[index].openEnded, "\(expectation.path) #\(index)")
            #expect(abs(segments[index].at - expectation.segments[index].at) < 1e-6, "\(expectation.path) #\(index)")
            #expect(abs(segments[index].duration - expectation.segments[index].duration) < 1e-6, "\(expectation.path) #\(index)")
            index += 1
        }
    }

    // MARK: Shape checks that do not depend on the fixtures

    @Test("Fran reads as a whiteboard")
    func franBoard() throws {
        let fran = try #require(library.entry(path: "girls/fran")?.workout)
        let board = fran.whiteboard()
        #expect(board.hasPrefix("FRAN\n"))
        #expect(board.contains("21-15-9 for time · cap 10:00"))
        #expect(board.contains("Score: time (capped: reps)"))
        #expect(board.contains("Levels: scaled"))
    }

    @Test("the French board renames the movements")
    func franBoardInFrench() throws {
        let fran = try #require(library.entry(path: "girls/fran")?.workout)
        let board = fran.whiteboard(language: .fr)
        #expect(board.contains("Traction"))
        #expect(!board.contains("Pull-up"))
    }

    @Test("an EMOM yields one segment per minute")
    func emomSegments() throws {
        let json = """
        {"wodcraft":"1.0","kind":"workout","title":"Every minute",
         "blocks":[{"type":"emom","duration_s":600,"interval_s":60,"items":[
            {"type":"movement","movement":"burpee","name":"Burpee",
             "quantity":{"kind":"reps","reps":8}}]}],
         "score":{"type":"none"}}
        """
        let workout = try compiledWorkout(json)
        let segments = workout.timeline()
        #expect(segments.count == 10)
        #expect(segments[0].at == 0)
        #expect(segments[0].duration == 60)
        #expect(segments[0].kind == .interval)
        #expect(segments[0].label == "EMOM 10:00 · 1/10: 8 Burpee")
        #expect(segments[9].at == 540)
        #expect(segments[9].label == "EMOM 10:00 · 10/10: 8 Burpee")
    }

    @Test("a Tabata yields one 30 s segment per interval and per movement")
    func tabataSegments() throws {
        let json = """
        {"wodcraft":"1.0","kind":"workout","title":"Tabata something",
         "blocks":[{"type":"tabata","rounds":8,"items":[
            {"type":"movement","movement":"air_squat","name":"Air squat"},
            {"type":"movement","movement":"sit_up","name":"Sit-up"}]}],
         "score":{"type":"reps"}}
        """
        let workout = try compiledWorkout(json)
        let segments = workout.timeline()
        #expect(segments.count == 16)
        #expect(segments.totalDuration == 480)
        for segment in segments {
            #expect(segment.duration == 30)
            #expect(segment.kind == .interval)
        }
        #expect(segments[0].label == "Tabata · 1/8: Air squat")
        #expect(segments[8].label == "Tabata · 1/8: Sit-up")
    }

    @Test("an Every block yields one segment per round")
    func everySegments() throws {
        let json = """
        {"wodcraft":"1.0","kind":"workout","title":"Every three",
         "blocks":[{"type":"every","interval_s":180,"rounds":5,"items":[
            {"type":"movement","movement":"row","name":"Row",
             "quantity":{"kind":"calories","cal":15}}]}],
         "score":{"type":"none"}}
        """
        let workout = try compiledWorkout(json)
        let segments = workout.timeline()
        #expect(segments.count == 5)
        #expect(segments.totalDuration == 900)
        #expect(segments[0].label == "Every 3:00 x 5 · 1/5: 15 cal Row")
        #expect(segments[4].at == 720)
    }

    @Test("a capped block is not open-ended, an uncapped one is")
    func openEndedSegments() throws {
        let capped = try compiledWorkout("""
        {"wodcraft":"1.0","kind":"workout",
         "blocks":[{"type":"for_time","cap_s":600,"rounds":3,"items":[
            {"type":"movement","movement":"burpee","name":"Burpee",
             "quantity":{"kind":"reps","reps":10}}]}],
         "score":{"type":"time"}}
        """)
        #expect(capped.timeline().first?.openEnded == false)
        #expect(capped.timeline().first?.duration == 600)

        let open = try compiledWorkout("""
        {"wodcraft":"1.0","kind":"workout",
         "blocks":[{"type":"for_time","rounds":3,"items":[
            {"type":"movement","movement":"burpee","name":"Burpee",
             "quantity":{"kind":"reps","reps":10}}]}],
         "score":{"type":"time"},"estimate":{"min_s":120,"max_s":240}}
        """)
        #expect(open.timeline().first?.openEnded == true)
        #expect(open.timeline().first?.duration == 240)
    }

    @Test("clock and number formatting follow the reference rules")
    func formatting() {
        #expect(formatClock(0) == "0:00")
        #expect(formatClock(59.6) == "1:00")
        #expect(formatClock(600) == "10:00")
        #expect(formatClock(3661) == "1:01:01")
        #expect(fmtNum(43) == "43")
        #expect(fmtNum(72.5) == "72.5")
        #expect(fmtNum(0.5) == "0.5")
    }
}
