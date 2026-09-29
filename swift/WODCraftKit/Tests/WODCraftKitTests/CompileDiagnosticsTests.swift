/// One test per diagnostic family (SPEC §15).
import Foundation
import Testing
@testable import WODCraftKit

@Suite("Compile: diagnostics")
struct CompileDiagnosticsTests {
    static func codes(_ source: String) -> [String] {
        WODCraft.check(source).map(\.code)
    }

    static func located(_ source: String) -> [String] {
        WODCraft.check(source).map { "\($0.code) \($0.line)" }
    }

    // MARK: - E00x: lexical and layout

    @Test("E001 — an unexpected token")
    func e001() {
        let diagnostics: [Diagnostic] = WODCraft.check("For time\n  10 Burpee ?\n")
        #expect(diagnostics.map(\.code) == ["E001"])
        #expect(diagnostics[0].line == 2)
        #expect(diagnostics[0].severity == .error)
    }

    @Test("E002 — a tab in the indentation")
    func e002() {
        #expect(Self.located("For time\n  10 Burpee\n\t10 Air squat\n") == ["E002 3"])
    }

    @Test("E003 — a decimal comma, with the fix as a suggestion")
    func e003() {
        let diagnostics: [Diagnostic] = WODCraft.check("For time\n  10 Thruster 43,5 kg\n")
        #expect(diagnostics.map(\.code) == ["E003"])
        #expect(diagnostics[0].suggestion == "write '43.5'")
    }

    @Test("E004 — inconsistent indentation")
    func e004() {
        #expect(Self.located("For time\n  100 Burpee\n    20 Sit-up\n") == ["E004 3"])
    }

    // MARK: - E01x: lines and structure

    @Test("E010 — a line that is not a recognised format")
    func e010() {
        #expect(Self.located("teams of 2\n  10 Burpee\n") == ["E010 1"])
    }

    @Test("E011 — an unknown label")
    func e011() {
        let diagnostics: [Diagnostic] = WODCraft.check("EMOM 10\n  Warmup: 10 Burpee\n  10 Air squat\n")
        #expect(diagnostics.map(\.code) == ["E011"])
        #expect(diagnostics[0].suggestion?.contains("Buy-in") == true)
    }

    @Test("E012 — an unknown meta key")
    func e012() {
        let diagnostics: [Diagnostic] = WODCraft.check("focus: breathing\nAMRAP 10:00\n  10 Burpee\n")
        #expect(diagnostics.map(\.code) == ["E012"])
        #expect(diagnostics[0].suggestion?.contains("stimulus") == true)
    }

    @Test("E013 — an invalid meta value")
    func e013() {
        #expect(Self.located("score: bananas\nAMRAP 10:00\n  10 Burpee\n") == ["E013 1"])
        #expect(Self.located("units: stone\nAMRAP 10:00\n  10 Burpee\n") == ["E013 1"])
        #expect(Self.located("cap: soon\nAMRAP 10:00\n  10 Burpee\n") == ["E013 1"])
    }

    @Test("E014 — a statement that is not allowed where it stands")
    func e014() {
        // a slot label outside an interval block
        #expect(Self.located("For time\n  100 Burpee\n  Odd: 10 Air squat\n") == ["E014 3"])
        // 'Teams of N' away from the main format line
        #expect(Self.located("3 rounds\n  AMRAP 4, teams of 2\n    10 Burpee\n") == ["E014 2"])
        // a non-meta line in a session preamble
        #expect(Self.located("# Day\n10 Burpee\n## Metcon\nAMRAP 10:00\n  10 Burpee\n") == ["E014 2"])
    }

    @Test("E015 — forbidden nesting")
    func e015() {
        #expect(Self.located("AMRAP 10:00\n  10 Burpee\n  EMOM 5\n    10 Air squat\n") == ["E015 3"])
    }

    @Test("E016 — an empty block, including the cascading one")
    func e016() {
        #expect(Self.located("AMRAP 10:00\n") == ["E016 1"])
        // a rejected movement leaves its block empty: both are reported
        #expect(Self.located("AMRAP 10:00\n  10 Frobnicate\n") == ["E016 1", "E020 2"])
    }

    // MARK: - E02x: the catalog

    @Test("E020 — an unknown movement, with the closest candidates")
    func e020() {
        let diagnostics: [Diagnostic] = WODCraft.check("AMRAP 10:00\n  10 Burpee\n  10 Trhuster 43 kg\n")
        #expect(diagnostics.map(\.code) == ["E020"])
        #expect(diagnostics[0].suggestion?.contains("Thruster") == true)
    }

    // MARK: - E03x: quantities, parameters, formats

    @Test("E030 — a missing quantity")
    func e030() {
        let diagnostics: [Diagnostic] = WODCraft.check("For time\n  Thruster 43/30 kg\n  21 Pull-up\n")
        #expect(diagnostics.map(\.code) == ["E030"])
        #expect(diagnostics[0].suggestion?.contains("21 Thruster") == true)
        // a ladder, Max load, Death by and Tabata all supply the quantity themselves
        #expect(Self.codes("21-15-9 for time\n  Thruster 43/30 kg\n").isEmpty)
        #expect(Self.codes("Max load\n  Back squat\n").isEmpty)
    }

    @Test("E031 — a load without a unit and no `units:` default")
    func e031() {
        #expect(Self.located("For time\n  21 Thruster 43\n  21 Pull-up\n") == ["E031 2"])
        #expect(Self.codes("units: kg\nFor time\n  21 Thruster 43\n  21 Pull-up\n").isEmpty)
    }

    @Test("E032 — a parameter kind the movement does not accept")
    func e032() {
        // a height on a thruster, a load on a box jump
        #expect(Self.located("AMRAP 10:00\n  10 Thruster 24/20 in\n  10 Box jump 43/30 kg\n") == ["E032 2", "E032 3"])
    }

