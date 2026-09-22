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
        for operation in operations {
            guard let changes = operation.meta else { continue }
            var current = meta ?? Meta()
            for key in changes.keys.sorted() {
                apply(key: key, value: changes[key] ?? .none, to: &current)
            }
            meta = current
        }

        var blocks: [Block] = []
        for block in out.blocks { blocks.append(self.block(block, operations: operations)) }
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
        out.levels = nil
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
        return block(input, operations: [])
    }

    func block(_ input: Block, operations: [LevelOperation]) -> Block {
        var out = input
        var items: [Item] = []
        for item in out.items {
            switch item {
            case let .movement(movement):
                items.append(.movement(self.movement(movement, operations: operations)))
            case .rest:
                items.append(item)
            case let .block(nested):
                items.append(.block(block(nested, operations: operations)))
            }
        }
        out.items = items
        return out
    }

    // MARK: Movements

    func movement(_ input: Movement, operations: [LevelOperation]) -> Movement {
        var item = input
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
            break
        }

        if let quantity = item.quantity { item.quantity = flatten(quantity: quantity) }
        if let load = item.load { item.load = flatten(load: load) }
        if let height = item.height { item.height = flatten(height: height) }
        if let percent = item.percent, let computed = fromPercent(percent) { item.load = computed }
        if let bodyweight = item.bodyweight, let weight = profile.bodyweightKg {
            let factor = pick(bodyweight)
            item.load = roundToPlate(kilograms: weight * factor)
        }
        return item
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
