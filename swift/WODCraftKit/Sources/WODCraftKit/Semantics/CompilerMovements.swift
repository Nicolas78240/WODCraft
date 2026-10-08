/// Movement lines, parameters, `use`, level blocks and score inference (SPEC §7, §9, §10, §12).
import Foundation

extension Compiler {
    // MARK: - movements

    func movement(_ mv: MovementLine, _ parent: String) -> JSONObject? {
        guard var out = oneMovement(mv, parent) else { return nil }
        if mv.alternatives.isEmpty { return out }
        var options: [JSONValue] = []
        for alternative in mv.alternatives {
            if alternative.quantity == nil, alternative.sets == nil {
                // "10 Ring row | Scapular pull-up": an option without a quantity takes the first one's
                alternative.quantity = mv.quantity
            }
            if let option = oneMovement(alternative, parent) {
                options.append(.object(option))
            }
        }
        if !options.isEmpty {
            out["or"] = .array(options)
        }
        return out
    }

    func oneMovement(_ mv: MovementLine, _ parent: String) -> JSONObject? {
        guard let entry = opt.catalog.get(mv.name) else {
            let hints: [String] = opt.catalog.suggest(mv.name)
            let suggestion: String
            if hints.isEmpty {
                suggestion = "add it to the movement catalog"
            } else {
                let quoted: String = hints.map { "'\($0)'" }.joined(separator: " or ")
                suggestion = "did you mean " + quoted + "?"
            }
            err("E020", "Unknown movement '\(mv.name)'.", mv.nameSpan, suggestion)
            return nil
        }
        movementIds.append(entry.id)
        var out = JSONObject()
        out["type"] = .string("movement")
        out["movement"] = .string(entry.id)
        out["name"] = .string(entry.name)
        var quantity: QuantityNode? = mv.quantity
        var params: [ParamNode] = mv.params

        // a distance or calorie parameter written after the name is the quantity
        if quantity == nil {
            for (index, param) in params.enumerated() {
                let isMeasure: Bool = param.kind == "distance" || param.kind == "calories"
                if isMeasure, entry.quantities.contains(param.kind) {
                    quantity = QuantityNode(param.kind, param.value, param.unit, param.span)
                    params.remove(at: index)
                    break
                }
            }
        }

        if let quantity {
            if let compiled = compileQuantity(quantity, entry) {
                out["quantity"] = .object(compiled)
            }
        } else if mv.sets == nil,
                  !["ladder", "max_load", "death_by", "tabata"].contains(parent),
                  !entry.quantities.isEmpty {
            err("E030", "\(entry.name) needs a quantity.", mv.nameSpan, "e.g. '21 \(entry.name)'")
        }

        if let sets = mv.sets {
            var value = JSONObject()
            value["reps"] = .array(sets.reps.map { JSONValue.number(Double($0)) })
            out["sets"] = .object(value)
        }

        for param in params {
            self.param(&out, param, entry)
        }

        if !mv.modifiers.isEmpty {
            out["modifiers"] = .array(mv.modifiers.map { JSONValue.string($0) })
        }
        out["source"] = sourceDict(mv.nameSpan)
        return out
    }

    /// The compiled quantity of a movement line, checked against its catalog entry.
    func compileQuantity(_ quantity: QuantityNode, _ entry: MovementEntry) -> JSONObject? {
        var out = JSONObject()
        var kind: String = quantity.kind == "max" && quantity.unit == nil ? "reps" : quantity.kind
        if quantity.kind == "max" {
            switch quantity.unit {
            case "cal": kind = "calories"
            case "m": kind = "distance"
            default: kind = "reps"
            }
        }
        if !entry.quantities.contains(kind) {
            let measured: String = entry.quantities.map(quantityWord).joined(separator: " or ")
            err(
                "E033",
                "\(entry.name) is not measured in \(quantityWord(kind)).",
                quantity.span,
                "it is measured in " + measured
            )
        } else if quantity.kind == "max" || quantity.value == nil {
            var out2 = JSONObject()
            out2["kind"] = .string("max")
            out2["of"] = .string(kind)
            out["quantity"] = .object(out2)
        } else if kind == "distance" {
            var measure: JSONObject = Measures.distanceToJSON(quantity.value!, quantity.unit ?? "m")
            measure["kind"] = .string("distance")
            out["quantity"] = .object(measure)
            checkDistance(measure, entry, quantity.span)
        } else if kind == "calories" {
            var measure = JSONObject()
            measure["kind"] = .string("calories")
            measure["cal"] = Measures.amount(quantity.value!)
            out["quantity"] = .object(measure)
        } else if kind == "time" {
            var measure = JSONObject()
            measure["kind"] = .string("time")
            measure["s"] = Measures.amount(quantity.value!)
            out["quantity"] = .object(measure)
        } else {
            var measure = JSONObject()
            measure["kind"] = .string("reps")
            measure["reps"] = Measures.amount(quantity.value!)
            out["quantity"] = .object(measure)
            if max(quantity.value!.men, quantity.value!.women) > 1000 {
                err("W105", "That is a lot of reps — is the number right?", quantity.span)
            }
        }
        return out["quantity"]?.objectValue
    }

