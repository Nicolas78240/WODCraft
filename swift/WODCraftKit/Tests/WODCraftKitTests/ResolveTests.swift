import Foundation
import Testing

@testable import WODCraftKit

/// Decode a compiled document written inline, the way the library stores them.
func compiledWorkout(_ json: String) throws -> Workout {
    let data = Data(json.utf8)
    let document = try JSONDecoder.wodcraft.decode(Document.self, from: data)
    guard case let .workout(workout) = document else {
        throw DecodingError.dataCorrupted(
            DecodingError.Context(codingPath: [], debugDescription: "expected a workout")
        )
    }
    return workout
}

/// Visit every movement of a block tree.
func walkMovements(_ blocks: [Block], _ visit: (Movement) -> Void) {
    for block in blocks { walkMovements(block.items, visit) }
}

func walkMovements(_ items: [Item], _ visit: (Movement) -> Void) {
    for item in items {
        switch item {
        case let .movement(movement): visit(movement)
        case .rest: break
        case let .block(block): walkMovements(block.items, visit)
        }
    }
}

/// The first movement of the first block, or a recorded failure.
func firstMovement(_ workout: Workout) -> Movement? {
    guard let block = workout.blocks.first, let item = block.items.first else { return nil }
    if case let .movement(movement) = item { return movement }
    return nil
}

@Suite("Resolve")
struct ResolveTests {
    let library = Library.shared

    // MARK: Level order (SPEC §14)

    @Test("Rx reads the workout as written")
    func rxKeepsTheWorkout() throws {
        let fran = try #require(library.entry(path: "girls/fran")?.workout)
        let resolved = fran.resolved(for: AthleteProfile(category: .men, level: .rx, units: .kg))
        #expect(resolved.resolved?.level == "rx")
        #expect(resolved.levels == nil)
        let thruster = try #require(firstMovement(resolved))
        #expect(thruster.movement == "thruster")
        #expect(thruster.load?.value == 43)
    }

    @Test("the level fallback walks down, then back up")
    func levelFallbackOrder() {
        #expect(AthleteProfile(level: .rx).levelsToTry() == [.rx, .intermediate, .scaled, .foundations])
        #expect(AthleteProfile(level: .intermediate).levelsToTry() == [.intermediate, .scaled, .foundations, .rx])
        #expect(AthleteProfile(level: .scaled).levelsToTry() == [.scaled, .foundations, .intermediate, .rx])
        #expect(AthleteProfile(level: .foundations).levelsToTry() == [.foundations, .scaled, .intermediate, .rx])
    }

    @Test("an intermediate athlete falls back to the scaled level Fran declares")
    func fallsBackToScaled() throws {
        let fran = try #require(library.entry(path: "girls/fran")?.workout)
        let resolved = fran.resolved(for: AthleteProfile(category: .men, level: .intermediate, units: .kg))
        #expect(resolved.resolved?.level == "scaled")
        let thruster = try #require(firstMovement(resolved))
        #expect(thruster.load?.value == 30)
        guard case let .movement(pullUp) = resolved.blocks[0].items[1] else {
            Issue.record("expected a movement")
            return
        }
        #expect(pullUp.movement == "jumping_pull_up")
        #expect(pullUp.name == "Jumping pull-up")
        #expect(pullUp.load == nil)
    }

    // MARK: Category and units

    @Test("Fran for a woman in kilograms is 30 kg")
    func franWomenInKilograms() throws {
        let fran = try #require(library.entry(path: "girls/fran")?.workout)
        let resolved = fran.resolved(for: AthleteProfile(category: .women, level: .rx, units: .kg))
        let thruster = try #require(firstMovement(resolved))
        #expect(thruster.load?.value == 30)
        #expect(thruster.load?.unit == "kg")
        #expect(thruster.load?.kg == .single(30))
        #expect(thruster.load?.written == nil)
        #expect(resolved.resolved == Resolved(category: .women, level: "rx", units: "kg"))
    }

    @Test("Fran for a woman in pounds keeps the written 65 lb")
    func franWomenInPounds() throws {
        let fran = try #require(library.entry(path: "girls/fran")?.workout)
        let resolved = fran.resolved(for: AthleteProfile(category: .women, level: .rx, units: .lb))
        let thruster = try #require(firstMovement(resolved))
        #expect(thruster.load?.value == 65)
        #expect(thruster.load?.unit == "lb")
        #expect(thruster.load?.kg == .single(30))
    }

    @Test("dual quantities collapse to the athlete's category")
    func quantitiesCollapse() throws {
        let entry = try #require(library.entry(path: "open/14_5")?.workout)
        let resolved = entry.resolved(for: AthleteProfile(category: .women, level: .rx, units: .kg))
        var duals = 0
        walkMovements(resolved.blocks) { movement in
            if let reps = movement.quantity?.reps, reps.isDual { duals += 1 }
            if let load = movement.load, load.kg.isDual { duals += 1 }
        }
        #expect(duals == 0)
    }

    // MARK: Percentages and bodyweight

    static let percentWorkout = """
    {"wodcraft":"1.0","kind":"workout","title":"Squats",
     "blocks":[{"type":"rounds","rounds":3,"items":[
        {"type":"movement","movement":"back_squat","name":"Back squat",
         "quantity":{"kind":"reps","reps":5},
         "percent":{"value":75,"of":"back_squat"}}]}],
     "score":{"type":"load"}}
    """

