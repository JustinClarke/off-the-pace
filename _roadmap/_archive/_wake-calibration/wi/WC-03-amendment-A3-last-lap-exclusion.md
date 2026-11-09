# WC-03 pre-registration, amendment A3: the last lap (and lap 1) as named exclusions

**Status: DRAFT. Not committed, not hashed. Decision recorded 2026-10-28 (see "Decision record" at the end): decided by the owner, delegated to the Opus session on 2026-10-28; not the owner's personal signature.** The owner chose this option (B: register the last lap as a named exclusion reason and count it). Registering `lap_1` in the same amendment was the drafter's proposal, with the reason given below; it is confirmed in the decision record. This file amends `wi/WC-03-preregistration-DRAFT.md` (signed 2026-10-28, SHA-256 `518c3348a619ebf6a964486bbe6313dcdc86c64ae05ca3daed8db202d9653a63`, commit `839e0f4`). The registered text is **not edited**: this file is read beside it (and beside amendments A1 and A2), and where they differ this file governs once it is committed and its SHA-256 is recorded on WC-03 in `status/build-log.json`.

**When it was made, stated plainly.** This amendment was drafted on 2026-10-28 (local machine clock, 18:06 +04:00; some earlier build-log entries carry 2026-10-29 stamps), **after** the synthetic G1 (i) test was seen to fail under the registered race-level bootstrap (amendment A1), and after a read-only inventory of the bronze lap and telemetry files (2026-10-28, build-log entry 2026-10-28T23:30) that counted the laps involved. **No real-data result has been seen:** nothing has been fitted, scored or gated on the pass table, the warehouse or the bronze files; the pass table has not been rebuilt; `data/dev.duckdb` has not been opened for this; G2 and G3 have not been run. The only real-data numbers behind this amendment are lap counts from that inventory (below), which carry no loss, curve, score or gate value. It is a pre-result amendment in the sense of §0. Whether that calls for any label beyond this paragraph is for the owner to rule.

**Nothing else changes.** No lap that the registered text would score becomes scored or unscored, no pass enters or leaves any fit, and no threshold, margin, season split, bin, trim, minimum or verdict rule changes. The amendment names and counts a drop that already happens.

---

## The change

Sections affected: **§4a** (new reason `last_lap`; `lap_1` restated at lap level) and **§8a** (steps 1 and 5: where the drop happens and how it is counted).

## The reason: the builder needs the neighbouring laps' telemetry

The WC-01 builder (`transform/tasks/wake_calibration/build_pass_table.py`) puts each car's race on one continuous distance axis so that a window can reach back over the start/finish line: the gap is read from 300 m before the segment start, and the segment runs to 100 m past the apex. It therefore builds lap L only when the driver's telemetry also has laps L−1 and L+1 (`CarTrace.lap_complete`, "laps L with L-1 and L+1 also present"; `find_apex_events` loops over those laps only). So:

- **A driver's final lap in the race has no pass rows.** There is no next lap's telemetry for the windows to cross the line into. Those rows are not made and so carry no `reason`.
- **Lap 1 has no pass rows**, by the same mechanism (there is no lap 0). The registered §4a lists "lap 1" as a pass-level reason, but WC-01 PROVENANCE item 13 already records that "reason lap_1 counts 0 by construction", and `exclusion_reasons_by_season.csv` shows `lap_1` = 0 in every season 2018-2025.

Under the registered §8a such laps already cannot be scored (they have no pass row to join in step 1, and step 2 needs a pass row at every braking corner), but the registered text gives them no reason: they fall into §2f's unnamed count "panel laps with no passes". §4a also does not mention the last lap at all. This amendment names both.

### Scale (inventory only; bronze lap and telemetry files, read-only, 2026-10-28)

Source: `bronze_laps_vs_telemetry_complete.csv` and `bronze_laps_by_season.csv` from the 2026-10-28 inventory (`laps_telemetry_counts.py`), which compare bronze laps (lap 2 on) with the (driver, lap) pairs present in bronze telemetry, using the builder's "L−1 and L+1 present" test. These are bronze laps, not yardstick-panel laps; the panel counts are produced by the run.

| Seasons | Laps from lap 2 with telemetry but not buildable | of which the driver's last lap | last lap and not a pit in/out lap | Lap-1 rows in bronze laps |
|---|---|---|---|---|
| 2018-2025 | 3,325 | 3,315 | 3,043 | 3,449 |
| 2022-2024 (main fit) | 1,320 | 1,319 | 1,216 | 1,354 |
| 2025 (held out) | 464 | 464 | 425 | 476 |