    @Test("E033 — a quantity kind the movement does not accept")
    func e033() {
        let diagnostics: [Diagnostic] = WODCraft.check("For time\n  400 m Thruster 43/30 kg\n")
        #expect(diagnostics.map(\.code) == ["E033"])
        #expect(diagnostics[0].suggestion?.contains("reps") == true)
    }

    @Test("E034 — a format without its required duration or count")
    func e034() {
        #expect(Self.located("AMRAP\n  10 Burpee\n") == ["E034 1"])
        #expect(Self.located("EMOM\n  10 Burpee\n") == ["E034 1"])
        #expect(Self.located("Every 3:00\n  10 Burpee\n") == ["E034 1"])
    }

    @Test("E035 — a value out of range")
    func e035() {
        // RPE above 10 and a percentage above 200
        #expect(Self.located("Max load\n  Back squat 5x5 @ RPE 14\n  Front squat 3x3 @ 250%\n") == ["E035 2", "E035 3"])
        // an open ladder without a constant step
        #expect(Self.codes("3-6-10 ... for time, cap 20:00\n  Burpee\n") == ["E035"])
    }

    @Test("E036 — a score the format cannot measure")
    func e036() {
        let diagnostics: [Diagnostic] = WODCraft.check("score: rounds+reps\nFor time\n  100 Burpee\n")
        #expect(diagnostics.map(\.code) == ["E036"])
        #expect(diagnostics[0].suggestion?.contains("time") == true)
    }

    // MARK: - E04x: levels

    @Test("E040 — a level names a movement absent from the Rx work")
    func e040() {
        #expect(Self.located("For time\n  100 Burpee\n\nScaled:\n  Thruster 30/20 kg\n") == ["E040 5"])
    }

    @Test("E041 — a duplicate level block")
    func e041() {
        let source: String = """
        For time
          21 Thruster 43/30 kg

        Scaled:
          Thruster 30/20 kg

        Scaled:
          Thruster 20/15 kg
        """
        #expect(Self.located(source) == ["E041 7"])
    }

    // MARK: - E05x: use

    @Test("E050 — an unresolved `use` path")
    func e050() {
        let diagnostics: [Diagnostic] = WODCraft.check("use girls/nowhere\n")
        #expect(diagnostics.map(\.code) == ["E050"])
        #expect(diagnostics[0].suggestion?.contains("girls/fran") == true)
    }

    @Test("E051 — a `use` cycle")
    func e051() throws {
        // the cycle case needs two files on disk, so it runs from the conformance corpus
        let url: URL = Conformance.directory.appendingPathComponent("err_use_cycle.wod")
        let source: String = try String(contentsOf: url, encoding: .utf8)
        let diagnostics: [Diagnostic] = WODCraft.check(source, file: url.path)
        #expect(diagnostics.map { "\($0.code) \($0.line)" } == ["E016 2", "E051 3"])
    }

    // MARK: - W10x: warnings

    @Test("W100 — an implausible distance")
    func w100() {
        let diagnostics: [Diagnostic] = WODCraft.check("For time\n  1 m Run\n  10 Burpee\n")
        #expect(diagnostics.map(\.code) == ["W100"])
        #expect(diagnostics[0].severity == .warning)
        #expect(diagnostics[0].suggestion?.contains("1 mi") == true)
    }

    @Test("W101 — a reversed dual")
    func w101() {
        let diagnostics: [Diagnostic] = WODCraft.check("For time\n  21 Thruster 30/43 kg\n")
        #expect(diagnostics.map(\.code) == ["W101"])
    }

    @Test("W102 — interval work above 90 % of the interval")
    func w102() {
        #expect(Self.located("EMOM 10\n  50 Burpee\n") == ["W102 2"])
    }

    @Test("W103 — an estimated duration wildly beyond the cap")
    func w103() {
        #expect(Self.located("For time, cap 1:00\n  100 Thruster 43/30 kg\n") == ["W103 1"])
    }

    @Test("W104 — a load far above the catalog reference")
    func w104() {
        let diagnostics: [Diagnostic] = WODCraft.check("For time\n  10 Thruster 300 kg\n")
        #expect(diagnostics.map(\.code) == ["W104"])
        #expect(diagnostics[0].message.contains("300 kg"))
    }

    @Test("W105 — an implausible number of reps")
    func w105() {
        #expect(Self.located("For time\n  6000 Burpee\n") == ["W105 2"])
    }

    // MARK: - reporting

    @Test("warnings do not make a compilation fail")
    func warningsAreNotErrors() {
        let result: CompileResult = WODCraft.compile("For time\n  6000 Burpee\n")
        #expect(result.ok)
        #expect(result.document != nil)
        #expect(result.diagnostics.count == 1)
    }

    @Test("diagnostics come out in source order, deduplicated")
    func ordering() {
        let diagnostics: [Diagnostic] = WODCraft.check("""
        For time
          10 Frobnicate
          10 Thruster 24/20 in
          400 m Thruster 43/30 kg
        """)
        #expect(diagnostics.map(\.line) == [2, 3, 4])
        #expect(diagnostics.map(\.code) == ["E020", "E032", "E033"])
    }

    @Test("a diagnostic prints its line and a caret under the span")
    func formatting() {
        let source: String = "For time\n  10 Thruster 43,5 kg\n"
        let diagnostic: Diagnostic = WODCraft.check(source, file: "fran.wod")[0]
        let printed: String = diagnostic.format(sourceLines: source.components(separatedBy: "\n"))
        #expect(printed.hasPrefix("fran.wod:2:15: error E003:"))
        #expect(printed.contains("^^^^"))
        #expect(printed.contains("help: write '43.5'"))
    }
}
