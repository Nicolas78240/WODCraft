/// The additions of WODCraft 1.2: attempts, the total, and a cap for the whole workout —
/// the CrossFit Total.
import Foundation
import Testing
@testable import WODCraftKit

@Suite("WODCraft 1.2")
struct LanguageOneTwoTests {
    static let total: String = """
        # CrossFit Total
        score: load, total
        cap: 30:00
        Max load, 3 attempts
          1 Back squat
          Rest 2:00
        Rest 3:00
        Max load, 3 attempts
          1 Shoulder press
          Rest 2:00
        Rest 3:00
        Max load, 3 attempts
          1 Deadlift
          Rest 2:00

        """

    static var perLift: String {
        total.replacingOccurrences(of: "cap: 30:00\n", with: "")
            .replacingOccurrences(of: "3 attempts", with: "3 attempts, cap 8:00")
    }

    static func workout(_ source: String) throws -> Workout {
        try CompileUnitsTests.workout(source)
    }

    static func codes(_ source: String) -> [String] {
        WODCraft.check(source).map { "\($0.code) \($0.line)" }
    }

    @Test("attempts go on the Max load block, in English or in French")
    func attempts() throws {
        let workout = try Self.workout(Self.total)
        let lifts: [Block] = workout.blocks.compactMap(\.asBlock)
        #expect(lifts.map(\.attempts) == [3, 3, 3])
        #expect(try Self.workout("Max load, 3 essais\n  1 Deadlift\n").blocks.first?.asBlock?.attempts == 3)
        #expect(Self.codes("For time, 3 attempts\n  10 Burpee\n") == ["E014 1"])
        #expect(Self.codes("Max load, 0 attempts\n  1 Deadlift\n") == ["E035 1"])
    }

    @Test("a total over several lifts is a multi score that adds up")
    func total() throws {
        let workout = try Self.workout(Self.total)
        #expect(workout.wodcraft == "1.2")
        #expect(workout.score.type == .multi)
        #expect(workout.score.isTotal)
        #expect(workout.score.unit == .load)
        #expect(workout.score.parts?.map(\.block) == [0, 2, 4])
        let lynne = try Self.workout("score: reps, total\n5 rounds\n  max Bench press bw\n  max Pull-up\n")
        #expect(lynne.score.type == .reps)
        #expect(lynne.score.aggregate == "sum")
        #expect(Self.codes("score: load, best\nMax load\n  1 Deadlift\n") == ["E013 1"])
        #expect(Self.codes("score: load, total\nMax load\n  1 Deadlift\nAMRAP 6:00\n  10 Burpee\n") == ["E036 4"])
    }

    @Test("one cap or the other: the workout's, or each block's")
    func caps() throws {
        let workout = try Self.workout(Self.total)
        #expect(workout.capS == 1800)
        #expect(workout.blocks.compactMap(\.asBlock).allSatisfy { $0.capS == nil })
        let single = try Self.workout("cap: 12:00\nFor time\n  100 Burpee\n")
        #expect(single.capS == nil)
        #expect(single.blocks.first?.asBlock?.capS == 720)
        #expect(single.wodcraft == "1.0")
        #expect(Self.codes("cap: 30:00\nMax load, cap 8:00\n  1 Back squat\nMax load\n  1 Deadlift\n") == ["E037 1"])
    }

    @Test("a build-up takes minutes, and the caps of the lifts add up")
    func estimates() throws {
        let estimate = try #require(try Self.workout(Self.total).estimate)
        #expect(estimate.cappedS == 1800)
        #expect(estimate.minS >= 15 * 60 && estimate.minS <= 20 * 60)
        let perLift = try #require(try Self.workout(Self.perLift).estimate)
        #expect(perLift.cappedS == 1800)  // 3 lifts of 8:00 and 2 rests of 3:00
    }

    @Test("the board shows the cap, the attempts and the total, in French too")
    func board() throws {
        let workout = try Self.workout(Self.total)
        let english = workout.whiteboard()
        #expect(english.contains("Cap: 30:00\nMax load · 3 attempts\n  1 Back squat\n  Rest 2:00 between attempts"))
        #expect(english.contains("Score: total load (best attempt of each lift)"))
        let french = workout.whiteboard(language: .fr)
        #expect(french.contains("Cap : 30:00\nCharge max · 3 essais\n  1 Squat arrière\n  Repos 2:00 entre les essais"))
        #expect(french.contains("Score : total des charges (meilleur essai de chaque barre)"))
    }

    @Test("the library ships the CrossFit Total in benchmarks/")
    func library() throws {
        let total = try #require(Library.shared.entry(path: "benchmarks/crossfit_total")?.workout)
        #expect(total.wodcraft == "1.2")
        #expect(total.capS == nil)  // the library keeps only official caps
        #expect(total.score.isTotal)
        let lifts: [Block] = total.blocks.compactMap(\.asBlock)
        #expect(lifts.compactMap { $0.items.first?.asMovement?.movement } == ["back_squat", "strict_press", "deadlift"])
        #expect(try Self.workout("use benchmarks/crossfit_total\n").score.unit == .load)
    }

    @Test("the timer shows when the workout cap stops the clock, in its place in time")
    func timerShowsTheWorkoutCap() throws {
        let total = try Self.workout(Self.total)
        let lines = total.timerText().split(separator: "\n").map(String.init)
        #expect(lines.suffix(2) == ["   30:00          cap: the clock stops", "           25:12  total"])
        let short = try Self.workout("cap: 12:00\nEMOM 10\n  10 Burpee\nRest 2:00\nAMRAP 6:00\n  10 Wall ball 9/6 kg\n")
        let text = short.timerText()
        #expect(text.contains("   10:00    2:00  Rest\n   12:00          cap: the clock stops\n   12:00    6:00  AMRAP 6:00"))
        // a cap per block, or on a single block, is already the length of its segment: no extra line
        #expect(!(try Self.workout(Self.perLift).timerText().contains("cap: the clock stops")))
        #expect(!(try Self.workout("cap: 12:00\nFor time\n  100 Burpee\n").timerText().contains("cap: the clock stops")))
        #expect(Timeline.cap(of: .workout(total)) == 1800)
        #expect(total.timeline().rendered() == Timeline.render(total.timeline()))
    }

    @Test("the timer gives each lift its own window")
    func timer() throws {
        let segments = try Self.workout(Self.perLift).timeline()
        #expect(segments.map(\.duration) == [480, 180, 480, 180, 480])
        #expect(segments.totalDuration == 1800)
        #expect(segments[0].label == "Max load · 3 attempts · cap 8:00: 1 Back squat + Rest 2:00 between attempts")
    }
}
