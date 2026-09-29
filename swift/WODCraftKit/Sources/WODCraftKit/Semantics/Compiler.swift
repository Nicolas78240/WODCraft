/// Semantic analysis: resolve, check and compile a parsed document into the JSON model.
import Foundation

/// The language this compiler implements.
let specVersion: String = "1.1"
/// The compiled format of a document that uses nothing newer (SPEC §13).
let baseVersion: String = "1.0"

let timedKinds: Set<String> = ["for_time", "amrap", "emom", "every", "tabata", "death_by", "max_load"]
let intervalKinds: Set<String> = ["emom", "every"]
let untimedKinds: Set<String> = ["rounds", "ladder"]

let allowedChildren: [String: Set<String>] = {
    var table: [String: Set<String>] = [:]
    table["rounds"] = timedKinds.union(untimedKinds).union(["buy_in", "cash_out"])
    table["ladder"] = timedKinds.union(untimedKinds)
    table["emom"] = Set(["for_time", "amrap", "slot"]).union(untimedKinds)
    table["every"] = Set(["for_time", "amrap", "slot"]).union(untimedKinds)
    table["for_time"] = untimedKinds.union(["buy_in", "cash_out"])
    table["amrap"] = untimedKinds.union(["buy_in", "cash_out"])
    table["tabata"] = untimedKinds
    table["death_by"] = []
    table["max_load"] = []
    table["slot"] = untimedKinds
    table["buy_in"] = untimedKinds
    table["cash_out"] = untimedKinds
    table["root"] = timedKinds.union(untimedKinds).union(["buy_in", "cash_out"])
    return table
}()

let scoreTypes: Set<String> = ["time", "rounds+reps", "rounds", "reps", "load", "distance", "calories", "none"]

let scoreByFormat: [String: String] = [
    "for_time": "time",
    "amrap": "rounds+reps",
    "tabata": "reps",
    "death_by": "rounds+reps",
    "max_load": "load",
    "emom": "none",
    "every": "none",
    "rounds": "none",
    "ladder": "none",
]

struct CompilerOptions {
    var catalog: MovementCatalog = .shared
    var equivalences: Equivalences = MovementCatalog.shared.equivalences
    var library: WorkoutLibrary?
    var estimate: Bool = true
}

final class Compiler {
    let diags: DiagnosticBag
    var opt: CompilerOptions
    let file: String?
    var units: String = "kg"
    var unitsDeclared: Bool = false
    var movementIds: [String] = []
    var usedWorkout: JSONObject?

    init(_ diags: DiagnosticBag, _ options: CompilerOptions = CompilerOptions(), _ file: String? = nil) {
        self.diags = diags
        self.opt = options
        self.file = file
    }

    // MARK: - documents

    func document(_ doc: DocumentNode) -> JSONObject {
        if doc.isSession {
            return session(doc)
        }
        return workout(doc.body ?? WorkoutBody(), doc.title)
    }

    func session(_ doc: DocumentNode) -> JSONObject {
        let meta: JSONObject = self.meta(JSONObject(), doc.meta)
        if let declared = meta["units"]?.stringValue {
            units = declared
            unitsDeclared = true
        }
        var sections: [JSONValue] = []
        var estimates: [JSONObject] = []
        for section in doc.sections ?? [] {
            let compiled: JSONObject = workout(section.body, section.title)
            var entry = JSONObject()
            entry["title"] = .string(section.title)
            entry["workout"] = .object(compiled)
            entry["source"] = sourceDict(section.span)
            sections.append(.object(entry))
            if let estimate = compiled["estimate"]?.objectValue {
                estimates.append(estimate)
            }
        }
        var out = JSONObject()
        out["wodcraft"] = .string(baseVersion)
        out["kind"] = .string("session")
        out["title"] = doc.title.map { JSONValue.string($0) } ?? .null
        out["sections"] = .array(sections)
        let newer: Bool = sections.contains { $0.objectValue?["workout"]?.objectValue?["wodcraft"]?.stringValue != baseVersion }
        if newer {
            out["wodcraft"] = .string(specVersion)
        }
        if !estimates.isEmpty {
            let minTotal: Double = estimates.reduce(0.0) { $0 + ($1["min_s"]?.doubleValue ?? 0) }
            let maxTotal: Double = estimates.reduce(0.0) { $0 + ($1["max_s"]?.doubleValue ?? 0) }
            var estimate = JSONObject()
            estimate["min_s"] = .number(minTotal.rounded(.toNearestOrEven))
            estimate["max_s"] = .number(maxTotal.rounded(.toNearestOrEven))
            out["estimate"] = .object(estimate)
        }
        for key in ["date", "time", "units", "tags", "notes", "stimulus"] where meta.has(key) {
            out[key] = meta[key]
        }
        return out
    }

