# TX-31 — Restart laps tagged green while the safety car was out

**Group:** 0a bronze honesty · **Depends on:** TX-30 · **Model / cost:** `sonnet-5`, 0.5d

**How to run:** own scratch folder, copy named `dev.duckdb`, 1 thread. Never write `data/dev.duckdb`, `data/bronze/` or `data/fits/`. Nothing staged or committed by an agent.
**Class:** measured, transform class. Found while checking the extra lap times from FastF1 3.9.2 (HD22, 2026-11-17).

## Problem
Some laps run behind the safety car carry `TrackStatus = '1'` (all clear) in Bronze. `stg_laps.is_valid_lap` and `is_safety_car_lap` read only that string (`stg_laps.sql`, the `[4567]` test), so these laps count as valid green-flag laps and enter pace, degradation and residual aggregates. They are mostly the first lap or two after a restart, where the feed's status flips to green before the cars have actually released.

## Evidence (scratch build of stg_laps, 2026-11-17, read-only)
| Race | Lap | TrackStatus | Valid laps / cars | Median lap time |
|---|---|---|---|---|
| 2021_12 | 2 | `1` | 20 of 20 | 198.7 s |
| 2022_18 | 4 | `1` | 17 of 18 | 166.3 s |
| 2022_18 | 5 | `1` | 16 of 18 | 171.9 s |
| 2022_18 | 6 | `1` | 14 of 18 | 118.2 s (normal pace) |

Laps with these times are 40 to 70 s slower than racing pace. The count over all races ("and others") is not measured yet; step 1 below measures it.

## Fix options
A. Relabel from race control: build the neutralised window per race from `stg_race_control` messages (safety car deployed, "SAFETY CAR IN THIS LAP", "RESTART" / green) and mark a lap neutralised when it overlaps the window, whatever `TrackStatus` says. Gives a real label; needs a rule for the lap on which the car comes in.
B. Mark status unknown: add a flag (for example `track_status_suspect`) on laps whose time is far above the race median and whose neighbours are neutralised, and exclude them from `is_valid_lap` without claiming a cause. Cheaper, less precise.
Recommendation: A for the label, B as the fallback where race control has no message. The owner picks before any build.

## Method
1. Measure: list laps with `TrackStatus` free of 4/5/6/7 that fall within two laps after a neutralised lap and run more than 25% slower than the race median. Report the count per season.
2. Build the chosen option in `stg_laps.sql`; no change to Bronze.
3. Scratch rebuild, diff `is_valid_lap` and downstream row counts.

## Done when
The measured laps are labelled neutralised (or flagged unknown), the 2021_12 and 2022_18 laps above are excluded, and a test fails if a lap more than 25% slower than the race median sits between two neutralised laps with a green label.

## Sources
`transform/models/staging/stg_laps.sql`, `transform/models/staging/stg_race_control.sql`, `transform/models/staging/stg_track_status.sql`.
