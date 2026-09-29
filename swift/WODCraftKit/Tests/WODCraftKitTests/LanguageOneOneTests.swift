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
}
