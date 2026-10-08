/// Whiteboard rendering of a compiled (and optionally resolved) workout.
///
/// A port of `src/wodcraft/emit/board.py`. The output is byte-for-byte the text the Python
/// implementation writes, so the same fixtures check both.
import Foundation

// MARK: - Formatting primitives

/// Number formatting shared by every emitter: integers lose their decimal point.
func fmtNum(_ value: Double) -> String {
    if value.rounded() == value && value.isFinite && abs(value) < 1e15 {
        return String(Int(value))
    }
    return String(format: "%g", value)
}

/// `m:ss`, or `h:mm:ss` past the hour.
func formatClock(_ total: Double) -> String {
    let whole = Int(Conversion.pythonRound(total))
    let hours = whole / 3600
    let remainder = whole % 3600
    let minutes = remainder / 60
    let seconds = remainder % 60
    if hours != 0 {
        return String(format: "%d:%02d:%02d", hours, minutes, seconds)
    }
    return String(format: "%d:%02d", minutes, seconds)
}

/// The first value of an amount: the men's side of a dual.
func oneValue(_ amount: Amount) -> Double {
    return amount.value(for: .men)
}

/// `95/65 lb` for a dual, `43 kg` for a single.
func pairText(_ amount: Amount?, _ unit: String) -> String {
    guard let amount = amount else { return "" }
    if case let .dual(men, women) = amount {
        return fmtNum(men) + "/" + fmtNum(women) + " " + unit
    }
    return fmtNum(oneValue(amount)) + " " + unit
}

// MARK: - Board

/// The whiteboard emitter.
public enum Board {
    /// How each score kind is spelled on the board.
    public static func scoreLabel(_ kind: Score.Kind) -> String {
        switch kind {
        case .time: return "time"
        case .roundsAndReps: return "rounds + reps"
        case .rounds: return "rounds"
        case .reps: return "reps"
        case .load: return "load"
        case .distance: return "distance"
        case .calories: return "calories"
        case .none: return "no score"
        case .multi: return "one score per part"
        }
    }

    /// How the total of each score kind is spelled on the board (1.2).
    public static func totalLabel(_ kind: Score.Kind) -> String {
        switch kind {
        case .time: return "total time"
        case .roundsAndReps: return "total rounds + reps"
        case .rounds: return "total rounds"
        case .reps: return "total reps"
        case .load: return "total load"
        case .distance: return "total distance"
        case .calories: return "total calories"
        case .none, .multi: return scoreLabel(kind)
        }
    }

    /// What the score counts: `load`, `total load (best attempt of each lift)`…
    public static func scoreText(_ workout: Workout, language: Language = .en) -> String {
        let score = workout.score
        let unit: Score.Kind
        var text: String
        if score.isTotal {
            unit = score.unit ?? score.type
            text = word(totalLabel(unit), language)
        } else {
            unit = score.type
            text = word(scoreLabel(score.type), language)
        }
        let attempts: Bool = workout.blocks.contains { item in
            if case let .block(block) = item, block.type == .maxLoad, let count = block.attempts, count != 0 { return true }
            return false
        }
        if unit == .load, attempts {  // 1.2: the best of the attempts counts, for each lift
            text += " (" + word(score.type == .multi ? "best attempt of each lift" : "best attempt", language) + ")"
        }
        return text
    }

    /// The whiteboard text of a document.
    public static func render(
        _ document: Document,
        width: Int = 46,
        language: Language = .en,
        showProfile: Bool = true
    ) -> String {
        let localized = language == .en ? document : localize(document, language: language)
        switch localized {
        case let .session(session):
            return renderSession(session, width: width, showProfile: showProfile, language: language)
        case let .workout(workout):
            return renderWorkout(workout, width: width, skipTitle: false, showProfile: showProfile, language: language)
        }
    }

    // MARK: Localization

    /// Rewrite movement names in another language, using the catalog aliases.
    public static func localize(_ document: Document, language: Language, catalog: Catalog = .shared) -> Document {
        switch document {
        case let .workout(workout):
            return .workout(localize(workout, language: language, catalog: catalog))
        case var .session(session):
            var sections: [Section] = []
            for section in session.sections {
                var copy = section
                copy.workout = localize(section.workout, language: language, catalog: catalog)
                sections.append(copy)
            }
            session.sections = sections
            return .session(session)
        }
    }