    // MARK: - workouts

    func workout(_ body: WorkoutBody, _ title: String?) -> JSONObject {
        let savedUnits: String = units
        movementIds = []
        let savedDeclared: Bool = unitsDeclared
        var metaLines: [MetaLine] = []
        walk(body.statements) { statement in
            if let line = statement as? MetaLine { metaLines.append(line) }
        }
        let meta = self.meta(JSONObject(), metaLines)
        if let declared = meta["units"]?.stringValue {
            units = declared
            unitsDeclared = true
        }
        if let used = soleUse(body.statements) {
            return adopt(used, title, meta)
        }
        var blocks: [JSONObject] = statements(body.statements, "root")
        blocks = blocks.map { normalizeBlock($0) }
        var team: JSONObject?
        for index in blocks.indices {
            if let size = blocks[index]["teams"]?.intValue {
                blocks[index].removeValue(forKey: "teams")
                var entry = JSONObject()
                entry["size"] = .number(Double(size))
                team = entry
            }
        }
        if let cap = meta["cap_s"], !blocks.isEmpty {
            blocks[0].setDefault("cap_s", cap)
        }
        var out = JSONObject()
        out["wodcraft"] = .string(baseVersion)
        out["kind"] = .string("workout")
        out["title"] = title.map { JSONValue.string($0) } ?? .null
        out["blocks"] = .array(blocks.map { JSONValue.object($0) })
        out["score"] = .object(score(blocks, meta))
        if let team {
            out["team"] = .object(team)
        }
        let levels: JSONObject = self.levels(body.levels)
        if !levels.isEmpty {
            out["levels"] = .object(levels)
        }
        var rest = JSONObject()
        for key in meta.keys where !["units", "cap_s", "score"].contains(key) {
            rest[key] = meta[key]
        }
        if !rest.isEmpty {
            out["meta"] = .object(rest)
        }
        out["wodcraft"] = .string(compiledVersion(out))
        if opt.estimate, let estimate = Estimator.estimateWorkout(out, opt.catalog, diags, file) {
            out["estimate"] = .object(estimate)
        }
        units = savedUnits
        unitsDeclared = savedDeclared
        return out
    }

    /// A body that is only a `use` line adopts the whole referenced workout.
    func soleUse(_ statements: [Statement]) -> (blocks: [JSONObject], source: JSONObject?)? {
        let real: [Statement] = statements.filter { !($0 is MetaLine) && !($0 is CommentLine) }
        guard real.count == 1, let line = real[0] as? UseLine else { return nil }
        let blocks: [JSONObject] = use(line)
        return (blocks, usedWorkout)
    }

    func adopt(_ used: (blocks: [JSONObject], source: JSONObject?), _ title: String?, _ meta: JSONObject) -> JSONObject {
        let source: JSONObject = used.source ?? JSONObject()
        var out = JSONObject()
        out["wodcraft"] = .string(baseVersion)
        out["kind"] = .string("workout")
        let sourceTitle: JSONValue = source["title"] ?? .null
        out["title"] = title.map { JSONValue.string($0) } ?? sourceTitle
        out["blocks"] = .array(used.blocks.map { JSONValue.object($0) })
        if let inherited = source["score"], !inherited.isNull {
            out["score"] = inherited
        } else {
            out["score"] = .object(score(used.blocks, meta))
        }
        for key in ["team", "levels", "estimate"] {
            if let value = source[key], !value.isNull {
                out[key] = value
            }
        }
        out["wodcraft"] = .string(compiledVersion(out))
        var merged: JSONObject = source["meta"]?.objectValue ?? JSONObject()
        for key in meta.keys where !["units", "cap_s", "score"].contains(key) {
            merged[key] = meta[key]
        }
        if !merged.isEmpty {
            out["meta"] = .object(merged)
        }
        return out
    }

    // MARK: - helpers

    /// The format version a compiled workout needs: "1.0" unless it uses a 1.1 construct (SPEC §13).
    func compiledVersion(_ workout: JSONObject) -> String {
        func uses(_ value: JSONValue?) -> Bool {
            switch value {
            case let .object(object)?:
                if let options = object["or"]?.arrayValue, !options.isEmpty { return true }
                if case .bool(true)? = object["there_and_back"] { return true }
                return object.keys.contains { uses(object[$0]) }
            case let .array(array)?:
                return array.contains { uses($0) }
            default:
                return false
            }
        }
        if workout.has("adapted") { return specVersion }
        let levels: JSONObject = workout["levels"]?.objectValue ?? JSONObject()
        for key in levels.keys {
            for operation in levels[key]?.arrayValue ?? [] {
                if let op = operation.objectValue, op.has("factor") || op.has("quantity") { return specVersion }
            }
        }
        return uses(workout["blocks"]) ? specVersion : baseVersion
    }

