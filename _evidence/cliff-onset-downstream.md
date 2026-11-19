# cliff_onset_shift_laps: consumers, format, and recommended method

Read-only review, 2026-11-18. No repo file edited, no build run. Published numbers come from
`app/public/data` (manifest generatedAt 2026-11-08). That export predates TX-18: SEs there are
0-filled, not NULL, and the `*_is_prior` columns are missing.

## 1. What the value is today

`int_constructor_deg_sensitivity.sql:568-581`:

```
shift = clip(-hinge_dev_shrunk * ref_depth / severity_used, -3, +3), COALESCE 0
se    = b_hinge_se * ref_depth / severity_used        (NULL when the cell is low-sample)
```

- `hinge_dev_shrunk` is the EB-shrunk deviation of the post-onset hinge slope. It is seconds of
  residual per lap past the field onset (a rate, s/lap^2 in lap-time terms).
- `ref_depth` is in laps (mean laps past onset, about 5 to 8). The product is **seconds**.
- `severity_used` is the median `compound_cliff_severity`. That is a **step height in seconds**
  (macros/compound_cliff_wear.sql, "THE UNITS"). Seconds divided by seconds has **no units**. It
  is not laps.
- The intended divisor, the ramp slope `plateau / 2.5` in s/lap, would give laps. The stored
  number therefore equals the "true" lap shift divided by 2.5.
- **The shape is also wrong, not only the units.** The derivation (comment at lines 115-136)
  assumes a linear post-onset ramp. Since 08m/CO-02 the field curve is a saturating ramp: it
  reaches the plateau 2.5 laps past onset and then stays flat. Moving the onset changes the
  penalty only inside that 2.5-lap window. At `ref_depth` (5 to 8 laps, past the plateau) an onset
  shift changes the penalty by **zero**, so the matching rule `severity * delta = dev * ref_depth`
  has no solution in the current curve. The hinge coefficient measures a persistent extra
  post-onset slope. That is a different effect from an earlier or later cliff, and the regression
  cannot tell the two apart (earlier cliff, bigger step and steeper post-cliff wear all load on
  it).
- Sign: positive means the cliff arrives later than the field (gentler), negative means earlier.
  The value is clipped to +/-3.
- Published range: -0.68 to +1.12 across 253 distinct host values, so the clip never binds. At
  2.5x it still would not bind (max 2.8).
- Zero has two meanings: (a) a low-sample cell is forced to 0 at the source (`is_low_sample_cliff`,
  which does not reach the ghost marts), and (b) a missing cell becomes 0 through COALESCE in the
  ghost mart (flagged by `*_deg_slope_is_prior`). In the published data, 15.6% of ghost lap rows
  have host shift = 0 **and** SE = 0. Those rows claim certainty about a value that was a fill.
- The SE is the raw hinge SE mapped through the same ratio. It is **not** the posterior sd of the
  shrunk value. `deg_slope_posterior_sd_s_per_lap` *is* a posterior sd and gives `tau` for
  low-sample cells. The cliff SE gives NULL there instead.

## 2. Consumers (complete: only two models; no ML, app or script reads it directly)

`int_constructor_deg_sensitivity` is referenced only by `fct_ghost_car_pace`. No file in
ml/src, app/src or scripts reads any `*cliff_shift*` column.

| # | Consumer (file:line) | Reads | Use | SE? | 0 / NULL |
|---|---|---|---|---|---|
| 1 | `marts/fct_ghost_car_pace.sql:174-175` (CTE `deg_sensitivity`), joined at host and ego cells `:349-358` | `cliff_onset_shift_laps`, `cliff_onset_shift_se_laps` | source | - | LEFT JOIN, so NULL when no cell |
| 1a | `fct_ghost_car_pace.sql:265-281` `cliff_interaction_s` | shift (host, ego) | **lap shift subtracted from stint age** inside `cliff_ramp_frac(GREATEST(age - onset - shift, 0))`, times the plateau (s). Clipped to +/-2 s. Then added to `predicted_lap_time_s`, `predicted_residual_pace_s` and `delta_vs_actual_lap_s` (`:374-408`) | no | COALESCE(shift, 0) = field-timed |
| 1b | `fct_ghost_car_pace.sql:304-319` `host_cliff_active`, `ego_cliff_active` | shift | **threshold**: 1 if `age - onset - shift > 0` | no | COALESCE 0 |
| 1c | `fct_ghost_car_pace.sql:243-244` `host_cliff_shift_laps`, `ego_cliff_shift_laps` | shift | explainability output column | no | COALESCE 0, flag via `*_deg_slope_is_prior` (`:219-223`) |
| 1d | `fct_ghost_car_pace.sql:295-296` `host_cliff_shift_se_laps`, `ego_cliff_shift_se_laps` | SE | passthrough for SE propagation | yes | NULL (since TX-18; published export has 0) |
| 2 | `marts/fct_ghost_race_finish.sql:85-86, 198-203, 230-234` | `host/ego_cliff_shift_se_laps`, `*_cliff_active`, `compound_cliff_severity` | **variance term**: `se_laps * mean_severity * frac_laps_past_onset`, as the host term (pairwise differential) and in `var_self` (ego) | yes | AVG skips NULL laps. If every lap is NULL, the term is NULL, then `sd_diff`, `p_beats_next` and `finish_pos_se` are NULL for the **whole scenario** (`:277-281, :318-321`) |
| tests | `tests/assert_cliff_hinge_centering.sql:19` rebuilds the hinge SE as `shift_se*severity/ref_depth`; `tests/assert_low_sample_cliff_cells_unshifted.sql`; schema range tests (+/-3, SE 0-50) in `intermediate/schema.yml:1524-1543`; `marts/schema.yml:1036-1090`; `tests/data_profile.baseline.json:2300-2367` | | | | |

