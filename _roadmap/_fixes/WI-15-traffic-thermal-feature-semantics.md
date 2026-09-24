# WI-15 — Traffic and thermal feature semantics

**Group:** 02 feature expansion · **Depends on:** nothing structurally, but the θ part of F48 rides
`WI-01`'s label bump (re-estimate once, after F1 and this file's feature-coding fix both land).
**Blocker:** a contract ablation decision per `foundations/gates.md` — these are feature-*meaning*
changes, not label changes, so they go through the standard feature-contract process, not a version
bump.

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
