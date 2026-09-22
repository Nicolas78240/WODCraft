# WODCraftKit

The WODCraft 1.0 language and compiled model, in Swift, for iOS, watchOS and macOS applications.

- **Model** — `Codable` types for the compiled document described by `spec/workout.schema.json`.
- **Catalog and library** — the 212 movements and the 40 benchmark workouts, embedded as JSON.
- **Compiler** — `WODCraft.compile(source:)` parses and checks `.wod` text offline, and returns the
  same document the Python reference implementation produces.
- **Views** — a whiteboard renderer and a timeline, ready for a timer or a Live Activity.

The resources come from `wodc bundle`; the test target runs the standard conformance suite
(`spec/conformance/`), which is what makes this a conforming implementation rather than a lookalike.

```bash
make -C ../.. swift-resources   # refresh Resources/ from the Python implementation
swift test
```
