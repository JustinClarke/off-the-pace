# WI-15 — Traffic and thermal feature semantics

**Group:** 02 feature expansion · **Depends on:** nothing structurally, but the θ part of F48 rides
`WI-01`'s label bump (re-estimate once, after F1 and this file's feature-coding fix both land).
**Blocker:** a contract ablation decision per `foundations/gates.md` — these are feature-*meaning*
changes, not label changes, so they go through the standard feature-contract process, not a version
bump.

**Executed as two board items.** `WI-15a` = F43 + F48's coding side (the traffic half) and `WI-15b` =
F47 + F49 (the thermal half, which carries the ablation). Only `WI-15a` has to land before `WI-01`'s
θ_air re-estimate — this doc's Definition of done says "this file's fixes", which is broader than
needed: checked 2026-09-24 that `int_lap_air_state.sql` takes its gaps from raw telemetry (not from
`int_lap_proximity`, which F43 fixes) and that `int_dirty_air_tax_component.sql`'s `ref()` list contains
no thermal or proximity model, so the thermal half cannot move θ.

**Findings folded in:** F43 (Low-Med), F47 (Low-Med), F48 feature-coding side (Low-Med), F49 (Low,
also an ML contract feature).

**Reverification:** all CONFIRMED-AS-STATED, with two severity notes: F47 and F49 both touch live ML
contract features, not just fan pages, which the original reports already disclose but don't
foreground in their severity tags.

---

## F43 — a car in the pit lane counts as "the car ahead"

`int_lap_proximity.sql`'s crossing/ordering window has no pit-lane filter anywhere (confirmed: grep
for "pit" in the full file returns only two unrelated comments). `stg_telemetry_position.sql`'s own
header (~lines 20-25) explicitly states pit-lane samples are kept "in order to exclude them
downstream with a reason rather than silently" — **a designed-for exclusion that was never
implemented.** `stg_pits.sql` already produces `pit_in_time_s`/`pit_out_time_s` on the same session
clock — exactly the oracle needed and already available, no new data required. Confirmed live:
`gap_ahead_min_s` changes on 6,355 training-eligible rows (4.5%), median 0.88s (pit-lane car) vs.
3.32s (on-track car), 2,932 rows crossing the 1s "within range" threshold.

## F47 — the push proxy reads fuel burn as pushing

`int_lap_thermal_proxy.sql:46-49` builds `push_residual` on **raw** `stg_laps.lap_time_s`, not
`weight_corrected_lap_time` — confirmed by direct read (`int_field_pace_curve.sql` already uses the
corrected column elsewhere in the tree, so the fix pattern exists to copy). Re-run fuel-corrected:
late in a stint (lap_in_stint 21+), the share of laps coded "pushing" drops from 67.7% to 30.8%,
about 63% of the bulk load at that point is fuel burn, not genuine pace variation.
**Reverification note:** `push_residual`, `cumulative_push_load_surface/bulk`, and
`surface_bulk_ratio` are genuine contract features used by all five model families, not fan-only —
this is a training-contract feature-semantics defect, though its practical ML damage is likely
limited since `lap_in_stint` and `fuel_mass_kg` are already separate features carrying similar
information (the original report notes this redundancy itself).

## F48 — closest followers coded "no dirty air" (feature-coding side)

`int_lap_air_state.sql:116-125`: an S2 median gap **<1.0s with DRS active** is coded `drs_train`
(dirty-air share 0), while **1.0-1.5s** is coded `dirty_air` (share 1) — non-monotone in the gap
itself. Confirmed live: 45% of sub-1s-gap laps get coded clean. The θ_air re-estimation this feeds is
handled in `WI-01`; **this file only owns the feature-coding fix** (base exposure on gap alone, keep
DRS as a separate column) — the physics question of whether DRS-open laps genuinely carry less aero
load is explicitly unsettled in-tree (no telemetry-based aero measure exists), so "Probably wrong" is
the correct hedge, not "Definitely wrong."

## F49 — surface/bulk ratio is capped at 0.5 by mathematical construction

