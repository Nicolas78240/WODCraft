# WODCraft standard library

Reference workouts written in WODCraft 1.0 (see `spec/SPEC.md`). One workout per file.

```
girls/     the 21 classic CrossFit "Girls" benchmarks
heroes/    10 Hero WODs
open/      selected CrossFit Games Open workouts (file name = <yy>_<n>)
```

## Using a workout

Any `.wod` file can pull a library workout in with `use`:

```wod
# Tuesday 23 September
## Metcon
use girls/fran
```

Paths are resolved against the current file's directory, then the directories given to the
compiler, then this standard library (§10 of the spec). The extension is omitted.

## Conventions

- Loads are written in the unit of the original prescription: `lb` for US benchmarks,
  `pood` for kettlebells, `in` for box heights. The compiler normalises to kg/cm using the
  official equivalence table (95 lb ↔ 43 kg, 24 in ↔ 60 cm, 1.5 pood ↔ 24 kg).
- Dual values are `men/women`, in that order.
- Rx work is written first; a `Scaled:` block, when present, lists only the differences.
- Time caps appear only when the original workout has an official one (the Open workouts,
  and the illustrative cap on `girls/fran`).
- Anything the language cannot express (free partitioning in Murph, wall-ball target height,
  "to failure" scoring) is stated in a `note:` line rather than invented syntax.

## Sources

- crossfit.com (benchmark and Hero WOD pages, workout of the day archive)
- games.crossfit.com (Open workout descriptions, scorecards and movement standards)
- wodwell.com and wodprep.com (cross-checks on loads, rep schemes and time caps)

Workout names and the Hero WODs remain the property of CrossFit, Inc.; they are reproduced
here as prescriptions, as they appear on gym whiteboards.