    public static func localize(_ workout: Workout, language: Language, catalog: Catalog = .shared) -> Workout {
        var out = workout
        var blocks: [Item] = []
        for item in out.blocks { blocks.append(localize(item: item, language: language, catalog: catalog)) }
        out.blocks = blocks
        return out
    }

    private static func localize(block: Block, language: Language, catalog: Catalog) -> Block {
        var out = block
        var items: [Item] = []
        for item in out.items { items.append(localize(item: item, language: language, catalog: catalog)) }
        out.items = items
        return out
    }

    /// A body holds items, not only blocks: a strength line stands on its own.
    private static func localize(item: Item, language: Language, catalog: Catalog) -> Item {
        switch item {
        case let .movement(movement):
            return .movement(localize(movement: movement, language: language, catalog: catalog))
        case .rest:
            return item
        case let .block(nested):
            return .block(localize(block: nested, language: language, catalog: catalog))
        }
    }

    private static func localize(movement: Movement, language: Language, catalog: Catalog) -> Movement {
        var out = movement
        if let entry = catalog.movement(id: movement.movement) {
            out.name = entry.displayName(language)
        }
        out.or = movement.or?.map { localize(movement: $0, language: language, catalog: catalog) }
        return out
    }

    static let french: [String: String] = [
        "or": "ou",
        "there and back": "aller-retour",
        "Max load": "Charge max",
        "attempt": "essai",
        "attempts": "essais",
        "Rest": "Repos",
        "between attempts": "entre les essais",
        "best attempt": "meilleur essai",
        "best attempt of each lift": "meilleur essai de chaque barre",
        // the labels in front of the lines under the workout
        "Cap": "Cap",
        "Score": "Score",
        "Estimate": "Durée",
        "Session estimate": "Durée de la séance",
        "Vest": "Lest",
        "Note": "Note",
        "Stimulus": "Stimulus",
        "Levels": "Niveaux",
        "Adapted": "Adapté",
        "capped": "cap atteint",
        // what is scored
        "time": "temps",
        "rounds + reps": "tours + répétitions",
        "rounds": "tours",
        "reps": "répétitions",
        "load": "charge",
        "distance": "distance",
        "calories": "calories",
        "one score per part": "un score par partie",
        "total time": "total des temps",
        "total rounds + reps": "total des tours + répétitions",
        "total rounds": "total des tours",
        "total reps": "total des répétitions",
        "total load": "total des charges",
        "total distance": "distance totale",
        "total calories": "total des calories",
    ]

    /// The words of the board in another language ("or", "there and back", "Max load", "Score"…).
    public static func word(_ text: String, _ language: Language) -> String {
        guard language == .fr else { return text }
        return french[text] ?? text
    }

    /// `Score:` — or `Score :` in French, which puts a space before the colon.
    public static func label(_ text: String, _ language: Language) -> String {
        return word(text, language) + (language == .fr ? " :" : ":")
    }

    // MARK: Session

    static func renderSession(_ session: Session, width: Int, showProfile: Bool, language: Language = .en) -> String {
        var lines: [String] = [titleText(session.title ?? "Session")]
        var head: [String] = []
        if let date = session.date, !date.isEmpty { head.append(date) }
        if let time = session.time, !time.isEmpty { head.append(time) }
        if !head.isEmpty { lines.append(head.joined(separator: " · ")) }
        for section in session.sections {
            lines.append("")
            lines.append(section.title.uppercased())
            lines.append(
                renderWorkout(section.workout, width: width, skipTitle: true, showProfile: showProfile, language: language)
            )
        }
        if let estimate = session.estimate {
            lines.append("")
            lines.append(label("Session estimate", language) + " " + rangeText(estimate))
        }
        var text = lines.joined(separator: "\n")
        while let last = text.last, last == " " || last == "\n" || last == "\t" || last == "\r" {
            text.removeLast()
        }
        return text + "\n"
    }

    // MARK: Workout

