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

    @Test("the timer gives each lift its own window")
    func timer() throws {
        let segments = try Self.workout(Self.perLift).timeline()
        #expect(segments.map(\.duration) == [480, 180, 480, 180, 480])
        #expect(segments.totalDuration == 1800)
        #expect(segments[0].label == "Max load · 3 attempts · cap 8:00: 1 Back squat + Rest 2:00 between attempts")
    }
}
