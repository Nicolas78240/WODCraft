# WODCraftKit

The WODCraft 1.0 language in Swift, for iOS, watchOS and macOS applications. **Offline**, with no
third-party dependency — Foundation only.

```swift
let result = WODCraft.compile("""
# Fran
21-15-9 for time, cap 10:00
  Thruster 95/65 lb
  Pull-up
""")

guard result.ok, case let .workout(fran)? = result.document else {
    return result.diagnostics    // code, line, column, message, suggestion — show them in the editor
}

let mine = fran.resolved(for: AthleteProfile(category: .women, units: .kilograms))
print(mine.whiteboard(language: .fr))  // the whiteboard, her loads, in French
fran.score.type                        // .time → ask for a stopwatch
fran.timeline()                        // the segments a timer plays
```

## What it carries

| | |
|---|---|
| **Model** | `Codable` types for the compiled document (`spec/workout.schema.json`) |
| **Compiler** | lexer, parser and semantic checks — the same diagnostics as the reference implementation |
| **Catalog** | 212 movements, English and French aliases, Rx loads, kg↔lb and cm↔in equivalences |
| **Library** | the 40 benchmarks (Girls, Heroes, Open), source and compiled, reachable with `use girls/fran` |
| **Athlete** | category, level, units and one-rep maxes — `resolved(for:)` |
| **Views** | `whiteboard()`, `markdown()`, `timeline()` |

Embedded resources: 115 kB.

## Conforming, not lookalike

`swift test` runs **124 tests**: the standard conformance suite (67 cases), the 40 library workouts
compiled and compared to the documents produced by the Python implementation, and every rendering
(English and French whiteboards, Markdown, timer, timeline) compared byte for byte on 77 documents.

```bash
swift test                      # macOS, no simulator needed
make -C ../.. swift-resources   # refresh Resources/ after changing the catalog or the library
```

## Using it in an application

Add it as a local package:

```swift
.package(path: "../packages/WODCraftKit")
```

Swift 6 strict concurrency, iOS 17 / macOS 13 / watchOS 9. The public API is `WODCraft`, `Catalog`,
`Library`, `AthleteProfile` and the model types; everything else is internal.