    static func renderWorkout(
        _ workout: Workout,
        width: Int,
        skipTitle: Bool,
        showProfile: Bool,
        language: Language = .en
    ) -> String {
        var lines: [String] = []
        if !skipTitle, let title = workout.title, !title.isEmpty {
            lines.append(titleText(title))
        }
        if let cap = workout.capS, cap != 0 {  // a cap on the whole workout has its own line (1.2)
            lines.append(label("Cap", language) + " " + formatClock(cap))
        }
        let meta = workout.meta
        var body: [String] = []
        for block in workout.blocks {
            body.append(contentsOf: blockLines(block, depth: 0, width: width, language: language))
        }
        if let team = workout.team, !body.isEmpty {
            body[0] = "Teams of " + String(team.size) + " · " + body[0]
        }
        lines.append(contentsOf: body)
        if let vest = meta?.vest {
            lines.append(label("Vest", language) + " " + loadText(vest))
        }
        let score = workout.score
        if score.type != Score.Kind.none {
            var text = scoreText(workout, language: language)
            if let capped = score.capped {
                text += " (" + label("capped", language) + " " + word(scoreLabel(capped), language) + ")"
            }
            lines.append(label("Score", language) + " " + text)
        }
        if let estimate = workout.estimate {
            lines.append(label("Estimate", language) + " " + rangeText(estimate))
        }
        for note in meta?.notes ?? [] { lines.append(label("Note", language) + " " + note) }
        for stimulus in meta?.stimulus ?? [] { lines.append(label("Stimulus", language) + " " + stimulus) }
        if let levels = workout.levels, !levels.isEmpty {
            lines.append(label("Levels", language) + " " + levels.keys.sorted().joined(separator: ", "))
        }
        let changes: [String] = (workout.adapted ?? []).compactMap { adaptationText($0, language: language) }
        if !changes.isEmpty {
            lines.append(label("Adapted", language) + " " + changes.joined(separator: "; "))
        }
        if showProfile, let resolved = workout.resolved {
            let level = resolved.level + (resolved.adapted == true ? " + adapted" : "")
            lines.append("[" + resolved.category.rawValue + " · " + level + " · " + resolved.units + "]")
        }
        return lines.joined(separator: "\n")
    }

    /// One change of the athlete's `Adapted:` block: `Bar muscle-up -> 2x Chest-to-bar pull-up`.
    static func adaptationText(_ operation: LevelOperation, language: Language, catalog: Catalog = .shared) -> String? {
        guard let movement = operation.movement else { return nil }
        func name(_ identifier: String) -> String {
            catalog.movement(id: identifier)?.displayName(language) ?? identifier
        }
        let source = name(movement)
        let target = name(operation.replaceWith ?? movement)
        var amount = quantityText(operation.quantity)
        if amount.isEmpty, let factor = operation.factor, factor != 0 { amount = fmtNum(factor) + "x" }
        let changed = amount.isEmpty ? target : amount + " " + target
        return changed == source ? changed : source + " -> " + changed
    }

    static func titleText(_ title: String) -> String {
        return title.uppercased()
    }

    // MARK: Blocks

    static func blockLines(_ item: Item, depth: Int, width: Int, language: Language = .en) -> [String] {
        switch item {
        case let .movement(movement):
            let pad = padding(depth)
            return [pad + movementText(movement, width: width - pad.count, language: language)]
        case let .rest(rest):
            return [padding(depth) + word("Rest", language) + " " + formatClock(rest.seconds)]
        case let .block(block):
            return blockLines(block, depth: depth, width: width, language: language)
        }
    }

    static func blockLines(_ block: Block, depth: Int, width: Int, language: Language = .en) -> [String] {
        let pad = padding(depth)
        let head = headText(block, language: language)
        let items = block.items
        let inlineKinds: [Block.Kind] = [.slot, .buyIn, .cashOut]
        if !head.isEmpty, inlineKinds.contains(block.type), items.count == 1,
           case let .movement(movement) = items[0] {
            let inner = movementText(movement, width: width - pad.count - head.count - 1, language: language)
            return [pad + head + " " + inner]
        }
        var lines: [String] = head.isEmpty ? [] : [pad + head]
        let childDepth = depth + (head.isEmpty ? 0 : 1)
        let attempts: Bool = block.type == .maxLoad && (block.attempts ?? 0) != 0
        for (index, item) in items.enumerated() {
            var inner = blockLines(item, depth: childDepth, width: width, language: language)
            if attempts, case .rest = item, index == items.count - 1, let first = inner.first {
                inner = [first + " " + word("between attempts", language)]  // SPEC §8: between the attempts
            }
            lines.append(contentsOf: inner)
        }
        return lines
    }