The 10 not-buildable laps that are not a last lap (2019: 1, 2020: 5, 2021: 3, 2022: 1; none in 2023-2025) are mid-race gaps in the telemetry; they are not given a reason here (see `no_pass_rows` below). 2018 Australia and Bahrain have no telemetry at all and are outside these columns (§2a: not built).

Laps from lap 2 with **no telemetry of their own** are also outside these columns. Under the step-1 order below the label goes by the lap's position, not by why it has no pass row: in the 2026-10-28 counting check on bronze laps 2018-2025, 44 such laps are a driver's last lap and are counted under `last_lap` (2018: 40, 2019-2022: 1 each), and 1,860 are not and are counted under `no_pass_rows` (2018: 1,857, 2020: 2, 2021: 1); 2023-2025 have none.

The number of **passes** these laps would have produced is not counted: no file holds it, and estimating it would need the pass table or the telemetry. An earlier scratch note put it at "roughly 50k" by multiplying by about 16 passes per lap; that is an estimate, not a count, and it is not part of this amendment.

## Exact new text

**§4a, first paragraph** — replace with:

> A pass is left out (it carries an exclusion `reason`) when any of these apply, first match wins: lap 1 (`lap_1`; in practice it never fires at pass level, because lap 1 has no pass row: see the next paragraph); no lap record or no lap time; the lap overlaps safety car, virtual safety car or red flag (`neutralised`); a sector yellow in marshal sector k excludes corners in sectors k and k+1 (`yellow_sector`, marshal sectors evenly spaced); the first 2 laps after a restart (`restart`); a pit in or out lap for the follower (`pit_lap`) or the car ahead (`pit_lap_leader`); wet (`wet`); the follower's lap deleted for track limits (`track_limits`); a corner with no clean-air pass in the race (`no_segment`); off-track samples (`off_track`); a car ahead exists but no gap could be measured (`no_gap`).

**§4a, new paragraph after the first** — insert:

> **Laps the builder never builds (amendment A3).** The builder builds a lap only when the driver's telemetry also has the lap before and the lap after, so that its windows can cross the start/finish line (`CarTrace.lap_complete`). Two laps therefore have no pass row at all and are excluded as whole laps, with a lap-level reason assigned in the WC-03 analysis layer (not in the builder, so G2 is unaffected):
> - `lap_1`: the driver's lap 1 (there is no lap 0 to reach back into). This is the same exclusion as the pass-level `lap_1` above, now counted where it actually acts.
> - `last_lap`: the driver's final lap in the race. Reason: the builder needs the next lap's telemetry to cross the line, so a driver's final lap in the race has no pass rows.
>
> Neither lap contributes a pass to any curve fit, to any reference or to the pit-stop figure, and neither is ever scored (§8a). θ_now is fitted on the yardstick panel, not on passes, and is not affected. Both labels go by the lap's position in the panel, not by why it has no pass row: a lap 1 or a driver's last lap with no pass row is counted under `lap_1` or `last_lap` even when that lap has no telemetry of its own. A panel lap with no pass row that is neither lap 1 nor the driver's last lap (for example, no telemetry for that lap, or a gap in the telemetry mid-race) gets no exclusion reason; it is counted under `no_pass_rows` (§8a).
>
> **A stint left too short (amendment A3).** A lap dropped at §8a step 4 because its panel stint (`stint_id`) is left with fewer than 2 laps is counted under `stint_under_2_laps`. This names an existing drop; it changes no lap that step 4 drops.

**§8a, Formal, step 1** — replace with:

> 1. Start from 2025 laps in the yardstick panel. A panel lap with no pass row cannot join the pass table (§2f) and is dropped here, before step 2. Each such lap is counted under exactly one reason, checked in this order (amendment A3): `lap_1` if `lap_number` < 2; `last_lap` if `lap_number` is the highest `lap_number` that driver has among the race's panel rows; otherwise `no_pass_rows`. The order is applied to every lap with no pass row whatever the cause, including a lap with no telemetry at all; it reads only the panel and the pass table's keys. The laps that remain join to the pass table (§2f) and go to step 2.

**§8a, Formal, step 5** — replace with:

> 5. Count every drop by its reason. Each dropped lap is counted once, under the first step and reason that drop it: at step 1 under `lap_1`, `last_lap` or `no_pass_rows` (amendment A3); at steps 2-3 by their reasons, as registered; at step 4 under `stint_under_2_laps` (amendment A3). The step-1 counts add up to §2f's "panel laps with no passes".

