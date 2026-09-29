/// Block ownership (§4.1), nesting (§4.2), levels (§9) and score inference (§12).
import Foundation
import Testing
@testable import WODCraftKit

@Suite("Compile: structure")
struct CompileStructureTests {
    static func workout(_ source: String) throws -> Workout {
        try CompileUnitsTests.workout(source)
    }

    /// A readable outline of the body: one line per item, indented like the tree.
    static func outline(_ body: [Item], _ depth: Int = 0) -> [String] {
        return outline(items: body, depth)
    }

    static func outline(items: [Item], _ depth: Int) -> [String] {
        var lines: [String] = []
        for item in items {
            switch item {
            case let .movement(movement):
                lines.append(String(repeating: "  ", count: depth) + movement.movement)
            case let .rest(rest):
                lines.append(String(repeating: "  ", count: depth) + "rest \(Int(rest.seconds))")
            case let .block(block):
                lines.append(String(repeating: "  ", count: depth) + label(block))
                lines.append(contentsOf: outline(items: block.items, depth + 1))
            }
        }
        return lines
    }

    static func label(_ block: Block) -> String {
        var text: String = block.type.rawValue
        if let slot = block.slot {
            switch slot {
            case .odd: text += " odd"
            case .even: text += " even"
            case let .minute(number): text += " min\(number)"
            }
        }
        return text
    }

    // MARK: - §4.1 block ownership

    @Test("rule 1: a block owns its indented children")
    func rule1IndentedChildren() throws {
        let workout: Workout = try Self.workout("""
        3 rounds
          10 Air squat
          10 Push-up
        """)
        #expect(Self.outline(workout.blocks) == ["rounds", "  air_squat", "  push_up"])
        #expect(workout.blocks[0].rounds == 3)
    }

    @Test("rule 2: the first format line owns the whole body")
    func rule2MainFormat() throws {
        let workout: Workout = try Self.workout("""
        For time, cap 10:00
        21-15-9
          Thruster 43/30 kg
          Pull-up
        """)
        // the canonical merge folds the ladder into the for_time block (SPEC §13)
        #expect(workout.blocks.count == 1)
        #expect(workout.blocks[0].asBlock?.type == .forTime)
        #expect(workout.blocks[0].reps == [21, 15, 9])
        #expect(workout.blocks[0].capS == 600)
        #expect(Self.outline(workout.blocks) == ["for_time", "  thruster", "  pull_up"])
    }

    @Test("rule 2: a meta line is transparent, the lines under it belong to the block above")
    func rule2MetaIsTransparent() throws {
        let workout: Workout = try Self.workout("""
        For time
        cap: 10:00
          10 Burpee
          20 Air squat
        """)
        #expect(workout.blocks.count == 1)
        #expect(workout.blocks[0].capS == 600)
        #expect(Self.outline(workout.blocks) == ["for_time", "  burpee", "  air_squat"])
    }

    @Test("rule 3: a format block also takes the label lines that follow it")
    func rule3Labels() throws {
        let workout: Workout = try Self.workout("""
        EMOM 12
        Odd: 12/10 cal Row
        Even: 10 Burpee
        """)
        #expect(Self.outline(workout.blocks) == ["emom", "  slot odd", "    row", "  slot even", "    burpee"])
        #expect(workout.blocks[0].durationS == 720)
        #expect(workout.blocks[0].intervalS == 60)
    }

    @Test("rule 3: Buy-in and Cash-out wrap the main work")
    func rule3BuyInCashOut() throws {
        let workout: Workout = try Self.workout("""
        For time
          Buy-in: 1 mi Run
          100 Pull-up
          Cash-out: 1 mi Run
        """)
        let expected: [String] = ["for_time", "  buy_in", "    run", "  pull_up", "  cash_out", "    run"]
        #expect(Self.outline(workout.blocks) == expected)
    }