    static func padding(_ depth: Int) -> String {
        if depth <= 0 { return "" }
        var pad = ""
        for _ in 0..<depth { pad += "  " }
        return pad
    }

    /// The header line of a block: `AMRAP 20:00`, `21-15-9 for time`, `Odd:`…
    static func headText(_ block: Block, language: Language = .en) -> String {
        var parts: [String] = []
        var ladderPieces: [String] = []
        for rep in block.reps ?? [] { ladderPieces.append(String(rep)) }
        let ladder = ladderPieces.joined(separator: "-")
        let rounds = block.rounds
        let repsOpen = block.repsOpen ?? false

        switch block.type {
        case .forTime:
            var core: String
            if !ladder.isEmpty {
                core = ladder + (repsOpen ? " …" : "")
            } else if let rounds = rounds {
                core = String(rounds) + " rounds"
            } else {
                core = ""
            }
            if core.isEmpty {
                parts.append("For time")
            } else {
                core = (core + " for time").trimmingCharacters(in: .whitespaces)
                parts.append(core)
            }
        case .amrap:
            parts.append("AMRAP " + formatClock(block.durationS ?? 0))
            if !ladder.isEmpty {  // a ladder merged into its AMRAP (SPEC §13): the reps still belong on the board
                parts.append(ladder + (repsOpen ? " …" : ""))
            }
        case .emom:
            let interval = Int((block.intervalS ?? 60) / 60)
            let name = interval <= 1 ? "EMOM" : "E" + String(interval) + "MOM"
            parts.append(name + " " + formatClock(block.durationS ?? 0))
        case .every:
            parts.append("Every " + formatClock(block.intervalS ?? 0) + " x " + optionalNumber(rounds))
        case .tabata:
            let count = rounds ?? 8
            parts.append("Tabata" + (count == 8 ? "" : " " + String(count)))
        case .deathBy:
            parts.append("Death by")
        case .maxLoad:
            parts.append(word("Max load", language))
            if let attempts = block.attempts, attempts != 0 {
                parts.append(String(attempts) + " " + word(attempts == 1 ? "attempt" : "attempts", language))
            }
        case .rounds:
            parts.append(optionalNumber(rounds) + " rounds")
        case .ladder:
            parts.append(ladder + (repsOpen ? " …" : ""))
        case .slot:
            switch block.slot {
            case .some(.odd): return "Odd:"
            case .some(.even): return "Even:"
            case let .some(.minute(number)): return "Min " + String(number) + ":"
            case .none: return "Min None:"
            }
        case .buyIn:
            return "Buy-in:"
        case .cashOut:
            return "Cash-out:"
        }

        if let cap = block.capS, cap != 0 {
            parts.append("cap " + formatClock(cap))
        }
        if block.thereAndBack == true {
            parts.append(word("there and back", language))
        }
        if let teams = block.teams, teams != 0 {
            parts.insert("Teams of " + String(teams), at: 0)
        }
        if let used = block.used {
            let name = used.title ?? used.path
            parts.append("[" + (name.isEmpty ? used.path : name) + "]")
        }
        return parts.joined(separator: " · ")
    }

    /// Python prints `None` for a missing number; keep the same shape so nothing silently differs.
    static func optionalNumber(_ value: Int?) -> String {
        guard let value = value else { return "None" }
        return String(value)
    }

    // MARK: Movements