    func param(_ out: inout JSONObject, _ original: ParamNode, _ entry: MovementEntry) {
        let eq: Equivalences = opt.equivalences
        var param: ParamNode = original
        let loadish: Bool = ["load", "percent", "rpe", "bw"].contains(param.kind)
        if loadish, !entry.params.contains("load") {
            let expected: String = entry.params.contains("height") ? "a height (in, cm)" : "no load"
            err("E032", "\(entry.name) takes \(expected), not a load.", param.span)
            return
        }
        if param.kind == "distance", entry.params.contains("height") {
            // a target height written in feet ("10/9 ft") rather than in inches
            let factor: Double = (Units.metresPer[param.unit ?? "m"] ?? 1.0) * 100
            let centimetres = Dual(param.value.men * factor, param.value.women * factor, param.value.isDual)
            param = ParamNode("height", centimetres, "cm", param.span)
        }
        if param.kind == "distance" || param.kind == "calories" {
            if !entry.quantities.contains(param.kind) {
                err(
                    "E032",
                    "\(entry.name) does not take a \(param.kind) parameter.",
                    param.span,
                    "write it as the quantity, before the movement name"
                )
                return
            }
            // a per-rep measure: "10 Shuttle run 25 m" is ten runs of 25 metres
            if param.kind == "distance" {
                out["distance"] = .object(Measures.distanceToJSON(param.value, param.unit ?? "m"))
            } else {
                var measure = JSONObject()
                measure["cal"] = Measures.amount(param.value)
                out["calories"] = .object(measure)
            }
            return
        }
        if param.kind == "height", !entry.params.contains("height") {
            let expected: String = entry.params.contains("load") ? "a load (kg, lb)" : "no height"
            err("E032", "\(entry.name) takes \(expected), not a height.", param.span)
            return
        }
        switch param.kind {
        case "load":
            let unit: String = param.unit ?? units
            if param.unit == nil, !unitsDeclared {
                err(
                    "E031",
                    "Load without a unit.",
                    param.span,
                    "write 'kg' or 'lb', or add 'units: kg' at the top of the workout"
                )
                return
            }
            if min(param.value.men, param.value.women) <= 0 {
                err("E035", "A load must be greater than zero.", param.span)
                return
            }
            let load: JSONObject = Measures.loadToJSON(param.value, unit, eq)
            out["load"] = .object(load)
            checkLoad(load, entry, param.span)
        case "height":
            out["height"] = .object(Measures.heightToJSON(param.value, param.unit ?? "cm", eq))
        case "percent":
            if param.value.men > 200 || param.value.women > 200 {
                err("E035", "A percentage above 200 % is not plausible.", param.span)
                return
            }
            var percent = JSONObject()
            percent["value"] = Measures.amount(param.value)
            if let of = param.of {
                if let reference = opt.catalog.get(of) {
                    percent["of"] = .string(reference.id)
                } else {
                    err("E020", "Unknown movement '\(of)'.", param.ofSpan ?? param.span)
                }
            } else {
                percent["of"] = .string(entry.id)
            }
            out["percent"] = .object(percent)
        case "rpe":
            if !(param.value.men >= 1 && param.value.men <= 10) {
                err("E035", "RPE must be between 1 and 10.", param.span)
                return
            }
            out["rpe"] = Measures.amount(param.value)
        case "bw":
            out["bodyweight"] = Measures.amount(param.value)
        default:
            break
        }
    }