    @Test("`Min N:` slots number the intervals of a cycle")
    func minuteSlots() throws {
        let workout: Workout = try Self.workout("""
        EMOM 15
        Min 1: 10 Burpee
        Min 2: 15 Air squat
        Min 3: 12/10 cal Row
        """)
        #expect(workout.blocks[0].items.count == 3)
        #expect(Self.outline(workout.blocks).first == "emom")
        #expect(Self.outline(workout.blocks).contains("  slot min2"))
    }

    @Test("two timed blocks in a row need an untimed parent")
    func timedBlocksNest() throws {
        let workout: Workout = try Self.workout("""
        3 rounds
          AMRAP 4:00
            10 Burpee
            10 Air squat
          Rest 1:00
        """)
        let expected: [String] = ["rounds", "  amrap", "    burpee", "    air_squat", "  rest 60"]
        #expect(Self.outline(workout.blocks) == expected)
    }

    // MARK: - §4.2 nesting

    @Test("an EMOM inside an AMRAP is forbidden nesting")
    func forbiddenNesting() {
        let diagnostics: [Diagnostic] = WODCraft.check("AMRAP 10:00\n  10 Burpee\n  EMOM 5\n    10 Air squat\n")
        #expect(diagnostics.map(\.code) == ["E015"])
    }

    @Test("a slot label outside an interval block is rejected")
    func slotOutsideInterval() {
        let diagnostics: [Diagnostic] = WODCraft.check("For time\n  100 Burpee\n  Odd: 10 Air squat\n")
        #expect(diagnostics.map(\.code) == ["E014"])
    }

    // MARK: - §9 levels

    @Test("a level replaces parameters and movements")
    func scaledLevel() throws {
        let workout: Workout = try Self.workout("""
        21-15-9 for time
          Thruster 95/65 lb
          Pull-up

        Scaled:
          Thruster 65/45 lb
          Pull-up -> Jumping pull-up
        """)
        let scaled: [LevelOperation] = try #require(workout.levels?["scaled"])
        #expect(scaled.count == 2)
        #expect(scaled[0].movement == "thruster")
        #expect(scaled[0].replaceWith == nil)
        #expect(scaled[0].load?.kg == .dual(men: 30, women: 20))
        #expect(scaled[1].movement == "pull_up")
        #expect(scaled[1].replaceWith == "jumping_pull_up")
        #expect(scaled[1].name == "Jumping pull-up")
    }

    @Test("parameters written before the arrow select the occurrences to change")
    func levelSelector() throws {
        let workout: Workout = try Self.workout("""
        For time
          10 Deadlift 225 lb
          10 Deadlift 155 lb

        Scaled:
          Deadlift 225 lb -> Deadlift 155 lb
        """)
        let scaled: [LevelOperation] = try #require(workout.levels?["scaled"])
        #expect(scaled[0].when?.load?.lb == .single(225))
        #expect(scaled[0].load?.lb == .single(155))
    }

    @Test("a level carries vest, cap and note; `vest: none` removes the vest")
    func levelMeta() throws {
        let workout: Workout = try Self.workout("""
        vest: 20/14 lb
        For time
          100 Burpee

        Scaled:
          vest: none
          Burpee -> Push-up
        """)
        let scaled: [LevelOperation] = try #require(workout.levels?["scaled"])
        #expect(scaled[0].meta?["vest"] == MetaValue.none)
        #expect(workout.meta?.vest?.lb == .dual(men: 20, women: 14))
    }

    @Test("the three levels can all be declared")
    func threeLevels() throws {
        let workout: Workout = try Self.workout("""
        AMRAP 12:00
          10 Box jump 24/20 in
          10 Wall ball 20/14 lb

        Intermediate:
          Box jump 20/16 in

        Scaled:
          Box jump -> Step-up 20/16 in

        Foundations:
          Box jump -> Step-up 12/12 in
        """)
        let levels: [String: [LevelOperation]] = try #require(workout.levels)
        #expect(Set(levels.keys) == ["intermediate", "scaled", "foundations"])
    }

