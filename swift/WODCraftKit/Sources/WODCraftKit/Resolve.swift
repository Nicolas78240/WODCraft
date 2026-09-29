/// Resolve a compiled workout for one athlete: level, category, units, percentages (SPEC §14).
///
/// A port of `src/wodcraft/semantics/resolve.py`.
import Foundation

/// The smallest plate change, per unit system.
enum PlateStep {
    static let kilograms = 2.5
    static let pounds = 5.0
}

// MARK: - Public entry points

public extension Workout {
    /// This workout as the given athlete should read it.
    ///
    /// Applies the level the profile asks for (falling back as SPEC §14 prescribes), keeps the
    /// value of the athlete's category, converts to their units and turns percentages into
    /// loads rounded to the plate.
    func resolved(for profile: AthleteProfile, catalog: Catalog = .shared) -> Workout {
        return Resolver(profile: profile, equivalences: catalog.equivalences).workout(self)
    }
}

public extension Session {
    /// Every section of the session, resolved for the athlete.
    func resolved(for profile: AthleteProfile, catalog: Catalog = .shared) -> Session {
        let resolver = Resolver(profile: profile, equivalences: catalog.equivalences)
        var copy = self
        var sections: [Section] = []
        for section in copy.sections {
            var resolvedSection = section
            resolvedSection.workout = resolver.workout(section.workout)
            sections.append(resolvedSection)
        }
        copy.sections = sections
        return copy
    }
}

public extension Document {
    /// The document, resolved for the athlete.
    func resolved(for profile: AthleteProfile, catalog: Catalog = .shared) -> Document {
        switch self {
        case let .workout(workout): return .workout(workout.resolved(for: profile, catalog: catalog))
        case let .session(session): return .session(session.resolved(for: profile, catalog: catalog))
        }
    }
}

// MARK: - Resolver

struct Resolver {
    let profile: AthleteProfile
    let equivalences: UnitEquivalences

    // MARK: Workout

    func workout(_ input: Workout) -> Workout {
        var out = input
        let level = appliedLevel(of: input)
        var operations: [LevelOperation] = []
        if let level = level {
            operations = input.levels?[level.rawValue] ?? []
        }

        var meta = out.meta
        let adapted: [LevelOperation]? = input.adapted
        // the level first, then the athlete's adaptation (SPEC §9.1)
        let stages: [[LevelOperation]] = [operations, adapted ?? []]
        for operation in operations + (adapted ?? []) {
            guard let changes = operation.meta else { continue }
            var current = meta ?? Meta()
            for key in changes.keys.sorted() {
                apply(key: key, value: changes[key] ?? .none, to: &current)
            }
            meta = current
        }

        var blocks: [Item] = []
        for item in out.blocks { blocks.append(self.item(item, stages: stages)) }
        out.blocks = blocks

        if var current = meta, let vest = current.vest {
            current.vest = flatten(load: vest)
            meta = current
        }
        out.meta = meta
        out.resolved = Resolved(
            category: profile.category,
            level: level?.rawValue ?? AthleteLevel.rx.rawValue,
            units: profile.units.rawValue
        )
        if adapted != nil { out.resolved?.adapted = true }
        out.levels = nil
        out.adapted = nil
        return out
    }

    /// The level whose operations apply, or `nil` for Rx (the workout as written).
    func appliedLevel(of workout: Workout) -> AthleteLevel? {
        let available = workout.levels ?? [:]
        for level in profile.levelsToTry() {
            if level == .rx { return nil }
            if available[level.rawValue] != nil { return level }
        }
        return nil
    }

    /// Write one meta change into the meta block, or erase it when the value is `none`.
    func apply(key: String, value: MetaValue, to meta: inout Meta) {
        switch key {
        case "vest":
            if case let .load(load) = value {
                meta.vest = load
            } else if case .none = value {
                meta.vest = nil
            }
        case "tiebreak":
            if case let .text(text) = value { meta.tiebreak = text } else if case .none = value { meta.tiebreak = nil }
        case "date":
            if case let .text(text) = value { meta.date = text } else if case .none = value { meta.date = nil }
        case "time":
            if case let .text(text) = value { meta.time = text } else if case .none = value { meta.time = nil }
        case "tags":
            meta.tags = strings(from: value)
        case "notes", "note":
            meta.notes = strings(from: value)
        case "stimulus":
            meta.stimulus = strings(from: value)
        default:
            break
        }
    }

    func strings(from value: MetaValue) -> [String]? {
        switch value {
        case let .text(text): return [text]
        case let .list(list): return list
        case .load, .none: return nil
        }
    }

    // MARK: Blocks

    func block(_ input: Block) -> Block {
        return block(input, stages: [])
    }

    func block(_ input: Block, stages: [[LevelOperation]]) -> Block {
        var out = input
        var items: [Item] = []
        for item in out.items { items.append(self.item(item, stages: stages)) }
        out.items = items
        return out
    }

    /// A body holds items, not only blocks: a strength line stands on its own.
    func item(_ input: Item, stages: [[LevelOperation]]) -> Item {
        switch input {
        case let .movement(movement):
            return .movement(self.movement(movement, stages: stages))
        case .rest:
            return input
        case let .block(nested):
            return .block(block(nested, stages: stages))
        }
    }

    // MARK: Movements

    func movement(_ input: Movement, stages: [[LevelOperation]]) -> Movement {
        var item = input
        for operations in stages {
            apply(operations, to: &item)
        }
        return flattened(item, stages: stages)
    }

