/// Statements, blocks, movements, parameters, `use`, levels and score (SPEC §4–§12).
import Foundation

extension Compiler {
    // MARK: - meta

    func meta(_ initial: JSONObject, _ metas: [MetaLine]) -> JSONObject {
        var out: JSONObject = initial
        // 'units' first: it decides how a load written without a unit is read
        let ordered: [MetaLine] = metas.filter { $0.key == "units" } + metas.filter { $0.key != "units" }
        for line in ordered {
            let key: String = line.key
            let value: String = line.value.trimmingCharacters(in: .whitespaces)
            switch key {
            case "units":
                let lowered: String = value.lowercased()
                if lowered != "kg" && lowered != "lb" {
                    err("E013", "units must be 'kg' or 'lb', found '\(value)'.", line.valueSpan)
                } else {
                    out["units"] = .string(lowered)
                }
            case "cap":
                if let seconds = durationFromText(value) {
                    out["cap_s"] = .number(seconds)
                } else {
                    err("E013", "Invalid cap '\(value)'.", line.valueSpan, "e.g. 'cap: 12:00'")
                }
            case "score":
                scoreMeta(&out, value, line)
            case "vest":
                if let parsed = dualFromText(value) {
                    let unit: String = parsed.unit ?? out["units"]?.stringValue ?? units
                    out["vest"] = .object(Measures.loadToJSON(parsed.value, unit, opt.equivalences))
                } else {
                    err("E013", "Invalid vest load '\(value)'.", line.valueSpan, "e.g. 'vest: 20/14 lb'")
                }
            case "tags":
                let tags: [JSONValue] = value
                    .split(separator: ",")
                    .map { $0.trimmingCharacters(in: .whitespaces) }
                    .filter { !$0.isEmpty }
                    .map { JSONValue.string($0) }
                out["tags"] = .array(tags)
            case "note", "stimulus":
                let bucket: String = key == "note" ? "notes" : "stimulus"
                var list: [JSONValue] = out[bucket]?.arrayValue ?? []
                list.append(.string(value))
                out[bucket] = .array(list)
            case "date", "time", "tiebreak":
                out[key] = .string(value)
            default:
                break
            }
        }
        return out
    }

    /// 'score: VALUE[, total]' — the value, then its modifiers after a comma (SPEC §6, 1.2).
    func scoreMeta(_ out: inout JSONObject, _ value: String, _ line: MetaLine) {
        let parts: [String] = value.split(separator: ",", omittingEmptySubsequences: false)
            .map { $0.trimmingCharacters(in: .whitespaces).lowercased() }
        let written: String = value.split(separator: ",", omittingEmptySubsequences: false).first
            .map { $0.trimmingCharacters(in: .whitespaces) } ?? value
        let head: String = scoreAliases[parts[0]] ?? parts[0]
        let modifiers: [String] = Array(parts.dropFirst())
        if !scoreTypes.contains(head) {
            let known: String = scoreTypes.sorted().joined(separator: ", ")
            err("E013", "Unknown score '\(written)'.", line.valueSpan, "one of: " + known)
            return
        }
        for modifier in modifiers where !scoreModifiers.contains(modifier) {
            err("E013", "Unknown score modifier '\(modifier)'.", line.valueSpan, "e.g. 'score: load, total'")
            return
        }
        if !modifiers.isEmpty, head == "none" {
            err("E013", "A workout scored 'none' has nothing to add up.", line.valueSpan, "e.g. 'score: load, total'")
            return
        }
        out["score"] = .string(head)
        if !modifiers.isEmpty {
            out["score_total"] = .bool(true)
        }
    }

    // MARK: - statements

    func statements(_ list: [Statement], _ parent: String) -> [JSONObject] {
        var items: [JSONObject] = []
        for statement in list {
            if statement is MetaLine || statement is CommentLine {
                continue
            }
            if let rest = statement as? RestLine {
                var out = JSONObject()
                out["type"] = .string("rest")
                out["seconds"] = .number(rest.seconds)
                out["source"] = sourceDict(rest.span)
                items.append(out)
            } else if let useLine = statement as? UseLine {
                for block in use(useLine) {
                    let kind: String = block["type"]?.stringValue ?? ""
                    if allowedChildren[parent]?.contains(kind) == true {
                        items.append(block)
                    } else {
                        let message: String =
                            "'\(useLine.path)' is a \(humanName(kind)) workout and cannot go inside \(humanName(parent))."
                        err("E015", message, useLine.span, "put the 'use' line on its own, at the top level")
                    }
                }
            } else if let movementLine = statement as? MovementLine {
                if let item = movement(movementLine, parent) {
                    items.append(item)
                }
            } else if let blockNode = statement as? BlockNode {
                if let compiled = block(blockNode, parent) {
                    items.append(compiled)
                }
            }
        }
        return items
    }