Indirect app readers: `fct_ghost_race_finish` feeds `features/counterfactual-championship`
(`predicted_mean_lap_s`) and `features/hidden-performance` (`predicted_finish_position`,
`finish_pos_se`). The ghost-car routes `routes/ghost-car/lap-chart.tsx` and `standings.tsx` are
stubs that will read `fct_ghost_car_pace`.

### What each consumer actually needs

- **1a (lap recombination)** needs two things: *when* this car's cliff starts relative to the field
  (laps, applied to stint age), and *how much extra* it costs once there (seconds, or s/lap past
  onset). The current single number tries to be both and is neither.
- **1b (active flag)** exists only to scale SE. The right exposure is the derivative of 1a with
  respect to the parameter, not "is past onset". For an onset shift, the derivative is
  `plateau/2.5` while the lap is **inside the ramp window**, and 0 on the plateau. For a
  post-onset rate, the derivative is the capped depth past onset.
- **2 (SE)** needs a posterior sd for every cell (prior sd `tau` when thin), NULL only when there
  is no cell. With the current form, the two unit errors cancel in the size of the per-lap SE
  (`se_laps*severity = b_hinge_se*ref_depth`, in seconds). The exposure is still wrong: it counts
  plateau laps as active, and plateau laps are about 26.5% of published rows.

## 3. What ML and the app need (owner update)

**ML.** No model reads this column today. The natural target is the `cliff_classifier`
(`laps_until_cliff_class`: 0-2 / 3-5 / 6+ / none, mart `fct_cliff_prediction_features`). Its
features carry only the *field* cliff (`compound_cliff_onset_laps`, `laps_past_cliff`). The useful
added feature is "this car's onset relative to the field, in laps", with its sd. It should be in
laps so the model can combine it with `laps_past_cliff` directly; a rate cannot be added to a lap
count. A per-constructor fitted curve has too many dimensions for a tree model; it is better used
as two scalars. The current value **would mislead a model**, for four reasons:

- it is unit-less, at 1/2.5 of the true scale;
- it encodes post-onset slope, not timing;
- 0 means both "thin data" and "truly field-timed", with no flag, so a tree learns the 0 spike as a
  category;
- it is fitted on the same season's laps, including post-onset laps of the stints being predicted.
  That is **target leakage** for a cliff classifier. Any ML feature must be as-of, meaning fitted
  on prior races only (the same rule T48 applies to the isolation marts).

The sd should go in as its own feature, or the shift should be shrunk to the prior, so that
precision is visible to the model.

**App.** Two pictures this needs to support:

1. **Cliff timing per team**: dot plus interval per constructor for each compound and season,
   relative to the field onset at 0 laps. The band (posterior interval) is required, because thin
   cells shrink to 0 and must show a wide band, not a confident dot.
2. **Predicted lap-time curve per team with the cliff marked**: field curve (wear plus ramp plus
   plateau), the team's curve shifted by its onset, the onset marked as a vertical line with a band
   for its interval, and the extra post-onset cost shown as the gap after the plateau. This plugs
   into `tyre-cliff-survival` (already KM onset per compound) and the ghost-car lap chart.

## 4. Recommended methodology

Split the one overloaded number into **two estimands**, each fitted by the method that matches it.

**A. Cliff timing: `cliff_onset_shift_laps` (laps, true units).**
- Estimation: time-to-event model on stints. Event = the stint's cliff lap
  (`fct_stint_features.cliff_lap_in_stint`). Right-censored when the stint ends without a cliff
  (`is_censored_stint`, or a pit before the cliff).
- Model: log-normal AFT (the same family `ml/src/survival.py` already uses), with fixed effects for
  (season, compound, circuit) and a **constructor x compound x season random effect**, EB/DL-shrunk
  to 0 as today.
- Output: `onset_shift_laps = field_KM_onset * (exp(b) - 1)`, its posterior sd (delta method), and
  `time_ratio = exp(b)`, `n_events`, `n_censored`.
- This is directly a lap count. It handles stints that pit before the cliff, which the hinge
  regression cannot. It gives a per-team survival curve with a band, which is picture 1 and the
  onset in picture 2, for free.

**B. Post-onset extra cost: `cliff_post_slope_dev_s_per_lap2` (s per lap per lap past onset).**
- Keep what the hinge regression measures today (`hinge_dev_shrunk`), publish it **as a rate**, and
  drop the severity divisor entirely. That deletes the units defect rather than re-deriving a
  floor.