    private func checkLoad(_ load: JSONObject, _ entry: MovementEntry, _ span: Span) {
        guard let kilos = load["kg"] else { return }
        let men: Double
        let women: Double
        if kilos.objectValue != nil {
            men = Measures.pick(kilos, "men")
            women = Measures.pick(kilos, "women")
        } else {
            men = kilos.doubleValue ?? 0
            women = men
        }
        if women > men {
            err("W101", "The women load is heavier than the men load — are the values reversed?", span)
        }
        if let rx = entry.rx, (entry.rxUnit ?? "kg") == "kg" {
            let reference: Double = rx["men"] ?? 0
            if reference != 0, men > reference * 3 {
                let shown: String = Units.formatNumber(reference)
                err("W104", "\(Units.formatNumber(men)) kg is far above the usual load for \(entry.name) (\(shown) kg).", span)
            }
        }
    }

    private func checkDistance(_ quantity: JSONObject, _ entry: MovementEntry, _ span: Span) {
        guard let metresValue = quantity["m"] else { return }
        var metres: Double = metresValue.doubleValue ?? 0
        if let object = metresValue.objectValue {
            metres = object.keys.compactMap { object[$0]?.doubleValue }.min() ?? 0
        }
        guard quantity["unit"]?.stringValue == "m", metres < 10, entry.family == "M" else { return }
        let written: JSONValue = quantity["written"] ?? .number(0)
        let shown: Double = written.objectValue != nil ? Measures.pick(written, "men") : (written.doubleValue ?? 0)
        err(
            "W100",
            "\(Units.formatNumber(shown)) m of \(entry.name) is very short.",
            span,
            "did you mean miles ('1 mi')?"
        )
    }

    // MARK: - use

    func use(_ statement: UseLine) -> [JSONObject] {
        guard let library = opt.library else {
            err("E050", "No library configured to resolve '\(statement.path)'.", statement.span)
            return []
        }
        let lookup: LibraryLookup = library.load(statement.path)
        switch lookup {
        case .cycle:
            err("E051", "Circular use of '\(statement.path)'.", statement.span)
            return []
        case .notFound:
            err("E050", "Workout '\(statement.path)' not found.", statement.span, "e.g. 'use girls/fran'")
            return []
        case let .found(workout, diagnostics):
            diags.extend(diagnostics)
            usedWorkout = workout
            var blocks: [JSONObject] = []
            for value in workout["blocks"]?.arrayValue ?? [] {
                guard var block = value.objectValue else { continue }
                var used = JSONObject()
                used["path"] = .string(statement.path)
                used["title"] = workout["title"] ?? .null
                block["used"] = .object(used)
                block["source"] = sourceDict(statement.span)
                blocks.append(block)
            }
            return blocks
        }
    }

    // MARK: - levels

