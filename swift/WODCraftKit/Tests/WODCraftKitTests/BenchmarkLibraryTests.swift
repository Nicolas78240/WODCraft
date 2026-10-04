/// The Girls and Hero benchmarks of the standard library: every entry is complete and its
/// prescriptions are coherent (dual loads and heights, bodyweight multiples, catalog movements).
import Foundation
import Testing
@testable import WODCraftKit

@Suite("Library: Girls and Heroes")
struct BenchmarkLibraryTests {
    static let benchmarks: [LibraryEntry] =
        Library.shared.collection("girls") + Library.shared.collection("heroes")

    static let girls: Set<String> = [
        "amanda", "angie", "annie", "barbara", "chelsea", "christine", "cindy", "diane", "elizabeth",
        "eva", "fran", "grace", "helen", "isabel", "jackie", "karen", "kelly", "linda", "lynne", "mary",
        "nancy", "nicole",
    ]

    static let heroes: Set<String> = [
        "adam_brown", "arnie", "badger", "blake", "brenton", "bull", "bulger", "capoot", "coe", "daniel",
        "danny", "dt", "erin", "forrest", "garrett", "griff", "hall", "hansen", "helton", "holleyman",
        "jack", "jason", "jerry", "johnson", "josh", "joshie", "jt", "luce", "lumberjack_20", "marco",
        "mcghee", "michael", "mr_joshua", "murph", "nate", "nutts", "paul", "pk", "randy", "rj", "roy",
        "ryan", "servais", "severin", "stephen", "the_seven", "thompson", "tommy_v", "tyler",
        "war_frank", "whitten",
    ]

    /// Every movement of a block, nested blocks included.
    static func movements(_ items: [Item]) -> [Movement] {
        items.flatMap { item -> [Movement] in
            switch item {
            case let .movement(movement): return movement.options
            case .rest: return []
            case let .block(block): return movements(block.items)
            }
        }
    }

    static func isCoherent(_ amount: Amount) -> Bool {
        switch amount {
        case let .single(value): return value > 0
        case let .dual(men, women): return women > 0 && men >= women
        }
    }

    @Test("the 22 Girls and the 51 Heroes are all there")
    func everyBenchmarkIsPresent() {
        let library = Library.shared
        #expect(Set(library.collection("girls").map { String($0.path.dropFirst("girls/".count)) }) == Self.girls)
        #expect(Set(library.collection("heroes").map { String($0.path.dropFirst("heroes/".count)) }) == Self.heroes)
    }

    @Test("every benchmark is tagged, has a stimulus and a score", arguments: benchmarks.map(\.path))
    func isComplete(_ path: String) throws {
        let entry = try #require(Library.shared.entry(path: path))
        let workout = try #require(entry.workout)
        #expect(workout.meta?.tags?.contains("benchmark") == true)
        #expect(workout.meta?.tags?.contains(entry.collection) == true)
        #expect(workout.meta?.stimulus?.isEmpty == false, "\(path): \(String(describing: workout.meta))")
        #expect(!Self.movements(workout.blocks).isEmpty)
    }

    @Test("every load, height and bodyweight multiple is coherent", arguments: benchmarks.map(\.path))
    func prescriptionsAreCoherent(_ path: String) throws {
        let workout = try #require(Library.shared.entry(path: path)?.workout)
        for movement in Self.movements(workout.blocks) {
            #expect(Catalog.shared.movement(id: movement.movement) != nil, "\(path): \(movement.movement)")
            if let load = movement.load {
                #expect(Self.isCoherent(load.kg), "\(path): \(movement.movement) \(load.kg)")
                if let written = load.written { #expect(Self.isCoherent(written), "\(path): \(movement.movement)") }
            }
            if let height = movement.height {
                #expect(Self.isCoherent(height.cm), "\(path): \(movement.movement) \(height.cm)")
            }
            if let bodyweight = movement.bodyweight {
                #expect(Self.isCoherent(bodyweight), "\(path): \(movement.movement)")
            }
        }
        if let vest = workout.meta?.vest { #expect(Self.isCoherent(vest.kg)) }
    }

    @Test("bodyweight benchmarks carry a multiple of bodyweight, not a fixed load")
    func bodyweightBenchmarks() throws {
        let pk = try #require(Library.shared.entry(path: "heroes/pk")?.workout)
        let lifts = Self.movements(pk.blocks).filter { $0.movement == "back_squat" || $0.movement == "deadlift" }
        #expect(lifts.map(\.bodyweight) == [.single(1), .single(1.5)])
        #expect(lifts.allSatisfy { $0.load == nil })
        let christine = try #require(Library.shared.entry(path: "girls/christine")?.workout)
        #expect(Self.movements(christine.blocks).first { $0.movement == "deadlift" }?.bodyweight == .single(1))
    }

    @Test("a few prescriptions, checked against the official definitions")
    func officialPrescriptions() throws {
        func first(_ path: String, _ id: String) throws -> Movement {
            let workout = try #require(Library.shared.entry(path: path)?.workout)
            return try #require(Self.movements(workout.blocks).first { $0.movement == id })
        }
        // Roy: 225/155 lb deadlifts (a printed 24 kg for women is a typo)
        #expect(try first("heroes/roy", "deadlift").load?.written == .dual(men: 225, women: 155))
        // Bulger: 150 m runs, 135/95 lb front squats
        #expect(try first("heroes/bulger", "run").quantity?.m == .single(150))
        #expect(try first("heroes/bulger", "front_squat").load?.written == .dual(men: 135, women: 95))
        // Servais: 1.5 mile run, 8 rounds, then the carries
        let servais = try #require(Library.shared.entry(path: "heroes/servais")?.workout)
        #expect(servais.blocks[0].items.compactMap(\.asBlock).first?.rounds == 8)
        #expect(try first("heroes/stephen", "stiff_legged_deadlift").load?.written == .dual(men: 95, women: 65))
        #expect(try first("heroes/joshie", "l_pull_up").quantity?.reps == .single(21))
    }

    @Test("the movements added for the Heroes resolve, in English and in French")
    func newMovementsResolve() {
        let catalog = Catalog.shared
        let names: [String: String] = [
            "L-pull-up": "l_pull_up", "traction en L": "l_pull_up",
            "Ring push-up": "ring_push_up", "Ring handstand push-up": "ring_handstand_push_up",
            "Dumbbell squat clean": "dumbbell_squat_clean", "Dumbbell split clean": "dumbbell_split_clean",
            "Kettlebell overhead squat": "kettlebell_overhead_squat",
            "Plate overhead lunge": "plate_overhead_lunge", "Plate carry": "plate_carry",
            "Stiff-legged deadlift": "stiff_legged_deadlift", "stiff leg deadlift": "stiff_legged_deadlift",
            "soulevé de terre jambes tendues": "stiff_legged_deadlift",
        ]
        for (name, id) in names {
            #expect(catalog.resolve(name: name)?.id == id, "\(name)")
        }
        #expect(catalog.resolve(name: "rdl")?.id == "romanian_deadlift")
    }
}
