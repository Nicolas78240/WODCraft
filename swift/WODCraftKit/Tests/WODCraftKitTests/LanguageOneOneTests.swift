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
}