Independently re-derived the bound from `int_lap_thermal_proxy.sql`'s own weight schedule: surface
weights (1, .717, .514, .369, .264) are each ≤ the bulk weights at the same lag (1, .819, .670, .549,
.449), and bulk sums three additional non-negative lags surface doesn't have. Since both loads sum
the same non-negative `push_residual` series, `surface ≤ bulk` is a **mathematical certainty**, not
an empirical pattern — confirmed 0 of 164,030 laps violate it. `surface_driven` (needs >0.65) can
never fire; the class sits dead in `int_tyre_surface_vs_bulk_decoupling.sql:118`.
**Reverification note:** the identical ratio expression is byte-identical to ML contract feature #19
(`fct_cliff_prediction_features.sql:544-550`), used across all five model families for every row —
the original report's own text already discloses this, but the "Low(fan)" severity tag undersells
it. Practically this likely doesn't hurt model performance much (trees can still split on relative
variation within [0, 0.5] — only the categorical `surface_driven` class is genuinely dead), so no
severity upgrade is warranted, but the fix should be scoped to touch both the ML-contract feature
(benign range compression) and the fan page (Tyre Recovery, which quotes 86-89% "recovery" against
the query's own 57.7-62.7%) together, since F49 depends entirely on F47's `push_residual`
construction — **fix F47 first, then re-derive F49's bound on the corrected feature.**

## Method

1. **F43.** Drop crossings that fall inside a car's own `stg_pits` pit window (join on session time)
   before the car-ahead ordering step.
2. **F47.** Switch `push_residual`'s baseline to `weight_corrected_lap_time`, as
   `int_field_pace_curve` already does. Re-run the thermal ablation (08e/08i) on the corrected
   feature to confirm the contract still benefits from it post-fix.
3. **F48 (feature side).** Base `dirty_air_share_lap`/`air_state_dominant` on the gap alone; carry
   `drs_active` as a separate column rather than folding it into the dirty-air classification. The
   θ_air re-estimation itself happens once, in `WI-01`, after this lands.
   *As built, narrower than this wording:* only the S2 (dirty-air) third is gap-only; the straight
   thirds keep their `drs_train`/`tow_zone` split. Why: see "As built: WI-15a" below.
4. **F49.** After F47 lands, normalize each load by its own weight sum before comparing (so the ratio
   reads 0.5 at steady push, not as a hard ceiling), or drop the `surface_driven` class entirely and
   rewrite the Tyre Recovery page's text to match whatever the corrected metric actually shows.

## Acceptance

- `gap_ahead_min_s` and related proximity features never treat a pit-lane car as on-track traffic.
- `push_residual` and its downstream loads are fuel-neutral, matching `int_field_pace_curve`'s
  existing convention.
- `dirty_air_share_lap` is monotone (non-increasing) in the measured gap.
- The surface/bulk ratio either reaches its full declared range or the dead class is removed and the
  Tyre Recovery page's claimed recovery rate matches its own query's output.

## Tests to add

T33 (F43), T37 (F47), T38 (F48 feature side), T39 (F49, reachability of declared categorical
classes).

## Definition of done

`verify_findings.py`'s F43, F47, F48, F49 checks flip to CLEARED (F48's θ-dependent check flips
alongside `WI-01`); this file's fixes land **before** `WI-01`'s θ re-estimation step so it only has to
run once.

## As built: WI-15a (2026-09-25)

Measured on a scratch copy of `data/dev.duckdb`, built twice from the same working tree (once with
the two models at `HEAD`, once fixed), `int_lap_proximity+ int_lap_air_state+` both times. The
`HEAD` build matches the live dev warehouse on every `fct_cliff_prediction_features` column within
1e-9 on all 137,759 training-eligible rows, so the before/after below is this item's effect alone.
`data/dev.duckdb` itself was **not** rebuilt (see the last paragraph).