    static func movementText(_ item: Movement, width: Int, dots: Bool = true, language: Language = .en) -> String {
        if let options = item.or, !options.isEmpty {  // an alternative: every option in full, joined by "or"
            let texts: [String] = item.options.map { movementText($0, width: 0, dots: false) }
            return texts.joined(separator: " " + word("or", language) + " ")
        }
        var leftParts: [String] = []
        var quantity = quantityText(item.quantity)
        if quantity.isEmpty, let factor = item.factor, factor != 0 { quantity = fmtNum(factor) + "x" }
        if !quantity.isEmpty { leftParts.append(quantity) }
        if !item.name.isEmpty { leftParts.append(item.name) }
        let left = leftParts.joined(separator: " ")

        var rightParts: [String] = []
        if let sets = item.sets, !sets.reps.isEmpty { rightParts.append(setsText(sets)) }
        if let load = item.load {
            rightParts.append(loadText(load))
        } else if let percent = item.percent {
            rightParts.append(fmtNum(oneValue(percent.value)) + "%")
        }
        if let height = item.height { rightParts.append(heightText(height)) }
        if let rpe = item.rpe, isTruthy(rpe) { rightParts.append("RPE " + fmtNum(oneValue(rpe))) }
        if let modifiers = item.modifiers, !modifiers.isEmpty {
            rightParts.append("(" + modifiers.joined(separator: ", ") + ")")
        }
        let right = rightParts.joined(separator: " ")
        if right.isEmpty { return left }
        if !dots || width <= 0 { return left + " " + right }
        let filler = max(1, width - left.count - right.count - 2)
        var dotsText = ""
        for _ in 0..<filler { dotsText += "." }
        return left + " " + dotsText + " " + right
    }

    /// Python truthiness of an amount: a dual is always truthy, a single only when non-zero.
    static func isTruthy(_ amount: Amount) -> Bool {
        if case let .single(value) = amount { return value != 0 }
        return true
    }

    static func quantityText(_ quantity: Quantity?) -> String {
        guard let quantity = quantity else { return "" }
        switch quantity.kind {
        case .max:
            return "max"
        case .reps:
            guard let reps = quantity.reps else { return "" }
            if case let .dual(men, women) = reps {
                return fmtNum(men) + "/" + fmtNum(women)
            }
            return fmtNum(oneValue(reps))
        case .distance:
            let amount = quantity.written ?? quantity.m
            return pairText(amount, quantity.unit ?? "m")
        case .calories:
            return pairText(quantity.cal, "cal")
        case .time:
            guard let seconds = quantity.s else { return "" }
            return formatClock(oneValue(seconds))
        }
    }

    static func loadText(_ load: Load) -> String {
        if let value = load.value {
            return fmtNum(value) + " " + (load.unit ?? "kg")
        }
        let unit = load.unit ?? "kg"
        var amount = load.written
        if amount == nil {
            amount = unit == "lb" ? load.lb : load.kg
        }
        return pairText(amount ?? load.kg, unit)
    }

    static func heightText(_ height: Height) -> String {
        if let value = height.value {
            return fmtNum(value) + " " + (height.unit ?? "cm")
        }
        let unit = height.unit ?? "cm"
        var amount = height.written
        if amount == nil {
            amount = unit == "in" ? height.inches : height.cm
        }
        return pairText(amount ?? height.cm, unit)
    }

    static func setsText(_ sets: Sets) -> String {
        let reps = sets.reps
        var uniform = true
        for rep in reps where rep != reps[0] { uniform = false }
        if !reps.isEmpty && uniform {
            return String(reps.count) + "x" + String(reps[0])
        }
        var pieces: [String] = []
        for rep in reps { pieces.append(String(rep)) }
        return pieces.joined(separator: "-")
    }

    static func rangeText(_ estimate: Estimate) -> String {
        let low = estimate.minS
        let high = estimate.maxS
        if abs(high - low) < 30 { return formatClock(low) }
        return formatClock(low) + "\u{2013}" + formatClock(high)
    }
}

// MARK: - Sugar

public extension Workout {
    /// The whiteboard text of this workout.
    func whiteboard(width: Int = 46, language: Language = .en, showProfile: Bool = true) -> String {
        return Board.render(.workout(self), width: width, language: language, showProfile: showProfile)
    }
}

public extension Session {
    /// The whiteboard text of this session.
    func whiteboard(width: Int = 46, language: Language = .en, showProfile: Bool = true) -> String {
        return Board.render(.session(self), width: width, language: language, showProfile: showProfile)
    }
}

public extension Document {
    /// The whiteboard text of this document.
    func whiteboard(width: Int = 46, language: Language = .en, showProfile: Bool = true) -> String {
        return Board.render(self, width: width, language: language, showProfile: showProfile)
    }
}
