/// The additions of WODCraft 1.1: ergometer, hold, alternatives, level quantities,
/// there and back, and the athlete's `Adapted:` block.
import Foundation
import Testing
@testable import WODCraftKit

@Suite("WODCraft 1.1")
struct LanguageOneOneTests {
    static func workout(_ source: String) throws -> Workout {
        try CompileUnitsTests.workout(source)
    }

    static func codes(_ source: String) -> [String] {
        WODCraft.check(source).map { "\($0.code) \($0.line)" }
    }

    @Test("hold keeps its duration and adds it to every rep of the estimate")
    func holdModifier() throws {
        let plain = try Self.workout("For time\n  3 Wall walk\n  10 Burpee\n")
        let held = try Self.workout("For time\n  3 Wall walk (hold 10 s)\n  10 Burpee\n")
        let movement = try CompileUnitsTests.firstMovement("For time\n  3 Wall walk (hold 10 s)\n")
        #expect(movement.modifiers == ["hold 10 s"])
        let before = try #require(plain.estimate)
        let after = try #require(held.estimate)
        #expect(after.minS > before.minS)
        #expect(Self.codes("AMRAP 10\n  5 Burpee\n  1 Wall walk (hold ten)\n") == ["E001 3"])
    }

    @Test("an alternative keeps the first option and lists the others in `or`")
    func alternatives() throws {
        let workout = try Self.workout("For time\n  10 Ring row | Scap pull | 8 Pull-up\n")
        #expect(workout.wodcraft == "1.1")
        let block = try #require(workout.blocks.first?.asBlock)
        let item = try #require(block.items.first?.asMovement)
        #expect(item.movement == "ring_row")
        #expect(item.options.map { $0.movement } == ["ring_row", "scapular_pull_up", "pull_up"])
        #expect(item.options.map { $0.quantity?.reps?.value() } == [10, 10, 8])
        let plain = try Self.workout("For time\n  10 Burpee\n")
        #expect(plain.wodcraft == "1.0")
        #expect(Self.codes("For time\n  10 Ring row |\n") == ["E016 1", "E001 2"])
        #expect(Self.codes("For time\n  10 Ring row | 8 Pull-up\n\nScaled:\n  Pull-up -> Ring row | Burpee\n") == ["E014 5"])
    }

    @Test("a level applies to every option, and the board says 'ou' in French")
    func alternativesResolvedAndShown() throws {
        let source = "For time\n  10 Ring row | 8 Pull-up\n\nScaled:\n  Pull-up -> Jumping pull-up\n"
        let workout = try Self.workout(source)
        let scaled: Workout = workout.resolved(for: AthleteProfile(category: .men, level: .scaled, units: .kg))
        let item = try #require(scaled.blocks.first?.asBlock?.items.first?.asMovement)
        #expect(item.or?.map { $0.movement } == ["jumping_pull_up"])
        #expect(workout.whiteboard(language: .fr).contains("10 Tirage aux anneaux ou 8 Traction"))
    }

    static let ladder: String = "AMRAP 5:00\n  1-2-3 ...\n    Wall walk\n    Chest-to-bar pull-up\n  10/8 cal Row\n\n"
        + "Scaled:\n  Chest-to-bar pull-up -> 2x Ring row\n  Wall walk -> 3 Inchworm\n  Row -> 0.5x Row\n"

    @Test("a level changes quantities after the arrow: a factor, or a new quantity")
    func levelQuantities() throws {
        let workout = try Self.workout(Self.ladder)
        #expect(workout.wodcraft == "1.1")
        let operations = try #require(workout.levels?["scaled"])
        #expect(operations.map { $0.factor } == [2, nil, 0.5])
        #expect(operations[1].quantity?.reps?.value() == 3)
        let scaled: Workout = workout.resolved(for: AthleteProfile(category: .women, level: .scaled, units: .kg))
        let amrap = try #require(scaled.blocks.first?.asBlock)
        let ladder = try #require(amrap.items.first?.asBlock)
        let pull = try #require(ladder.items.last?.asMovement)
        #expect(pull.movement == "ring_row")
        #expect(pull.factor == 2)
        #expect(pull.quantity == nil)
        let row = try #require(amrap.items.last?.asMovement)
        #expect(row.quantity?.cal?.value() == 4)
        #expect(scaled.whiteboard().contains("2x Ring row"))
        let errors = "For time\n  20 Pull-up\n  10 Burpee\n\nScaled:\n  10 Pull-up -> Ring row\n"
            + "  Burpee -> 0x Air squat\n  Pull-up -> 400 m Ring row\n"
        #expect(Self.codes(errors) == ["E014 6", "E035 7", "E033 8"])
    }

    @Test("there and back: the block and the score carry it, the estimate counts the way back")
    func thereAndBack() throws {
        let source = "For time, cap 25:00, teams of 2, there and back\n  50 cal Row\n  40 Pull-up\n  10 Wall walk\n"
        let workout = try Self.workout(source)
        #expect(workout.wodcraft == "1.1")
        let block = try #require(workout.blocks.first?.asBlock)
        #expect(block.thereAndBack == true)
        #expect(workout.score.thereAndBack == true)
        #expect(workout.score.capped == .reps)
        let once = try Self.workout(source.replacingOccurrences(of: ", there and back", with: ""))
        let there = try #require(workout.estimate)
        let single = try #require(once.estimate)
        #expect(there.minS > single.minS * 1.5)
        #expect(workout.whiteboard(language: .fr).contains("For time · cap 25:00 · aller-retour"))
        let french = try Self.workout(source.replacingOccurrences(of: "there and back", with: "aller-retour"))
        #expect(french.blocks.first?.asBlock?.thereAndBack == true)
        #expect(Self.codes("EMOM 10, there and back\n  5 Burpee\n  5 Air squat\n") == ["E014 1"])
    }
}