**F43, as the Method says.** `int_lap_proximity` builds `pit_windows` from `stg_pits` and drops every
crossing inside the driver's own window before the car-ahead ordering. A stop with no recorded exit
closes `proximity_pit_window_open_s` (120 s) after entry; none of the 248 such stops has a crossing
past that bound. Two choices the Method did not spell out:
- The per-bin dwell time (`bin_duration_s`, read only by `time_within_1s`) is measured on the full
  crossing sequence *before* the filter, so the bin before pit entry keeps its real ~1 s instead of
  the 5 s clamp. Everything else equals the audit's own oracle (the round-3 probe's pit-window
  rebuild): 0 differing laps on 13 of 14 columns over 189,418 laps; `time_within_1s` differs on 877
  pit laps, by design.
- Two diagnostic columns, `gap_ahead_min_driver_id` and `gap_ahead_min_crossing_s` (never features),
  so T33 checks the output against `stg_pits` instead of trusting the filter.

Effect on eligible rows: `gap_ahead_min_s` moves on 6,288 (4.6%), median 0.90 s → 3.32 s, 2,896 of
them crossing the 1 s threshold, none turned NULL; the share features move on 1,454-5,042 rows each
(mean |Δ| ≤ 0.0005). F43 is label-neutral: `int_lap_proximity`'s only child is the mart.
**Not covered:** pit-lane race starts are not stops and have no `stg_pits` row. 139 lap-1 laps still
have a pit-lane starter as their closest car ahead, none training-eligible.

**F48: narrower than Method step 3's wording, on purpose.** S2 is classified on the gap alone (< 1.5 s
is `dirty_air` whatever DRS did). The straight thirds keep their `drs_train`/`tow_zone` split. DRS
and the S2 gap are carried as `s2_drs_active` and `s2_gap_median_s` (not in the ML contract). The
literal reading, taking DRS out of every third, was measured and rejected:

| On training-eligible rows | As built (S2 only) | Literal (every third) |
| :-- | --: | --: |
| `air_state_dominant` recoded | 4,377 (all `drs_train` → `dirty_air`) | 18,823 |
| Laps entering or leaving `int_field_pace_curve`'s clean-air set (`air_state_dominant IN ('free_air','tow_zone')`) | **0** | **16,308** |
| `tow_benefit_lap_s` changed | 0 | 25,409 |
| `drs_train` category | kept (13,194 rows) | retired |

The clean-air set is the field base's filter, so the literal reading would move the label through a
second path that neither this doc nor `WI-01` accounts for. It would also retire a category that the
shipped encoders, the Degradation Simulator's picker and the Lap Air Map all use. The as-built coding
satisfies the acceptance line (share monotone in the gap), matches the audit's own probe
(`r3_dirty_air_drs_train.py` recodes S2 only) and matches `verify_findings.py`'s "cleared means".

Effect: `dirty_air_share_lap` goes 0 → 1 on 11,540 eligible rows and 1 → 0 on none. No eligible S2
lap under 1 s is coded clean any more (25,624 of 25,624 are dirty). **F48 reaches the label through
θ_air only:** on the as-built panel θ_air moves **0.160673 → 0.264795** (+65%). Downstream, on
eligible rows: `next_5_lap_cumulative_jump_s` moves on 78,583 (mean |Δ| 0.227 s, max 2.06 s, 25,378
over 250 ms), `laps_until_cliff_class` on 2,638, `anomaly_class` on 554, and `is_training_eligible`
flips on 348. `int_field_pace_curve` is unchanged (0 rows). The θ re-estimate this implies is
`WI-01`'s, not this item's.

**Tests.** T33 `assert_proximity_excludes_pit_lane` and T38 `assert_dirty_air_share_monotone`, both
error severity and both passing on the fixed build. Both fail when their defect is put back: T33
returns 13,384 rows with the pit-lane filter removed, and T38 fails on all ten sub-1 s bins
(shares 0.53-0.96 against 1.0) with the DRS-first S2 coding restored. Full downstream `dbt build` on the
fixed copy: PASS=399, WARN=1, ERROR=0. The one warning is `assert_sector_aggregates_to_lap`, known
from WI-07; F48 brings it down from 11,892 to 10,533. `ml.src.features --check` against the fixed
copy with a full-compile manifest: forward-window, aggregation-scope and leakage all CLEAN, 32
features, and `encoders.json` unchanged.