    func err(_ code: String, _ message: String, _ span: Span, _ suggestion: String? = nil) {
        diags.add(code, message, Span(span.line, span.col, span.endCol, file), suggestion)
    }

    func sourceDict(_ span: Span) -> JSONValue {
        var out = JSONObject()
        out["line"] = .number(Double(span.line))
        out["col"] = .number(Double(span.col))
        return .object(out)
    }

    func walk(_ statements: [Statement], _ visit: (Statement) -> Void) {
        for statement in statements {
            visit(statement)
            if let block = statement as? BlockNode {
                walk(block.children, visit)
            }
        }
    }
}

// MARK: - free helpers

func hasMax(_ block: JSONObject) -> Bool {
    for value in block["items"]?.arrayValue ?? [] {
        guard let item = value.objectValue else { continue }
        if item["type"]?.stringValue == "movement",
           let quantity = item["quantity"]?.objectValue,
           quantity["kind"]?.stringValue == "max" {
            return true
        }
        if hasMax(item) { return true }
    }
    return false
}

/// A declared score is accepted when the format can plausibly measure it.
func scoreCompatible(_ declared: String, _ kind: String) -> Bool {
    if declared == "none" { return true }
    if kind == "movement" {
        return ["load", "reps", "time", "distance", "calories", "rounds"].contains(declared)
    }
    if intervalKinds.contains(kind) {
        return ["reps", "rounds", "rounds+reps", "calories", "distance", "none"].contains(declared)
    }
    if ["for_time", "rounds", "ladder"].contains(kind) {
        if ["time", "reps", "rounds"].contains(declared) { return true }
        return declared == "load" && kind != "for_time"
    }
    if kind == "amrap" {
        return ["rounds+reps", "rounds", "reps", "calories", "distance"].contains(declared)
    }
    if kind == "max_load" {
        return ["load", "reps"].contains(declared)
    }
    if kind == "tabata" {
        return ["reps", "rounds", "calories", "distance"].contains(declared)
    }
    return true
}

func quantityWord(_ kind: String) -> String {
    kind
}

func humanName(_ kind: String) -> String {
    let names: [String: String] = [
        "for_time": "For time",
        "amrap": "AMRAP",
        "emom": "EMOM",
        "every": "Every",
        "tabata": "Tabata",
        "death_by": "Death by",
        "max_load": "Max load",
        "rounds": "rounds",
        "ladder": "rep ladder",
        "slot": "minute",
        "buy_in": "Buy-in",
        "cash_out": "Cash-out",
        "root": "the workout body",
    ]
    return names[kind] ?? kind
}

/// Canonical form: 'For time' + a single untimed child merges into one block (SPEC §13).
func normalizeBlock(_ block: JSONObject) -> JSONObject {
    var out: JSONObject = block
    var items: [JSONValue] = []
    for value in block["items"]?.arrayValue ?? [] {
        guard let item = value.objectValue, let kind = item["type"]?.stringValue, allowedChildren[kind] != nil else {
            items.append(value)
            continue
        }
        items.append(.object(normalizeBlock(item)))
    }
    if block["items"] != nil {
        out["items"] = .array(items)
    }
    let kind: String = block["type"]?.stringValue ?? ""
    guard kind == "for_time" || kind == "amrap", items.count == 1, let child = items[0].objectValue else {
        return out
    }
    let childKind: String = child["type"]?.stringValue ?? ""
    guard childKind == "rounds" || childKind == "ladder" else { return out }
    for blocker in ["cap_s", "duration_s", "teams"] where child.has(blocker) {
        return out
    }
    var merged: JSONObject = out
    for key in ["rounds", "reps", "reps_open"] where child.has(key) && !merged.has(key) {
        merged[key] = child[key]
    }
    merged["items"] = child["items"] ?? .array([])
    return merged
}

func durationFromText(_ text: String) -> Double? {
    let line = SourceLine(1, 0, text, text)
    let cur = Cursor(Lexer.tokenize(line, DiagnosticBag(), nil), line)
    do {
        let value = try parseDuration(cur, bareMinutes: true)
        try cur.expectEnd()
        return value
    } catch {
        return nil
    }
}

func dualFromText(_ text: String) -> (value: Dual, unit: String?)? {
    let line = SourceLine(1, 0, text, text)
    let cur = Cursor(Lexer.tokenize(line, DiagnosticBag(), nil), line)
    guard let value = try? parseDual(cur) else { return nil }
    var unit: String?
    if let tok = cur.peek(), tok.kind == .word, let kind = Units.unitKind(tok.text), kind.kind == "load" {
        unit = kind.unit
        _ = try? cur.next()
    }
    return cur.done ? (value, unit) : nil
}
