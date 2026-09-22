/// The WODCraft 1.0 conformance suite: `spec/conformance/NAME.wod` with `NAME.json` or `NAME.diag`.
import Foundation
import Testing
@testable import WODCraftKit

@Suite("Conformance")
struct ConformanceTests {
    @Test("the suite is complete")
    func suiteIsPresent() {
        #expect(Conformance.cases.count >= 60, "found \(Conformance.cases.count) cases in \(Conformance.directory.path)")
    }

    @Test("case", arguments: Conformance.cases)
    func conformanceCase(_ testCase: Conformance.Case) throws {
        let source: String = try String(contentsOf: testCase.wod, encoding: .utf8)
        if testCase.isDiagnostics {
            let diagnostics: [Diagnostic] = WODCraft.check(source, file: testCase.wod.path)
            let expected: [String] = Conformance.expectedDiagnostics(testCase.expectation)
            let actual: [String] = Conformance.actualDiagnostics(diagnostics)
            #expect(actual == expected, "\(testCase.name): expected \(expected), got \(actual)")
            return
        }

        let documents: [[String: Any]] = Conformance.compiledJSON(source, file: testCase.wod.path)
        let expectedData: Data = try Data(contentsOf: testCase.expectation)
        let expectedAny: Any = try JSONSerialization.jsonObject(with: expectedData)

        if let expectedList = expectedAny as? [Any] {
            let got: Any = Conformance.withoutEstimate(documents)
            let want: Any = Conformance.withoutEstimate(expectedList)
            let difference: String? = Conformance.firstDifference(got, want)
            #expect(difference == nil, "\(testCase.name): \(difference ?? "")")
            return
        }

        let first: [String: Any] = documents.first ?? [:]
        let got: Any = Conformance.withoutEstimate(first)
        let want: Any = Conformance.withoutEstimate(expectedAny)
        let difference: String? = Conformance.firstDifference(got, want)
        #expect(difference == nil, "\(testCase.name): \(difference ?? "")")
    }

    @Test("a compiled document decodes into the typed model")
    func documentsDecode() throws {
        for testCase in Conformance.cases where !testCase.isDiagnostics {
            let source: String = try String(contentsOf: testCase.wod, encoding: .utf8)
            let result: CompileResult = WODCraft.compile(source, file: testCase.wod.path)
            #expect(result.document != nil, "\(testCase.name) did not decode")
        }
    }
}