**Why `data/dev.duckdb` was not rebuilt.** Rebuilding `int_lap_air_state`'s descendants re-estimates
θ_air in SQL and moves the label (numbers above). That is `WI-01`'s single label bump, so it should
happen once, there. Until then T33 and T38 error on dev, because the columns they read only exist
after a rebuild. `dbt run -s int_lap_proximity int_lap_air_state` alone would make them pass but
leave dev's air state out of step with its θ and its mart.

**Evidence preserved.** The fixed and unfixed warehouse copies used to verify acceptance are archived at
`_roadmap/_fixes/_evidence/wi-15a-2026-09-25/` with a comparison README. They are provided for
review; both are deterministic and can be rebuilt from the working-tree code.

**Orchestrator re-run (LANDED, 2026-09-25).** On a fresh scratch copy of `data/dev.duckdb`, built from
the working tree with `int_lap_proximity+ int_lap_air_state+ int_lap_thermal_proxy+`, so WI-15b is in the
build too. It was compared with `_evidence/.../dev_unfixed.duckdb` (HEAD) at a 1e-9 tolerance. Every
number above reproduces. WI-15b moves no label or eligibility, so the label movements are this item's.
- F43 against the audit's own oracle (HEAD's model plus the round-3 probe's pit-window filter, rebuilt
  here): 0 differing laps on every column except `time_within_1s` (877 laps, 876 of them a stop's in- or
  out-lap).
- Mutation checks: T33 returns 13,384 rows with the pit-lane filter removed, and T38 fails on all ten
  sub-1 s bins (0.53-0.96) with the DRS-first S2 coding restored. Both return 0 rows on the fixed build.
- Two things the section above leaves out. First, eligibility also moves the other way: 466 laps that
  were ineligible at HEAD become eligible, so the eligible count goes 137,759 → 137,877 (348 lost, 466
  gained). Second, `cliff_candidate_flag` moves on 216 eligible rows. Both come through θ_air, like the
  rest of the label movement. `int_pit_strategy_value` (reads `min_gap_s` only) and
  `int_lap_normalized_pace` do not move.
- `dbt build`: PASS=406, WARN=1 (`assert_sector_aggregates_to_lap`, 10,533), ERROR=1. The error is
  `assert_p_beats_next_geq_half` (5,730 rows). It comes from WI-14a's F46 rank-key change in
  `fct_ghost_race_finish`, not from this item: the pairwise probabilities still use
  `predicted_mean_lap_s`, and all 5,730 rows are adjacent pairs whose lap-time order disagrees with the
  new rank.

## As built: WI-15b (2026-09-25)

Measured on a scratch copy of `data/dev.duckdb`, `int_lap_thermal_proxy+` built from the working
tree, against `_evidence/wi-15a-2026-09-25/dev_unfixed.duckdb` as HEAD. Everything outside that
subtree is identical in the two, so the before/after below is this item alone. On
`fct_cliff_prediction_features` exactly four columns move, the thermal family. No label,
`is_training_eligible`, row count or thermal-NaN count moves (2,477 eligible rows either way).

**The first build (the MEASURED session) had two defects, both fixed here.**
- *F47 dropped laps.* It read `int_lap_fuel_state` as the lap source with an inner join, and that
  model carries valid laps only. The 28,378 invalid laps (SC, pit, lap 1, deleted, inaccurate) left
  `int_lap_thermal_proxy` (189,418 → 161,040 rows). The LAG window then treated the laps on either
  side of an SC period or a stop as adjacent, which the model's header says it must not do. That
  moved the bulk load on 7,890 training-eligible rows for reasons unrelated to fuel.
- *F49 left the class dead.* Dividing by weight sums does not make [0, 1] reachable. Surface ≤ bulk
  still holds lag by lag, so the normalised ratio is 1/(1 + (b/s)·(Ws/Wb)) ≤ Wb/(Ws+Wb) = 4.403/7.267
  = **0.606**. `surface_driven` (> 0.65) still had 0 of 41,437 rows. The build log's "full [0, 1]
  range reachable" was wrong, and `verify_findings.py`'s F49 check would have read CLEARED anyway: it
  cleared on `max > 0.5` alone.

