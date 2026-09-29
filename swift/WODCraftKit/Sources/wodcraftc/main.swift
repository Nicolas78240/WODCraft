// A thin command line over WODCraftKit, so the Swift implementation can be checked from a shell:
//
//     swift run wodcraftc compile fran.wod     # the compiled document, as JSON
//     swift run wodcraftc check fran.wod       # the diagnostics, as JSON
//
// It exists for differential testing against the reference implementation; an application embeds
// the library, not this.
import Foundation
import WODCraftKit

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("wodcraftc: \(message)\n".utf8))
    exit(2)
}

let arguments: [String] = Array(CommandLine.arguments.dropFirst())
guard arguments.count == 2, ["compile", "check"].contains(arguments[0]) else {
    fail("usage: wodcraftc compile|check FILE")
}

let path: String = arguments[1]
guard let source = try? String(contentsOfFile: path, encoding: .utf8) else {
    fail("\(path): cannot be read as UTF-8 text")
}

let result = WODCraft.compile(source, file: path)
let diagnostics: [[String: Any]] = result.diagnostics.map { diagnostic in
    var row: [String: Any] = [
        "code": diagnostic.code,
        "severity": diagnostic.severity.rawValue,
        "message": diagnostic.message,
        "line": diagnostic.line,
        "col": diagnostic.col,
    ]
    if let suggestion = diagnostic.suggestion { row["suggestion"] = suggestion }
    return row
}

var payload: [String: Any] = ["ok": result.ok, "diagnostics": diagnostics]
if arguments[0] == "compile" {
    let encoder = JSONEncoder.wodcraft
    encoder.outputFormatting = [.sortedKeys]
    let documents: [Any] = result.documents.compactMap { document in
        guard let data = try? encoder.encode(document) else { return nil }
        return try? JSONSerialization.jsonObject(with: data)
    }
    payload["documents"] = documents
}

guard let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]) else {
    fail("cannot serialize the result")
}
FileHandle.standardOutput.write(data)
FileHandle.standardOutput.write(Data("\n".utf8))
exit(result.ok ? 0 : 1)