    /// The level blocks, then the athlete's `Adapted:` block, which may also adapt what a level
    /// put in (SPEC §9.1).
    func levels(_ blocks: [BlockNode]) -> (levels: JSONObject, adapted: [JSONValue]?) {
        var out = JSONObject()
        let ordered: [BlockNode] = blocks.filter { $0.kind != "adapted" } + blocks.filter { $0.kind == "adapted" }
        for level in ordered {
            var known: Set<String> = Set(movementIds)
            if level.kind == "adapted" {
                for key in out.keys {
                    for operation in out[key]?.arrayValue ?? [] {
                        if let replacement = operation.objectValue?["replace_with"]?.stringValue {
                            known.insert(replacement)
                        }
                    }
                }
            }
            if out.has(level.kind) {
                let shown: String = level.kind.prefix(1).uppercased() + level.kind.dropFirst()
                err("E041", "Duplicate '\(shown):' block.", level.span)
                continue
            }
            var operations: [JSONValue] = []
            for statement in level.children {
                if let metaLine = statement as? MetaLine {
                    if !["vest", "cap", "note"].contains(metaLine.key) {
                        err(
                            "E014",
                            "A level block cannot change '\(metaLine.key)'.",
                            metaLine.span,
                            "only vest, cap and note can be adapted"
                        )
                        continue
                    }
                    let lowered: String = metaLine.value.trimmingCharacters(in: .whitespaces).lowercased()
                    if metaLine.key == "vest", ["none", "no", "off"].contains(lowered) {
                        var wrapper = JSONObject()
                        var inner = JSONObject()
                        inner["vest"] = .null
                        wrapper["meta"] = .object(inner)
                        operations.append(.object(wrapper))
                    } else {
                        var wrapper = JSONObject()
                        wrapper["meta"] = .object(meta(JSONObject(), [metaLine]))
                        operations.append(.object(wrapper))
                    }
                    continue
                }
                guard let mv = statement as? MovementLine else {
                    let span: Span = (statement as? BlockNode)?.span
                        ?? (statement as? RestLine)?.span
                        ?? (statement as? UseLine)?.span
                        ?? level.span
                    err("E014", "A level block only contains movement lines.", span)
                    continue
                }
                if let operation = levelOperation(mv, level, known) {
                    operations.append(.object(operation))
                }
            }
            out[level.kind] = .array(operations)
        }
        let adapted: [JSONValue]? = out.removeValue(forKey: "adapted")?.arrayValue
        return (out, adapted)
    }

    private func levelOperation(_ mv: MovementLine, _ level: BlockNode, _ known: Set<String>) -> JSONObject? {
        guard let entry = opt.catalog.get(mv.name) else {
            err("E020", "Unknown movement '\(mv.name)'.", mv.nameSpan)
            return nil
        }
        if !known.contains(entry.id) {
            err(
                "E040",
                "\(entry.name) does not appear in the Rx work.",
                mv.nameSpan,
                "a level block only adapts movements of the workout"
            )
            return nil
        }
        var target: MovementEntry = entry
        var operation = JSONObject()
        operation["movement"] = .string(entry.id)
        if let replaceWith = mv.replaceWith {
            guard let replacement = opt.catalog.get(replaceWith) else {
                let hints: [String] = opt.catalog.suggest(replaceWith)
                let suggestion: String? = hints.isEmpty
                    ? nil
                    : "did you mean " + hints.map { "'\($0)'" }.joined(separator: " or ") + "?"
                err("E020", "Unknown movement '\(replaceWith)'.", mv.replaceSpan ?? mv.nameSpan, suggestion)
                return nil
            }
            operation["replace_with"] = .string(replacement.id)
            operation["name"] = .string(replacement.name)
            target = replacement
        }
        if !mv.selectorParams.isEmpty {
            var selector = JSONObject()
            for param in mv.selectorParams {
                self.param(&selector, param, entry)
            }
            var when = JSONObject()
            if let load = selector["load"] {
                when["load"] = load
            }
            if let height = selector["height"] {
                when["height"] = height
            }
            if !when.isEmpty {
                operation["when"] = .object(when)
            }
        }
        var params = JSONObject()
        for param in mv.params {
            self.param(&params, param, target)
        }
        if let quantity = mv.quantity, level.kind == "adapted", mv.replaceWith == nil {
            // the athlete's own count: "5 Wall walk" — what was actually done
            if let compiled = compileQuantity(quantity, entry) {
                operation["quantity"] = .object(compiled)
            }
        } else if let quantity = mv.quantity {
            err(
                "E014",
                "A level block only changes quantities after the arrow.",
                quantity.span,
                "e.g. '\(entry.name) -> 2x \(target.name)'"
            )
        }
        if let factor = mv.factor {
            operation["factor"] = .number(factor)
        }
        if let replaceQuantity = mv.replaceQuantity, let quantity = compileQuantity(replaceQuantity, target) {
            operation["quantity"] = .object(quantity)
        }
        for key in params.keys {
            operation[key] = params[key]
        }
        operation["source"] = sourceDict(mv.nameSpan)
        return operation
    }

    // MARK: - score