**F47, as built.** `stg_laps` stays the lap source, and `int_lap_fuel_state` is LEFT-joined for
`weight_corrected_lap_time`, which is the baseline and residual input and replaces `lap_time_s` in the
output. No model read that column; the leakage test and the 08i script's replica now read the new
name. Invalid laps get a NULL corrected time and so a NULL residual. They keep their slot in the
window and contribute 0 (the existing rule for a NULL prior residual). Effect on eligible rows:
`push_residual` moves on 135,282 (mean +0.215 → −0.112 s), the surface load on 116,694, the bulk load on
123,182 (mean 1.728 → 1.099) and the ratio on 119,719. Laps past `lap_in_stint` 20 coded "pushing":
**67.6% → 32.5%**. `fct_stint_features.cumulative_thermal_load_end` moves on 7,060 of 9,374 stints, and
`stint_length_laps` on none.
*Where this differs from the audit's probe:* `round3/r3_push_residual_fuel.py` falls back to the raw
time on invalid laps (`COALESCE(corrected, raw)`), which moves the bulk load on 235 eligible rows
against this build. Scored against the corrected baseline, 126 invalid laps come out ahead of it. 71
of them are flagged inaccurate timing (12 of the 14 more than 5 s ahead) and 57 are deleted laps. That
is timing error, not push, and it is excluded from the push measure for the same reason it is
excluded from the baseline. The exact alternative, the per-(race, lap) fuel penalty applied to
invalid laps, is only available for 12,470 of the 28,378.

**F49, as built.** Kept the normalisation (a steady push reads 0.5, where it used to read 0.394), with
the weight sums moved to two dbt vars (`thermal_surface_weight_sum`, `thermal_bulk_weight_sum`) so
the fan model and the mart cannot drift apart. `surface_driven` was **removed** (Method step 4's
second option), because no threshold under the 0.606 ceiling is anything but invented. Declared range
is now [0, 0.606] (schema bound). Eligible rows: range [0, 0.5], mean 0.372 → [0, 0.606], mean 0.425,
median 0.505. The fan model: `bulk_driven` 11,664 → 8,882, `mixed` 29,773 → 32,555.
**For the ML contract:** the new ratio is a strictly monotone function of the old one, so XGBoost
splits on it are unchanged. What the contract actually gains from WI-15b is F47.

**Tyre Recovery page.** The interpretation note is computed from the rows (`pctRange`, unit-tested)
instead of typed in. The query gives a 57.7–63.8% recovery rate by compound, not 86–89%. The
methodology and `docs/app/tyre-recovery-forecast.mdx` are rewritten to what the SQL computes.
`recovery_flag` compares the next two laps' residual with this lap's; it never looked at a "cliff
slope". `recovery_probability` is a fixed formula, not a fitted model. The classes are now
bulk-driven or mixed.

**Checks.** `verify_findings.py` F47 CLEARED (share 0.325) and F49 CLEARED (0.606, 0 rows, class gone)
on the fixed build; the full board has no ERROR. F49's check was tightened: it now fails while a
declared class cannot fire. T37 `assert_push_residual_fuel_neutral` and T39
`assert_degradation_source_classes_reachable` pass. T37 fails on all 161,040 valid laps with raw time
restored and on the 28,378 dropped laps of the first build. T39 returns 3 rows at HEAD and 1 on the
first build. `dbt build -s int_lap_thermal_proxy+`: PASS=43, ERROR=0. `ml/tests` (features,
attribution, manifest contract) 95 passed against the fixed build. App: vitest, tsc and eslint clean.
The 08i replica reproduces the fixed build on all 161,040 rows.

**Not done here.**
- The thermal ablation (08e, Method step 2) and gate step 5 (`ml.src.features --check`) were not
  run. `WI-01` moves the label they score, so running them now means running them twice (same
  reasoning as W21).
- `data/dev.duckdb` still holds the first build's thermal subtree (the MEASURED session rebuilt it).
  Until it is rebuilt, T37 errors on dev.
- `app/public/data` still has pre-fix `int_tyre_surface_vs_bulk_decoupling` values (ratio 0.32–0.38 by
  compound).
