# WI-13 — Pit-strategy stop matching

**Group:** 07 causal pit timing · **Depends on:** nothing · **Blocker:** none.

**Findings folded in:** F31 (Medium); **added 2026-09-24:** F55 (Low) and two open NULL-guard sites from
WI-02a's T29 lint (see "Added scope" at the end).

**Reverification:** CONFIRMED-AS-STATED.

---

## The defect, reconfirmed

`int_pit_strategy_value.sql`'s `stint_meta` CTE filters `WHERE sg.is_valid_lap = TRUE`, and a stop is
matched only within `stint_start_lap` to `stint_end_lap + 1` (confirmed at the join clause). Any
SC/VSC/red-flag run-in, or an invalid lap immediately before the stop, puts the real in-lap outside
that window. Confirmed live: pit-ended stints with `actual_pit_lap` NULL — green 105/4,061 (2.6%), SC
191/644 (**29.7%**), VSC 38/230, red **96/115 (83.5%)**. Each gets `verdict = NULL` and
`opportunity_cost_s = 0.0` via an explicit `CASE WHEN r.actual_pit_lap IS NULL THEN 0.0`, as if the
stop never happened (at build time, after WI-05 re-cut the stints: green 79/4,064, SC 194/653, VSC
38/236, red 107/116 -- 418 stints). In the app, `pit-strategy/queries.ts:101,115-116` then does
`ORDER BY actual_pit_lap NULLS LAST` and `COALESCE(actual_pit_lap, tl.n)`, which draws those stints'
bars all the way to the chequered flag — a visibly wrong Gantt for a large majority of red-flag
stops.

## Fix assessment (from reverification)

Genuinely minimal: `int_stint_end_regime.end_lap_number` **already exists** as the correct join key
— this isn't a new-data requirement, it's a JOIN-clause swap.

## Method

1. Replace the `stint_end_lap + 1` match window with a match against
   `int_stint_end_regime.end_lap_number`, which already accounts for stints ending under SC/VSC/red
   conditions. **As built: a window ending at `end_lap_number`, not a match on it** -- equality leaves
   13 stints unmatched (see "As built" below).
2. Remove the app's `NULLS LAST`/`COALESCE(..., tl.n)` fallback once the underlying join reliably
   resolves `actual_pit_lap` for these stints — that fallback exists specifically to paper over the
   current gap and should go away with it, not be left as a second layer of masking.

## Acceptance

- No pit-ended stint (`stint_end_cause LIKE '%pit'` or `'red'`) has a NULL `actual_pit_lap`.
- The Gantt draws every stop at its real lap, including SC/VSC/red-flag run-ins.

## Tests to add

T23.

## Definition of done

`verify_findings.py`'s F31 check flips to CLEARED; T23 is wired in and would fail against the
pre-fix join.


---

## Added scope (2026-09-24) -- three small fixes folded in so one pass solves them

Unrelated to F31 apart from being small. Folded in at the user's direction; the item's model was raised
from `sonnet-5` to `opus-5` because A and B leave design choices open (where the fitter reads its rate,
what a NULL should default to).

### A. F55 -- `fit_weight_penalty.py` divides by a burn rate the model no longer reads

Full write-up: [`../reference/new-findings.md`](../reference/new-findings.md) (F55). The fitter divides
the fuel slope by `circuit_reference.fuel_consumption_rate_kg_per_lap` (Spain 1.9 kg/lap); the model now
burns `fuel_regulatory_max_kg / scheduled_laps` (Spain ~1.66).

**Do:** make the fitter take the burn rate the fuel model applies (the per-circuit mean of
`int_lap_fuel_state.fuel_consumption_rate_kg_per_lap`) instead of the seed constant. Then check who else
reads `fuel_consumption_rate_kg_per_lap` on `circuit_reference` / `dim_circuits` (the name appears in
`fit_compound_cliff.py`, several `schema.yml` files and tests): remove the column if nothing computes
from it, otherwise mark it legacy in the schema docs.