- Fit the hinge at the constructor-shifted onset from A, so A and B do not double-count.
- Ghost use: `(dev_h - dev_e) * LEAST(laps_past_cliff, H)` with H = 5 laps, the existing
  `compound_wear_hold_after_onset_laps`. That keeps the "bounded, outlier-robust" property the
  original note asked for without a clip.

**Recombination (1a):**
`plateau * [ramp(age - onset - A_h) - ramp(age - onset - A_e)] + (B_h - B_e) * LEAST(lpc, H)`.
ego == host still gives exactly 0.

**Uncertainty:**
- Publish the posterior sd for both A and B. For thin cells use the prior sd `tau` (the same
  convention as `deg_slope_posterior_sd_s_per_lap`). NULL only when there is no cell at all.
- In `fct_ghost_car_pace`, replace `*_cliff_active` with two exposures:
  - `in_ramp_s = (plateau/2.5) * 1[0 < age - onset - A < 2.5]`
  - `capped_depth = LEAST(lpc, H)`
- `fct_ghost_race_finish` then uses `sd_A * mean(in_ramp_s)` and `sd_B * mean(capped_depth)`, in
  the same structure as the deg-slope term.
- ML takes the point and sd as features (as-of only). The app draws the posterior interval as the
  band.

**Thin data:**
- A cell with too few events or stints: point = 0, sd = `tau`, `is_low_sample_cliff = TRUE`. This
  means "field-timed by prior, uncertain", not "known field-timed".
- No cell at all (constructor never ran the compound): point NULL, filled 0 in the ghost mart with
  `*_is_prior`, as TX-18 does now.
- **Drop the +/-3 clip.** It never binds today. Shrinkage is the regularizer, and a clip would hide
  a real extreme team rather than flag it. Keep a schema range test as an alarm only, at about +/-8.

**Tradeoffs, stated honestly:**
- A depends on the per-stint cliff event definition. `cliff_candidate_flag` was pruned as an ML
  *feature* in 08j as "dead", so its quality as an *event* label must be checked first (open
  decision 1).
- A AFT with circuit fixed effects plus random effects is a Python task (transform/tasks), not pure
  SQL.
- The minimal alternative fixes only the units: divide by `plateau/2.5`, which is `stored * 2.5`.
  It is a one-line change, but it keeps the shape error. The value would still be a slope dressed
  as a timing, and the ramp-window effect would still have no fitted basis. I do not recommend it
  except as a stopgap.

## 5. Published numbers that would move

Any version of the fix (including the minimal x2.5) moves the following.

**`fct_ghost_car_pace`** (published, app-exported):
- `host_cliff_shift_laps`, `ego_cliff_shift_laps`, `*_cliff_shift_se_laps`
- `cliff_interaction_s`: non-zero on 70,426 of 1,384,558 rows (5.1%), mean absolute value
  0.089 s, max 0.86 s
- `predicted_lap_time_s`, `predicted_residual_pace_s`, `delta_vs_actual_lap_s`
- `*_cliff_active`, which would be replaced

**`fct_ghost_race_finish`**:
- Moves: `predicted_mean_lap_s`, `predicted_mean_residual_pace_s`, `predicted_total_race_time_s`,
  `predicted_mean_lap_se_s`, `p_beats_next`, `finish_pos_se`.
- `predicted_finish_position` moves only where a rank flips. The scenario-mean cliff term is small
  today (mean |.| 0.004 s against 0.147 s for the deg term; max 0.13 s), so flips should be rare
  under x2.5. Under method B (rate times depth up to 5) flips could be larger and must be counted.

**App pages**:
- `hidden-performance` shows `predicted_finish_position` and `finish_pos_se`. `finish_pos_se` will
  move for every row, because the exposure changes.
- `counterfactual-championship` shows `predicted_mean_lap_s`.

**Tests and baselines**: `data_profile.baseline.json`, `assert_cliff_hinge_centering.sql` (its
SE reconstruction breaks), `assert_low_sample_cliff_cells_unshifted.sql` (semantics change:
SE = tau, not NULL), and the schema range tests.

`int_constructor_deg_sensitivity` itself is not exported to the app.

## 6. Open decisions for the owner

1. Is the per-stint cliff event (`cliff_lap_in_stint` from `cliff_candidate_flag`) good enough to be
   the event for A, or does A need its own event definition (for example the residual crossing the
   field plateau)?
2. Two estimands (A timing in laps, B post-onset rate), or the stopgap x2.5 now and A/B later?
3. For thin cells: SE = prior `tau` (recommended, consistent with deg slope), or keep NULL? Keeping
   NULL blanks `finish_pos_se` for whole scenarios on the current build.
4. Remove the +/-3 clip (recommended) or keep it as a guardrail?
5. For ML: admit an as-of (prior-races-only) version of A as a cliff_classifier candidate feature
   under the usual ablation gate? The in-season version must not be used: it leaks.
6. Cap H for the B exposure: 5 laps (the existing hold var), or `ref_depth`?
