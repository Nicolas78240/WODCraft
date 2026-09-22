/// Units, durations, duals and the equivalence table (SPEC §2.1, §2.2, §13).
import Foundation
import Testing
@testable import WODCraftKit

@Suite("Compile: units and durations")
struct CompileUnitsTests {
    // MARK: - helpers

    static func workout(_ source: String) throws -> Workout {
        let result: CompileResult = WODCraft.compile(source)
        let document: Document = try #require(result.document, "did not compile: \(result.diagnostics.map(\.code))")
        guard case let .workout(workout) = document else {
            throw TestFailure.notAWorkout
        }
        return workout
    }

    static func firstMovement(_ source: String) throws -> Movement {
        let workout: Workout = try workout(source)
        let block: Block = try #require(workout.blocks.first)
        for item in block.items {
            if case let .movement(movement) = item { return movement }
        }
        throw TestFailure.noMovement
    }

    enum TestFailure: Error {
        case notAWorkout
        case noMovement
    }

    // MARK: - durations

    @Test("a bare number is minutes only on a format line")
    func bareMinutes() throws {
        let workout: Workout = try Self.workout("AMRAP 12\n  10 Burpee\n")
        #expect(workout.blocks[0].durationS == 720)
        #expect(WODCraft.check("EMOM 10\n  5 Burpee\n").isEmpty)
    }

    @Test("`m` means metres, never minutes")
    func metresAreNeverMinutes() throws {
        let diagnostics: [Diagnostic] = WODCraft.check("AMRAP 12 m\n  10 Burpee\n")
        #expect(diagnostics.map(\.code) == ["E001"])
        #expect(diagnostics[0].message.contains("metres"))
        #expect(diagnostics[0].suggestion?.contains("12 min") == true)

        // as a quantity, the same `m` is a distance
        let movement: Movement = try Self.firstMovement("For time\n  400 m Run\n")
        #expect(movement.quantity?.kind == .distance)
        #expect(movement.quantity?.m == .single(400))
        #expect(movement.quantity?.unit == "m")
    }

    @Test("clock, seconds and minutes all reach the same rest")
    func restDurations() throws {
        let sources: [String] = [
            "3 rounds\n  10 Burpee\n  Rest 2:00\n",
            "3 rounds\n  10 Burpee\n  Rest 120 s\n",
            "3 rounds\n  10 Burpee\n  Rest 2 min\n",
        ]
        for source in sources {
            let workout: Workout = try Self.workout(source)
            guard case let .rest(rest) = workout.blocks[0].items[1] else {
                Issue.record("expected a rest item in \(source)")
                continue
            }
            #expect(rest.seconds == 120)
        }
        // outside a format line a bare number needs a unit
        #expect(WODCraft.check("3 rounds\n  10 Burpee\n  Rest 2\n").map(\.code) == ["E001"])
    }

    @Test("an h:mm:ss cap is read as a clock")
    func clockCap() throws {
        let workout: Workout = try Self.workout("For time, cap 1:00:00\n  100 Burpee\n")
        #expect(workout.blocks[0].capS == 3600)
    }

    @Test("distances normalize to metres")
    func distances() throws {
        let table: [(String, Double)] = [("1 mi", 1609.344), ("5 km", 5000), ("400 m", 400), ("10 ft", 3.048)]
        for (written, metres) in table {
            let movement: Movement = try Self.firstMovement("For time\n  \(written) Run\n")
            #expect(movement.quantity?.m == .single(metres), "\(written)")
        }
    }

    // MARK: - duals and conversions

    @Test("`95/65 lb` converts through the equivalence table")
    func loadEquivalences() throws {
        let movement: Movement = try Self.firstMovement("For time\n  21 Thruster 95/65 lb\n")
        let load: Load = try #require(movement.load)
        #expect(load.written == .dual(men: 95, women: 65))
        #expect(load.unit == "lb")
        #expect(load.lb == .dual(men: 95, women: 65))
        // 95 lb ↔ 43 kg and 65 lb ↔ 30 kg come from the table, not from arithmetic (43.09, 29.48)
        #expect(load.kg == .dual(men: 43, women: 30))
    }

    @Test("a load written in kilograms carries the table's pounds")
    func kilogramsToPounds() throws {
        let movement: Movement = try Self.firstMovement("For time\n  21 Thruster 43/30 kg\n")
        let load: Load = try #require(movement.load)
        #expect(load.kg == .dual(men: 43, women: 30))
        #expect(load.lb == .dual(men: 95, women: 65))
        #expect(load.unit == "kg")
    }

    @Test("a pood is sixteen kilograms")
    func poods() throws {
        let movement: Movement = try Self.firstMovement("For time\n  21 Kettlebell swing 1.5/1 pood\n")
        let load: Load = try #require(movement.load)
        #expect(load.kg == .dual(men: 24, women: 16))
        #expect(load.lb == .dual(men: 53, women: 36))
        #expect(load.written == .dual(men: 1.5, women: 1))
        #expect(load.unit == "pood")
    }

    @Test("heights convert through the equivalence table")
    func heights() throws {
        let inches: Movement = try Self.firstMovement("For time\n  10 Box jump 24/20 in\n")
        #expect(inches.height?.cm == .dual(men: 60, women: 50))
        #expect(inches.height?.inches == .dual(men: 24, women: 20))
        let centimetres: Movement = try Self.firstMovement("For time\n  10 Box jump 60/50 cm\n")
        #expect(centimetres.height?.inches == .dual(men: 24, women: 20))
        #expect(centimetres.height?.unit == "cm")
    }

    @Test("a single written value is not a dual")
    func singleValue() throws {
        let movement: Movement = try Self.firstMovement("For time\n  21 Thruster 43 kg\n")
        #expect(movement.load?.kg == .single(43))
        #expect(movement.load?.kg.isDual == false)
    }

    @Test("`units:` fills in a load written without one")
    func defaultUnits() throws {
        let movement: Movement = try Self.firstMovement("units: lb\nFor time\n  21 Thruster 95\n")
        #expect(movement.load?.unit == "lb")
        #expect(movement.load?.kg == .single(43))
        // without the default, the same line is an error
        #expect(WODCraft.check("For time\n  21 Thruster 95\n").map(\.code) == ["E031"])
    }

    @Test("a calorie quantity keeps its dual")
    func calories() throws {
        let movement: Movement = try Self.firstMovement("AMRAP 10:00\n  15/12 cal Row\n")
        #expect(movement.quantity?.kind == .calories)
        #expect(movement.quantity?.cal == .dual(men: 15, women: 12))
    }

    @Test("a time quantity is carried in seconds")
    func timeQuantity() throws {
        let movement: Movement = try Self.firstMovement("For time\n  1:00 Plank\n")
        #expect(movement.quantity?.kind == .time)
        #expect(movement.quantity?.s == .single(60))
        let minutes: Movement = try Self.firstMovement("For time\n  2 min Plank\n")
        #expect(minutes.quantity?.s == .single(120))
    }
}