    func score(_ blocks: [JSONObject], _ meta: JSONObject) -> JSONObject {
        let timedIndexes: [Int] = blocks.indices.filter { timedKinds.contains(blocks[$0]["type"]?.stringValue ?? "") }
        let total: Bool = meta["score_total"] != nil
        if timedIndexes.count > 1, total, let declared = meta["score"]?.stringValue {
            return totalScore(blocks, timedIndexes, declared, meta)
        }
        if timedIndexes.count > 1, !meta.has("score") {
            var parts: [JSONValue] = []
            for index in timedIndexes {
                let kind: String = blocks[index]["type"]?.stringValue ?? ""
                var part = JSONObject()
                part["type"] = .string(scoreByFormat[kind] ?? "none")
                part["block"] = .number(Double(index))
                if case .bool(true)? = blocks[index]["there_and_back"] {
                    part["there_and_back"] = .bool(true)
                }
                parts.append(.object(part))
            }
            var out = JSONObject()
            out["type"] = .string("multi")
            out["parts"] = .array(parts)
            return out
        }
        let main: JSONObject? = blocks.first
        let kind: String = main?["type"]?.stringValue ?? "none"
        var inferred: String = scoreByFormat[kind] ?? "none"
        if kind == "movement", main?["sets"] != nil {
            inferred = "load"  // a bare strength line: the score is what you lifted
        }
        if intervalKinds.contains(kind), let main, hasMax(main) {
            inferred = "reps"
        }
        if kind == "rounds" || kind == "ladder", main?["for_time"] != nil {
            inferred = "time"
        }
        var out = JSONObject()
        if let declared = meta["score"]?.stringValue {
            if declared != inferred, !scoreCompatible(declared, kind) {
                let span: Span
                if let source = main?["source"]?.objectValue {
                    span = Span(source["line"]?.intValue ?? 1, source["col"]?.intValue ?? 1)
                } else {
                    span = Span(1, 1)
                }
                err(
                    "E036",
                    "A \(humanName(kind)) workout cannot be scored by '\(declared)'.",
                    span,
                    "this workout scores '\(inferred)'"
                )
                out["type"] = .string(inferred)
            } else {
                out["type"] = .string(declared)
            }
            if total {
                out["aggregate"] = .string("sum")  // "score: reps, total": every effort adds up (1.2)
            }
        } else {
            out["type"] = .string(inferred)
        }
        var cap: Double?
        if let value = meta["cap_s"]?.doubleValue, value != 0 {
            cap = value
        } else if let value = main?["cap_s"]?.doubleValue, value != 0 {
            cap = value
        }
        if out["type"]?.stringValue == "time", cap != nil {
            out["capped"] = .string("reps")
        }
        if let tiebreak = meta["tiebreak"], !tiebreak.isNull {
            out["tiebreak"] = tiebreak
        }
        if case .bool(true)? = main?["there_and_back"], out["type"]?.stringValue != "none" {
            // a round is the whole path, and a capped athlete counts the reps done along it
            out["there_and_back"] = .bool(true)
        }
        return out
    }

    /// 'score: load, total' over several timed blocks: one score per part, and they add up (1.2).
    func totalScore(_ blocks: [JSONObject], _ timedIndexes: [Int], _ declared: String, _ meta: JSONObject) -> JSONObject {
        var parts: [JSONValue] = []
        for index in timedIndexes {
            let block: JSONObject = blocks[index]
            let kind: String = block["type"]?.stringValue ?? ""
            if declared != scoreByFormat[kind], !scoreCompatible(declared, kind) {
                let source: JSONObject = block["source"]?.objectValue ?? JSONObject()
                err(
                    "E036",
                    "This \(humanName(kind)) part cannot be scored by '\(declared)', so it cannot count in the total.",
                    Span(source["line"]?.intValue ?? 1, source["col"]?.intValue ?? 1),
                    "this part scores '\(scoreByFormat[kind] ?? "none")'"
                )
            }
            var part = JSONObject()
            part["type"] = .string(declared)
            part["block"] = .number(Double(index))
            if case .bool(true)? = block["there_and_back"] {
                part["there_and_back"] = .bool(true)
            }
            parts.append(.object(part))
        }
        var out = JSONObject()
        out["type"] = .string("multi")
        out["aggregate"] = .string("sum")
        out["unit"] = .string(declared)
        out["parts"] = .array(parts)
        if let tiebreak = meta["tiebreak"], !tiebreak.isNull {
            out["tiebreak"] = tiebreak
        }
        return out
    }
}