    @Test("a percentage of a one-rep max becomes a load rounded to the plate")
    func percentageBecomesLoad() throws {
        let workout = try compiledWorkout(ResolveTests.percentWorkout)
        let profile = AthleteProfile(units: .kg, oneRepMax: ["back_squat": 140])
        let squat = try #require(firstMovement(workout.resolved(for: profile)))
        #expect(squat.load?.value == 105)
        #expect(squat.load?.unit == "kg")
        #expect(squat.load?.kg == .single(105))
    }

    @Test("a percentage in pounds rounds to the nearest 5 lb")
    func percentageRoundsInPounds() throws {
        let workout = try compiledWorkout(ResolveTests.percentWorkout)
        // 75 % of 140 kg is 105 kg, i.e. 231.5 lb, which the 5 lb plates make 230 lb.
        let profile = AthleteProfile(units: .lb, oneRepMax: ["back_squat": 140])
        let squat = try #require(firstMovement(workout.resolved(for: profile)))
        #expect(squat.load?.value == 230)
        #expect(squat.load?.unit == "lb")
    }

    @Test("a percentage rounds to the nearest 2.5 kg plate")
    func percentageRoundsToPlate() throws {
        let json = ResolveTests.percentWorkout.replacingOccurrences(of: "\"value\":75", with: "\"value\":70")
        let workout = try compiledWorkout(json)
        // 70 % of 103 kg is 72.1 kg, which the 2.5 kg plates make 72.5 kg.
        let profile = AthleteProfile(units: .kg, oneRepMax: ["back_squat": 103])
        let squat = try #require(firstMovement(workout.resolved(for: profile)))
        #expect(squat.load?.value == 72.5)
    }

    @Test("a percentage without a matching one-rep max is left alone")
    func percentageWithoutReference() throws {
        let workout = try compiledWorkout(ResolveTests.percentWorkout)
        let squat = try #require(firstMovement(workout.resolved(for: AthleteProfile(units: .kg))))
        #expect(squat.load == nil)
        #expect(squat.percent?.value == .single(75))
    }

    @Test("a bodyweight factor becomes a load when the profile knows the athlete's weight")
    func bodyweightBecomesLoad() throws {
        let json = """
        {"wodcraft":"1.0","kind":"workout",
         "blocks":[{"type":"rounds","rounds":1,"items":[
            {"type":"movement","movement":"back_squat","name":"Back squat","bodyweight":1.5}]}],
         "score":{"type":"load"}}
        """
        let workout = try compiledWorkout(json)
        let profile = AthleteProfile(units: .kg, bodyweightKg: 80)
        let squat = try #require(firstMovement(workout.resolved(for: profile)))
        #expect(squat.load?.value == 120)
    }

    // MARK: Heights

    static let boxWorkout = """
    {"wodcraft":"1.0","kind":"workout",
     "blocks":[{"type":"rounds","rounds":1,"items":[
        {"type":"movement","movement":"box_jump","name":"Box jump",
         "quantity":{"kind":"reps","reps":10},
         "height":{"cm":{"men":60,"women":50},"in":{"men":24,"women":20},
                   "unit":"in","written":{"men":24,"women":20}}}]}],
     "score":{"type":"time"}}
    """

    @Test("box heights follow the unit system")
    func heightsFollowUnits() throws {
        let workout = try compiledWorkout(ResolveTests.boxWorkout)
        let metric = try #require(firstMovement(workout.resolved(for: AthleteProfile(category: .women, units: .kg))))
        #expect(metric.height?.value == 50)
        #expect(metric.height?.unit == "cm")
        #expect(metric.height?.cm == .single(50))

        let imperial = try #require(firstMovement(workout.resolved(for: AthleteProfile(category: .men, units: .lb))))
        #expect(imperial.height?.value == 24)
        #expect(imperial.height?.unit == "in")
        #expect(imperial.height?.cm == .single(60))
    }

    // MARK: Whole library

    @Test("every library workout resolves for every profile without losing its blocks")
    func resolvesTheWholeLibrary() {
        let profiles: [AthleteProfile] = [
            AthleteProfile(category: .men, level: .rx, units: .kg),
            AthleteProfile(category: .women, level: .rx, units: .lb),
            AthleteProfile(category: .women, level: .scaled, units: .kg),
            AthleteProfile(category: .men, level: .foundations, units: .lb),
        ]
        for entry in library.entries {
            for profile in profiles {
                let resolved = entry.compiled.resolved(for: profile)
                #expect(resolved.workouts.count == entry.compiled.workouts.count)
                for workout in resolved.workouts {
                    #expect(workout.levels == nil)
                    #expect(workout.resolved?.units == profile.units.rawValue)
                    #expect(workout.resolved?.category == profile.category)
                    walkMovements(workout.blocks) { movement in
                        if let load = movement.load { #expect(load.value != nil) }
                        if let height = movement.height { #expect(height.value != nil) }
                    }
                }
            }
        }
    }

    @Test("a resolved workout prints its profile on the board")
    func resolvedBoardShowsProfile() throws {
        let fran = try #require(library.entry(path: "girls/fran")?.workout)
        let resolved = fran.resolved(for: AthleteProfile(category: .women, level: .rx, units: .kg))
        let board = resolved.whiteboard()
        #expect(board.contains("[women · rx · kg]"))
        #expect(board.contains("30 kg"))
        #expect(!board.contains("Levels:"))
        #expect(!resolved.whiteboard(showProfile: false).contains("[women · rx · kg]"))
    }
}