    func block(_ node: BlockNode, _ parent: String) -> JSONObject? {
        var kind: String = node.kind
        if (kind == "rounds" || kind == "ladder"), node.forTime {
            kind = "for_time"
        }
        if kind == "slot", !intervalKinds.contains(parent) {
            err(
                "E014",
                "'Odd:', 'Even:' and 'Min N:' are only allowed inside an EMOM or an 'Every' block.",
                node.span,
                "indent it under the EMOM it belongs to"
            )
            return nil
        }
        let allowed: Set<String> = allowedChildren[parent] ?? []
        if !allowed.contains(kind) {
            let hint: String? = timedKinds.contains(parent) ? "indent it under an untimed block, e.g. '3 rounds'" : nil
            err("E015", "A \(humanName(kind)) block is not allowed inside \(humanName(parent)).", node.span, hint)
            return nil
        }
        var out = JSONObject()
        out["type"] = .string(kind)
        out["source"] = sourceDict(node.span)
        if (node.kind == "rounds" || node.kind == "ladder"), node.forTime {
            if let rounds = node.rounds {
                out["rounds"] = .number(Double(rounds))
            }
            if let reps = node.reps {
                out["reps"] = .array(reps.map { JSONValue.number(Double($0)) })
            }
        }
        if let duration = node.durationS, !out.has("duration_s") {
            out["duration_s"] = .number(duration)
        }
        if let interval = node.intervalS, !out.has("interval_s") {
            out["interval_s"] = .number(interval)
        }
        if let rounds = node.rounds, !out.has("rounds") {
            out["rounds"] = .number(Double(rounds))
        }
        if let cap = node.capS, !out.has("cap_s") {
            out["cap_s"] = .number(cap)
        }
        if let reps = node.reps, !out.has("reps") {
            out["reps"] = .array(reps.map { JSONValue.number(Double($0)) })
        }
        if node.repsOpen {
            out["reps_open"] = .bool(true)
        }
        if let name = node.slotName {
            out["slot"] = .string(name)
        } else if let minute = node.slotMinute {
            out["slot"] = .number(Double(minute))
        }
        if node.thereAndBack {
            if thereAndBackKinds.contains(kind) {
                out["there_and_back"] = .bool(true)
            } else {
                err(
                    "E014",
                    "'there and back' does not apply to \(humanName(kind)).",
                    node.span,
                    "use it on For time, AMRAP, N rounds or a rep ladder"
                )
            }
        }
        if let attempts = node.attempts {
            if kind != "max_load" {
                err("E014", "Attempts only apply to Max load, not to \(humanName(kind)).", node.span, "e.g. 'Max load, 3 attempts'")
            } else if attempts < 1 {
                err("E035", "A Max load needs at least one attempt.", node.span)
            } else {
                out["attempts"] = .number(Double(attempts))
            }
        }
        if let teams = node.teams {
            if parent != "root" {
                err("E014", "'Teams of N' is only allowed on the main format line.", node.span)
            } else {
                out["teams"] = .number(Double(teams))
            }
        }
        checkBlockArguments(kind, out, node.span)
        // inside a rep ladder, movements take their reps from the ladder
        let childParent: String = out.has("reps") ? "ladder" : kind
        let children: [JSONObject] = statements(node.children, childParent)
        out["items"] = .array(children.map { JSONValue.object($0) })
        if children.isEmpty, kind != "max_load" {
            err("E016", "Empty \(humanName(kind)) block.", node.span)
        }
        return out
    }

    private func checkBlockArguments(_ kind: String, _ out: JSONObject, _ span: Span) {
        if kind == "amrap", out["duration_s"] == nil {
            err("E034", "An AMRAP needs a duration.", span, "e.g. 'AMRAP 12'")
        }
        if kind == "emom", out["duration_s"] == nil {
            err("E034", "An EMOM needs a total duration.", span, "e.g. 'EMOM 10'")
        }
        if kind == "every" {
            if out["interval_s"] == nil {
                err("E034", "'Every' needs an interval.", span, "e.g. 'Every 3:00 x 5'")
            }
            if out["rounds"] == nil {
                err("E034", "'Every' needs a number of intervals.", span, "e.g. 'Every 3:00 x 5'")
            }
        }
        let checks: [(key: String, what: String)] = [
            ("duration_s", "duration"),
            ("interval_s", "interval"),
            ("cap_s", "cap"),
        ]
        for check in checks {
            if let value = out[check.key]?.doubleValue, value <= 0 {
                err("E035", "The \(check.what) must be greater than zero.", span)
            }
        }
        if kind == "tabata", (out["rounds"]?.intValue ?? 0) < 1 {
            err("E035", "A Tabata needs at least one round.", span)
        }
        if kind == "slot", let minute = out["slot"]?.intValue, out["slot"]?.stringValue == nil, minute < 1 {
            err("E035", "Minutes are numbered from 1.", span)
        }
        if kind == "rounds" || kind == "for_time", let rounds = out["rounds"]?.intValue, rounds < 1 {
            err("E035", "The number of rounds must be at least 1.", span)
        }
        for value in out["reps"]?.arrayValue ?? [] where (value.intValue ?? 1) < 1 {
            err("E035", "Rep ladder values must be at least 1.", span)
            break
        }
    }
}
