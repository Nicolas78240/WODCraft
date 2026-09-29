import Foundation
import Testing

@testable import WODCraftKit

@Suite("Catalog")
struct CatalogTests {
    let catalog = Catalog.shared

    @Test("the embedded catalog holds the 214 movements of WODCraft 1.1")
    func loadsEveryMovement() {
        #expect(catalog.count == 214)
        #expect(catalog.identifiers.count == 214)
        #expect(catalog.all.count == 214)
    }

    @Test("a movement is found by identifier")
    func findsByIdentifier() throws {
        let pullUp = try #require(catalog.movement(id: "pull_up"))
        #expect(pullUp.name == "Pull-up")
        #expect(pullUp.family == .gymnastics)
        #expect(catalog.movement(id: "not_a_movement") == nil)
    }

    @Test("English names, aliases and identifiers all resolve")
    func resolvesEnglish() {
        #expect(catalog.resolve(name: "Pull-up")?.id == "pull_up")
        #expect(catalog.resolve(name: "pull ups")?.id == "pull_up")
        #expect(catalog.resolve(name: "  Pull   Up  ")?.id == "pull_up")
        // As in Python, the identifier answers with spaces, not with its underscore.
        #expect(catalog.resolve(name: "pull_up") == nil)
        #expect(catalog.resolve(name: "deadlift")?.id == "deadlift")
        #expect(catalog.resolve(name: "Wall balls")?.id == "wall_ball")
    }

    @Test("the generic ergometer, the yoga push-up and the scap pull resolve")
    func resolvesLotBMovements() {
        for alias in ["ergometer", "ergo", "cal ergo", "machine", "Ergomètre"] {
            #expect(catalog.resolve(name: alias)?.id == "ergometer")
        }
        #expect(catalog.resolve(name: "ergo")?.quantities == ["calories", "distance", "time"])
        #expect(catalog.resolve(name: "yoga push-up")?.id == "yoga_push_up")
        #expect(catalog.resolve(name: "scap pull")?.id == "scapular_pull_up")
    }

    @Test("French aliases resolve, with or without accents")
    func resolvesFrench() {
        #expect(catalog.resolve(name: "tractions")?.id == "pull_up")
        #expect(catalog.resolve(name: "traction")?.id == "pull_up")
        #expect(catalog.resolve(name: "soulevé de terre")?.id == "deadlift")
        #expect(catalog.resolve(name: "souleve de terre")?.id == "deadlift")
        #expect(catalog.resolve(name: "SOULEVÉ DE TERRE")?.id == "deadlift")
    }

    @Test("an unknown name resolves to nothing")
    func rejectsUnknown() {
        #expect(catalog.resolve(name: "quantum burpee") == nil)
    }

    @Test("normalization matches the Python rule")
    func normalizes() {
        #expect(Catalog.normalize("Pull-Ups") == "pull up")
        #expect(Catalog.normalize("Toes-to-bar") == "toes to bar")
        // A short word keeps its trailing s, and so does a double s.
        #expect(Catalog.normalize("as") == "as")
        #expect(Catalog.normalize("press") == "press")
        #expect(Catalog.normalize("Dumbbell  snatch\n") == "dumbbell snatch")
    }

    @Test("display names follow the requested language")
    func displaysNames() {
        #expect(catalog.displayName(for: "pull_up", language: .en) == "Pull-up")
        #expect(catalog.displayName(for: "pull_up", language: .fr) == "Traction")
        #expect(catalog.displayName(for: "deadlift", language: .fr) == "Soulevé de terre")
        // An unknown identifier degrades to a readable spelling.
        #expect(catalog.displayName(for: "not_a_movement", language: .en) == "not a movement")
    }

    @Test("search ranks exact matches first and honours the family filter")
    func searches() {
        let snatches = catalog.search("snatch", limit: 10)
        #expect(snatches.first?.id == "snatch")
        #expect(snatches.count > 1)

        let gymnastics = catalog.search("pull", family: .gymnastics, limit: 50)
        #expect(!gymnastics.isEmpty)
        for movement in gymnastics { #expect(movement.family == .gymnastics) }

        #expect(catalog.search("pull", limit: 3).count == 3)
        #expect(catalog.search("absolutely nothing", limit: 10).isEmpty)
    }

    @Test("suggestions find the movement behind a typo")
    func suggests() {
        let suggestions = catalog.suggestions(for: "thrustr")
        #expect(suggestions.contains("Thruster"))
        #expect(catalog.suggestions(for: "deadlif").contains("Deadlift"))
    }

    @Test("loads convert through the equivalence table")
    func convertsLoads() {
        #expect(catalog.poundsToKilograms(95) == 43)
        #expect(catalog.kilogramsToPounds(43) == 95)
        #expect(catalog.poundsToKilograms(65) == 30)
        #expect(catalog.kilogramsToPounds(24) == 53)
        // Off the table, arithmetic takes over: 100 lb is 45.36 kg, rounded to the half kilo.
        #expect(catalog.poundsToKilograms(99) == 45)
        #expect(catalog.kilogramsToPounds(41) == 90)
    }

    @Test("heights convert through the equivalence table")
    func convertsHeights() {
        #expect(catalog.inchesToCentimetres(24) == 60)
        #expect(catalog.centimetresToInches(60) == 24)
        #expect(catalog.inchesToCentimetres(20) == 50)
        // Off the table: 27 in is 68.58 cm, rounded to the centimetre.
        #expect(catalog.inchesToCentimetres(27) == 69)
    }

    @Test("paces are keyed by quantity kind")
    func readsPaces() throws {
        let row = try #require(catalog.movement(id: "row"))
        #expect(row.pace(forQuantity: "distance") != nil)
        #expect(row.pace(forQuantity: "calories") != nil)
        let thruster = try #require(catalog.movement(id: "thruster"))
        #expect(thruster.pace(forQuantity: "reps") != nil)
    }
}