**Accept:** a fitter test asserting the rate passed to `calibrate_circuit` equals `int_lap_fuel_state`'s
mean rate for that circuit; it fails against the seed constant for Spain.

**Not in scope -- stays with WI-02b:** refitting Spain's `weight_penalty_factor` and deciding the fit
order against the compound refit. The compound seed is about to be refit (FD3), and the two fits feed
each other, so a Spain refit now would be redone. A scratch / dry-run fit for Spain with the corrected
rate is fine to report a number, but write nothing to `seeds/circuit_reference.csv` or `seeds/_pending/`.

### B. Two open NULL-guard sites (WI-02a's T29 lint)

DuckDB's `LEAST`/`GREATEST` skip a NULL argument, so an unknown value becomes the bound. Documented in
WI-02's "As built -- WI-02a" (T29 bullet); the reviewed sites are in
`transform/tests/least_greatest_nullable.allowlist.json` (10 marked `open`).

- `fct_cliff_prediction_features.survival_weight` is 4.0 instead of the COALESCE's 1.0 on the 4,088
  unknown-compound rows. None is training-eligible and the weight is off the training path.
  **Corrected by the build:** 24,800 rows, 18,878 training-eligible -- every 2018 row, not only the
  unknown-compound ones (see "As built").
- `int_constructor_deg_sensitivity.cliff_onset_shift_laps` is -3.0 (the harshest bound) instead of 0 on 1
  of 233 cells whose `ref_depth` is NULL. It feeds the ghost-car pages.

**Do:** guard both so a NULL stays NULL or takes its documented neutral value (read the models to confirm
what "neutral" is; if it is not clear, report rather than guess). Then walk the remaining `open` allowlist
entries: guard those whose fix is a one-liner and delete their entries; leave any that need a judgement
call with a written reason, and list them in the report.

**Accept:** both sites stop firing on dev (before/after counts); each fix is mutation-tested (revert ->
the check fails); the T29 lint stays green with no stale allowlist entry.

## As built (2026-09-25): F31, F55, and the T29 NULL-guard sites

State is in `../status/build-log.json`; this section only corrects or refines the spec where the
build did. Dev was rebuilt for `int_pit_strategy_value+` (F31; rebuilt again after a lint-only
refactor, output identical row for row) and for `int_constructor_deg_sensitivity+
fct_cliff_prediction_features+ fct_stint_features` (Part B: those three plus `fct_ghost_car_pace`
and `fct_ghost_race_finish`). No model was retrained, no seed was written, and `app/public/data` was
not re-exported.

**F31 -- stop matching**

- **A window, not equality.** The stop is the latest `stg_pits` pit-in between the stint's first lap
  (any validity, from `int_stint_geometry`) and `int_stint_end_regime.end_lap_number`. Equality with
  `end_lap_number`, as the Method read, leaves 13 stints unmatched (12 green-pit, 1 SC-pit) and F31's
  check PRESENT: on those, bronze puts the stint boundary one or two laps after the in-lap. Example:
  2018_2 VET's first stint, pit-in lap 17, `end_lap_number` 18 (the out-lap). On every stint that
  ended in a stop, the matched stop sits on `end_lap_number` or at most 2 laps before it. Two stints
  that did not end in a stop carry a pit-in well inside their span, and they did before this change
  too: 2018_15 MAG's third stint (stop on lap 48, stint runs to the flag at 59, with no stint break
  at the stop) and 2022_8 LEC's second (stop on lap 20, retired on lap 21). Both are graded `early`
  at 0.0.
- **Size at build time.** 418 pit-ended stints had no stop (green 79/4,064, SC 194/653, VSC 38/236,
  red 107/116). These differ from the reverification's counts above because WI-05 re-cut the stints
  in between. After the fix: 0 (T23, `assert_pit_ended_stints_have_stop`, which fails on 418 rows
  against the pre-fix table). 427 stints changed `actual_pit_lap`: those 418, plus 9 retirement
  stints whose pit-in (a retirement into the pit lane) the old window also missed. 182 of 328
  retirement stints now carry a pit-in, up from 173.