    /// The first operation that matches the movement adapts it.
    func apply(_ operations: [LevelOperation], to item: inout Movement) {
        for operation in operations {
            guard operation.movement == item.movement else { continue }
            if let when = operation.when, !matches(item, when) { continue }
            if let replacement = operation.replaceWith {
                item.movement = replacement
                item.name = operation.name ?? replacement
                item.load = nil
                item.height = nil
            }
            if let load = operation.load { item.load = load }
            if let height = operation.height { item.height = height }
            if let percent = operation.percent { item.percent = percent }
            if let rpe = operation.rpe { item.rpe = rpe }
            if let bodyweight = operation.bodyweight { item.bodyweight = bodyweight }
            if let quantity = operation.quantity { item.quantity = quantity }
            if let factor = operation.factor { multiply(&item, by: factor) }
            break
        }
    }

    func flattened(_ input: Movement, stages: [[LevelOperation]]) -> Movement {
        var item = input

        if let quantity = item.quantity { item.quantity = flatten(quantity: quantity) }
        if let load = item.load { item.load = flatten(load: load) }
        if let height = item.height { item.height = flatten(height: height) }
        if let percent = item.percent, let computed = fromPercent(percent) { item.load = computed }
        if let bodyweight = item.bodyweight, let weight = profile.bodyweightKg {
            let factor = pick(bodyweight)
            item.load = roundToPlate(kilograms: weight * factor)
        }
        if let options = item.or {  // every option of an alternative is resolved the same way
            item.or = options.map { movement($0, stages: stages) }
        }
        return item
    }

    /// `A -> 2x B`: the quantity is multiplied; a movement that takes its reps from a ladder keeps
    /// the factor, and does factor × the ladder value.
    func multiply(_ item: inout Movement, by factor: Double) {
        guard var quantity = item.quantity, quantity.kind != .max else {
            item.factor = tidy(factor * (item.factor ?? 1))
            return
        }
        func scaled(_ amount: Amount?) -> Amount? {
            switch amount {
            case let .single(value)?: return .single(tidy(value * factor))
            case let .dual(men, women)?: return .dual(men: tidy(men * factor), women: tidy(women * factor))
            case nil: return nil
            }
        }
        quantity.reps = scaled(quantity.reps)
        quantity.cal = scaled(quantity.cal)
        quantity.s = scaled(quantity.s)
        quantity.m = scaled(quantity.m)
        quantity.written = scaled(quantity.written)
        item.quantity = quantity
    }

    func matches(_ item: Movement, _ when: LevelOperation.When) -> Bool {
        if let expected = when.load {
            guard let actual = item.load else { return false }
            if actual.written != expected.written || actual.unit != expected.unit { return false }
        }
        if let expected = when.height {
            guard let actual = item.height else { return false }
            if actual.written != expected.written || actual.unit != expected.unit { return false }
        }
        return true
    }

    // MARK: Flattening

    func pick(_ amount: Amount) -> Double {
        return amount.value(for: profile.category)
    }

    func flatten(quantity: Quantity) -> Quantity {
        var out = quantity
        if let reps = out.reps { out.reps = .single(pick(reps)) }
        if let cal = out.cal { out.cal = .single(pick(cal)) }
        if let seconds = out.s { out.s = .single(pick(seconds)) }
        if let metres = out.m { out.m = .single(pick(metres)) }
        if let written = out.written { out.written = .single(pick(written)) }
        return out
    }

    func flatten(load: Load) -> Load {
        let kg = pick(load.kg)
        var pounds: Double?
        if let lb = load.lb { pounds = pick(lb) }
        let value: Double
        if profile.units == .kg {
            value = kg
        } else if let pounds = pounds {
            value = pounds
        } else {
            value = kg / Conversion.kilogramsPerPound
        }
        var out = Load(kg: .single(tidy(kg)))
        out.unit = profile.units.rawValue
        out.value = tidy(value)
        return out
    }

    func flatten(height: Height) -> Height {
        let cm = pick(height.cm)
        let inches: Double
        if let written = height.inches {
            inches = pick(written)
        } else {
            inches = cm / Conversion.centimetresPerInch
        }
        let imperial = profile.units == .lb
        var out = Height(cm: .single(tidy(cm)))
        out.unit = imperial ? "in" : "cm"
        out.value = tidy(imperial ? inches : cm)
        return out
    }

    func fromPercent(_ percent: Percent) -> Load? {
        guard let of = percent.of, let reference = profile.oneRepMax(of: of), reference != 0 else { return nil }
        let share = pick(percent.value) / 100.0
        return roundToPlate(kilograms: reference * share)
    }

    /// Round a load to the smallest plate change of the athlete's unit system.
    func roundToPlate(kilograms: Double) -> Load {
        if profile.units == .lb {
            let pounds = kilograms / Conversion.kilogramsPerPound
            let rounded = Conversion.pythonRound(pounds / PlateStep.pounds) * PlateStep.pounds
            var out = Load(kg: .single(tidy(rounded * Conversion.kilogramsPerPound)))
            out.unit = "lb"
            out.value = tidy(rounded)
            return out
        }
        let rounded = Conversion.pythonRound(kilograms / PlateStep.kilograms) * PlateStep.kilograms
        var out = Load(kg: .single(tidy(rounded)))
        out.unit = "kg"
        out.value = tidy(rounded)
        return out
    }

    func tidy(_ value: Double) -> Double {
        return Conversion.pythonRound(value, 2)
    }
}

// MARK: - Convenience

public extension Load {
    init(kg: Amount) {
        self.init(kg: kg, lb: nil, unit: nil, written: nil, value: nil)
    }
}

public extension Height {
    init(cm: Amount) {
        self.init(cm: cm, inches: nil, unit: nil, written: nil, value: nil)
    }
}