Unchanged: §8a steps 2-4 and the Plain English paragraph (step 4 drops the same laps as registered; A3 only names its count); §2f (its "panel laps with no passes" count is now broken down by the step-1 reasons); §12b ("every §8a drop by reason" now includes `lap_1`, `last_lap`, `no_pass_rows` and `stint_under_2_laps`; its text is not changed here — amendment A2 is the only amendment that rewrites the §12b "Counts" bullet).

## The last lap and the scored set, stated plainly

- **A last lap is simply out of the scored set.** It has no pass at any braking corner, so under §8a it can never meet step 2's "every braking corner of that race has a pass row on that lap". It is not scored with a cost of 0, not scored by any candidate, and not part of the clean-reference half, the no-reference half or the train laps. This was already so under the registered text; the amendment does not change which laps are scored.
- **How the drop is counted.** Once, at step 1, under `last_lap` (or under `lap_1` if the driver's last lap is lap 1). It is not counted again at step 2, and it never enters the step-3 baseline regression, so it cannot move any other lap's trim. If removing it leaves its stint with fewer than 2 laps, that stint's remaining lap is dropped at step 4, as registered, and counted there under `stint_under_2_laps`.
- **The fit side is untouched.** There are no last-lap or lap-1 passes in the pass table, so no fit set loses a row. θ_now (§2d) is fitted on the yardstick panel and is not restricted by this amendment.
- **Scope, stated as a limitation.** The verdict does not speak for a driver's final lap (or lap 1). Final laps can differ (old tyres, low fuel, last-lap fights or cruising). Every candidate is scored on the same laps, so the contest stays even, but the scorecard states the `last_lap` and `lap_1` counts in 2025 beside the scored-lap count.

## Lap 1: registered here, and why

**Decision: register `lap_1` in this amendment, at lap level, beside `last_lap`.** Reasons:

1. It is the same mechanism (no neighbouring lap's telemetry), so one rule covers both.
2. It is **not a new exclusion**: lap 1 is already excluded by the registered §4a. Counting it at lap level changes no scored lap and no fit.
3. Without it, §4a goes on saying lap-1 passes "carry an exclusion reason" that WC-01 shows counts 0 by construction, and lap-1 panel laps would be the one group of step-1 drops left unnamed in the §8a counts.

The pass-level reason `lap_1` in the builder and in the WC-01 count files is unchanged (it stays 0), so G2's byte-for-byte check is unaffected. If the yardstick panel holds no lap-1 rows, the lap-level `lap_1` count is reported as 0.

## What follows, stated so it is not decided silently

- **Code.** The analysis layer (`transform/tasks/wake_calibration/estimator.py`: `lap_step1_reason`, `short_stint_reason`, `lap_drop_counts`) assigns `lap_1`, `last_lap` and `no_pass_rows` at §8a step 1 and `stint_under_2_laps` at step 4, in the order above, with synthetic tests (`tests/test_estimator.py`, `test_a3_*`). Both are uncommitted at the time of the decision record. §8a step 3 (the ±5 s trim) is not in that code.
- **`no_pass_rows`** is a counting label, not an exclusion reason: those laps already cannot be scored. In the inventory there are no such 2025 laps from lap 2 on with telemetry, so it is expected to be at or near 0 for 2025; this is not asserted.
- **The other inventory findings** (VSC endings counted as restarts, `off_track` never firing, laps with no stint number) are not addressed here.

## Decision record

**Decided 2026-10-28. Decided by the owner, delegated to the Opus session on 2026-10-28; not the owner's personal signature.**

- **Option B is adopted:** `last_lap` and `lap_1` are registered as named lap-level exclusions, counted at §8a step 1 in the order `lap_1`, `last_lap`, `no_pass_rows`, as written in "Exact new text" above. The drafter's proposal to register `lap_1` in this amendment is confirmed, not struck.
- **Reading of the step-1 order:** the labels go by the lap's position in the panel, not by the cause of the missing pass rows. A driver's last panel lap with no pass row is `last_lap` even when it has no telemetry of its own; `no_pass_rows` is every other lap from lap 2 on with no pass row.
- **Step 4 label:** a lap dropped at §8a step 4 is counted under `stint_under_2_laps`.
- No threshold, scored lap, fit set or other registered text changes with this decision.

## After the decision is recorded

1. Commit this file alone.
2. `shasum -a 256 _roadmap/_wake-calibration/wi/WC-03-amendment-A3-last-lap-exclusion.md`; record the digest and commit on WC-03 in `status/build-log.json`.
3. Nothing is fitted or scored on real data before step 2 (BUILD-ORDER rule 4).