- **`end_lap_number` is a new output column** (documented, `not_null`-tested). The app's Gantt
  orders stints on it, ends a bar at `COALESCE(actual_pit_lap, end_lap_number)`, and starts the
  next bar one lap later. A stint with no stop now ends on its own last lap (the chequered flag, or a
  retirement on track), not on the race's last valid lap, which is where the removed
  `COALESCE(actual_pit_lap, tl.n)` had drawn those bars. The Gantt query no longer reads
  `fct_lap_residuals`.
- **Axis widening.** `queryRaceSummary`'s lap count is `MAX(lap_number)` over `fct_lap_residuals`,
  which holds valid laps only, so a race that finished under SC or red flag reads short. With bars
  ending on their real lap, 96 bars in 12 of 172 races (2018-2025; 89 in 11 of 148 for 2018-2024)
  end past it, by up to 6 laps. `transform()` widens the axis to the last bar and never shrinks it.
  The pit-strategy methodology text no longer says `fct_lap_residuals` supplies "lap windows".
- **ML untouched.** `ml/src` reads only `stint_length_laps`, `is_censored_stint` and
  `stint_end_cause` from `fct_stint_features`, and none of them comes from `int_pit_strategy_value`.
  The page will only show the fix once `int_pit_strategy_value` is re-exported to `app/public/data`.
  The shipped parquet has no `end_lap_number`, so the new query fails against it. The re-export is
  a user decision.

**Part A -- F55**

- `fit_weight_penalty.py` divides by `model_fuel_rates()`: the mean of
  `int_lap_fuel_state.fuel_consumption_rate_kg_per_lap` over the circuit's calibration laps, so that
  race's rate (FIA limit / scheduled laps) is weighted by that race's calibration laps, which is the
  burn the pooled slope reflects. It refuses to fit, rather than fall back to the seed, if a
  calibration lap has no rate. Nine fitter tests, four of which fail against the pre-fix fitter.