    @Test("a level never changes quantities, and never names a movement outside the Rx work")
    func levelErrors() {
        #expect(WODCraft.check("For time\n  100 Burpee\n\nScaled:\n  Thruster 30/20 kg\n").map(\.code) == ["E040"])
        #expect(WODCraft.check("For time\n  100 Burpee\n\nScaled:\n  50 Burpee\n").map(\.code) == ["E014"])
    }

    // MARK: - §12 score

    @Test("the score is inferred from the main block")
    func inferredScores() throws {
        let table: [(String, Score.Kind)] = [
            ("For time\n  10 Burpee\n", .time),
            ("AMRAP 10:00\n  10 Burpee\n", .roundsAndReps),
            ("3 rounds for time\n  10 Burpee\n", .time),
            ("21-15-9 for time\n  Burpee\n", .time),
            ("3 rounds\n  10 Burpee\n", Score.Kind.none),
            ("Tabata\n  max Air squat\n", .reps),
            ("Death by Burpee\n", .roundsAndReps),
            ("Max load\n  Back squat 5x5 @ 75%\n", .load),
            ("EMOM 10\n  10 Burpee\n", Score.Kind.none),
        ]
        for (source, expected) in table {
            let workout: Workout = try Self.workout(source)
            #expect(workout.score.type == expected, "\(source)")
        }
    }

    @Test("an interval block with a `max` child scores reps")
    func intervalWithMax() throws {
        let workout: Workout = try Self.workout("EMOM 10\n  max Burpee\n")
        #expect(workout.score.type == .reps)
    }

    @Test("a capped for-time workout tells the capped athlete what to score")
    func cappedScore() throws {
        let workout: Workout = try Self.workout("For time, cap 10:00\n  100 Burpee\n")
        #expect(workout.score.type == .time)
        #expect(workout.score.capped == .reps)
    }

    @Test("two timed blocks in one workout score `multi`, one part per block")
    func multiScore() throws {
        let workout: Workout = try Self.workout("AMRAP 5:00\n  10 Burpee\n\nAMRAP 5:00\n  10 Air squat\n")
        #expect(workout.score.type == .multi)
        #expect(workout.score.parts?.count == 2)
        #expect(workout.score.parts?[0].block == 0)
        #expect(workout.score.parts?[1].block == 1)
    }

    @Test("a declared score the format cannot measure is E036")
    func incompatibleScore() {
        #expect(WODCraft.check("score: rounds+reps\nFor time\n  100 Burpee\n").map(\.code) == ["E036"])
        // a capped for-time workout may legitimately be scored by reps
        #expect(WODCraft.check("score: reps\nFor time, cap 12:00\n  150 Wall ball 20/14 lb\n").isEmpty)
    }

    @Test("a tiebreak rides along with the score")
    func tiebreak() throws {
        let workout: Workout = try Self.workout("tiebreak: time at the last round\nAMRAP 15:00\n  10 Pull-up\n")
        #expect(workout.score.tiebreak == "time at the last round")
    }

    // MARK: - documents and sessions

    @Test("a file holds one document per `# Title`")
    func multipleDocuments() {
        let result: CompileResult = WODCraft.compile("# Part A\nAMRAP 5:00\n  10 Burpee\n\n# Part B\nFor time\n  50 Air squat\n")
        #expect(result.documents.count == 2)
        #expect(result.documents[0].title == "Part A")
        #expect(result.documents[1].title == "Part B")
    }

    @Test("`## Section` headings make the document a session")
    func session() throws {
        let result: CompileResult = WODCraft.compile("""
        # Tuesday
        date: 2026-09-23
        units: kg

        ## Warm-up
        3 rounds
          10 Air squat

        ## Metcon
        AMRAP 12:00
          10 Burpee
        """)
        let document: Document = try #require(result.document)
        guard case let .session(session) = document else {
            Issue.record("expected a session")
            return
        }
        #expect(session.date == "2026-09-23")
        #expect(session.units == "kg")
        #expect(session.sections.map(\.title) == ["Warm-up", "Metcon"])
        #expect(document.workouts.count == 2)
    }
}