- **Changes nothing for Spain today.** A scratch `run_fit`-path fit with nothing written found 78
  calibration laps, all from 2024_10 (the loader's `race_to_track` join drops single-digit rounds;
  that is WI-02b's). Model rate 1.667 kg/lap. The measured factor hits the 0.005 floor at 1.667 and
  at 1.9 alike, so the flag is REVIEW_REQUIRED and the prior 0.02162 is kept. Refitting Spain stays
  with WI-02b.
- **Column kept, marked LEGACY.** No transform model or fitter computes from
  `circuit_reference` / `dim_circuits.fuel_consumption_rate_kg_per_lap`: `int_lap_fuel_state` and
  `fit_compound_cliff.py` use a model column of the same name. But the app's Degradation Simulator
  reads the `dim_circuits` copy (`degradation-simulator/queries.ts`, `inputs.ts`,
  `SimulatorControls.tsx`), so the column is documented as LEGACY in the seed and reference schema
  rather than removed. The simulator still burns the seed constant, which is out of scope here and
  recorded as a neighbouring issue.

**Part B -- the T29 sites**

- **`survival_weight` fired far wider than the spec said.** The spec named 4,088 unknown-compound
  rows. The build found 24,800 rows at 4.0 that should be 1.0, 18,878 of them training-eligible:
  all 17,367 known-compound 2018 rows (15,806 eligible; 2018 has no prior season to lag from), the
  4,088 unknown-compound rows (846 of them 2018; none eligible), and 3,345 later-season rows
  (3,072 eligible) whose (compound, `lap_in_stint`) no earlier season reached. That last group is
  mostly 2019 HARD/INTERMEDIATE/WET, whose 2018 curve is nearly empty, plus long-stint tails
  such as 2024 HARD laps 69-77. After the guard, all 24,800 rows are 1.0, and the 8,117 rows at
  4.0 are genuine clips (`survival_prob` <= 0.25). The mean is 1.976 -> 1.514 overall and
  1.953 -> 1.541 on eligible rows. `data_profile.baseline.json` records 1.801, a baseline already
  out of date that WI-07 owns.
- **Only `survival_weight` moved.** Against a snapshot taken before the rebuild, no other column of
  `fct_cliff_prediction_features` changed on any row (tolerance 1e-9; 0 sub-tolerance differences
  either), and 0 rows changed eligibility. The weight has been off the training path since 08o
  (`train.py::_sample_weight` returns None for the quantile heads). **However, the 08f-1 and 08o
  gates' IPW arms were built on code that put these rows at 4.0.** The season lag (08f-1) and the
  `GREATEST(0.25, LEAST(4.0, ...))` clip coexist in every commit since the lag landed, so every 2018
  training row carried the maximum weight in those arms, not the 1.0 the 08f-1 comment intended.
  08f-1's recorded AFTER weight vector (mean 1.970, max 4.0) is consistent with that. The arms were
  not re-run.
- **1.0 is the documented neutral, with one caveat.** The model documents 1.0 for "no prior curve"
  and for an unmatched (compound, lap) cell. For long-stint tails, though, the empirical survival
  is effectively 0, so a reading of IPW would give the 4.0 cap. The guard follows the documented
  rule. Which value is right only matters if IPW is ever brought back as a training weight.
- **`cliff_onset_shift_laps`:** 1 of 233 cells, 2018 Renault HARD (`is_low_sample_cliff`, no
  post-onset laps so `ref_depth` NULL), goes from -3.0 to 0.0, the documented field-timed value. No
  cell sits at +/-3 any more. Downstream, 310 `fct_ghost_car_pace` rows in one race change their
  shift columns but no prediction: 2018 HARD's onset is 37 laps and its oldest lap is 32, so the
  cliff term is 0 at either shift. `fct_ghost_race_finish` has no difference above 1e-9. Every other
  difference in the rebuilt tables is float reassociation under the 4-thread dev build, at most
  3.6e-12 (`fct_cliff_prediction_features` and `fct_stint_features`: none at all).
- **`tyre_management_score`** (clamp_or_null, guarded in the same pass) fires on 0 of 4,674
  stints with a positive cost. No value of `fct_stint_features` changed across the Part B rebuild.
- **Tests.** `assert_survival_weight_neutral_without_prior_curve` re-derives the "no prior cell"
  population from `int_lap_residual_decomposed`. It fails on exactly the 24,800 rows of the
  pre-guard snapshot. `assert_low_sample_cliff_cells_unshifted` fails on the one cell. Both pass as
  built. T29 lint: reverting each of the three guards in a scratch copy of the scanned tree fails
  `test_no_unreviewed_least_greatest_over_a_nullable_expression`, and restoring passes all 16 tests.
- **Allowlist walk.** 40 -> 34 entries: the three guarded sites' six calls are gone. Two entries
  were re-measured and re-verdicted. `int_constructor_deg_sensitivity`'s slope_se floor becomes
  `intended`: every read of `slope_se` is gated on `qualifies`, which requires `sxx > 0` and is
  never NULL, and 0 qualifying cells have a NULL pre-floor SE. The entry's claim that the final
  SELECT reads it for every cell was false. `fct_ghost_race_finish`'s sd_diff floor becomes
  `not_null`: 0 NULL inputs over 32,037 driver rows and 0 NULL or floored values over 586,522
  pairs. The two `int_pit_strategy_value` opportunity-cost clips stay `open` as a judgement call,
  0.0 vs NULL for a stint the model cannot grade. Neither fires (0 of 5,112 graded stints). Final:
  27 `not_null`, 5 `intended`, 2 `open`.
- **Lint.** The F31 edit added two sqlfluff violations to `int_pit_strategy_value.sql` (a long
  comment line, and a subquery where the project uses CTEs). Both are fixed, and the rebuilt output
  is identical row for row. `int_constructor_deg_sensitivity.sql` and
  `fct_cliff_prediction_features.sql` are over sqlfluff's 20 KB limit and are skipped by the gate,
  as they were at HEAD.
