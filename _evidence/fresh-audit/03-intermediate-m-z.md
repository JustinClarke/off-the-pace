# Fresh audit 03: intermediate models int_m* to int_z*

Scope: 22 SQL models in `transform/models/intermediate/` whose name starts int_m to int_z (there are no .py models in this range; `int_lap_physical_ahead.py` starts with int_l and is outside it). Read-only review of the code and yml tests. Current Bronze taken as truth. 2018 Italian GP race (HD15 B) is a known gap, 2026 not audited.

Two small read-only checks were run on Bronze parquet (no warehouse touched): (1) X/Y unit check for `int_track_geometry`; (2) race-slug and SC-status duplicate checks for `int_pit_loss_circuit` / `int_sc_hazard_history`. Results are quoted where used.

Verdict tally: SOUND 12, QUESTIONABLE 8, WRONG 2.

All paths below are relative to `/Users/justin/github/off-the-pace/transform/models/intermediate/` unless stated. Singular tests live in `/Users/justin/github/off-the-pace/transform/tests/`.

---

## Flow (A -> B means B reads A)

Edges inside this group:

```
int_stint_geometry            -> int_stint_end_regime
int_stint_geometry            -> int_pit_strategy_cost_curve
int_stint_geometry            -> int_pit_strategy_value
int_stint_geometry            -> int_microsector_proximity     (lap_neutralised only)
int_stint_geometry            -> int_power_law_lap
int_stint_geometry            -> int_synthetic_teammate
int_stint_end_regime          -> int_pit_strategy_value
int_pit_loss_circuit          -> int_pit_strategy_cost_curve
int_pit_loss_circuit          -> int_pit_strategy_value
int_sc_hazard_history         -> int_pit_strategy_cost_curve
int_pit_strategy_cost_curve   -> int_pit_strategy_value
int_microsector_crossings     -> int_microsector_proximity
int_qualifying_segments       -> int_qualifying_push_laps
int_qualifying_decomposed     -> int_qualifying_driver_summary
int_power_law_lap             -> int_stint_power_law_fit
int_traffic_exposure_driver_race -> int_traffic_exposure_race
```

Consumers outside this group (from `ref()` search of the whole models tree):

```
int_stint_geometry            -> fct_stint_features, int_compound_cliff_predicted, int_constructor_structural_pace, int_corner_drift_from_early_stint, int_corner_skill_residuals, int_dirty_air_tax_component, int_driver_isolation_lap_panel, int_field_pace_curve, int_lap_air_state, int_lap_fuel_state, int_lap_physical_ahead, int_lap_proximity, int_lap_residual_decomposed, int_lap_thermal_proxy
int_stint_end_regime          -> fct_driver_isolation_stint, fct_stint_features
int_pit_strategy_value        -> fct_driver_isolation_stint, fct_stint_features
int_sc_hazard_history         -> fct_cliff_prediction_features
int_power_law_lap             -> fct_power_law_training, int_cell_power_law_fit
int_qualifying_push_laps      -> int_constructor_structural_pace_qualifying, int_lap_residual_decomposed_qualifying
int_qualifying_driver_summary -> fct_cliff_prediction_features
int_synthetic_teammate        -> fct_driver_skill_features
int_track_evolution           -> int_constructor_structural_pace, int_dirty_air_tax_component, int_driver_race_paired_laps, int_driver_race_skill_loro, int_lap_normalized_pace, int_lap_residual_decomposed, mart_corner_skill_driver
int_physical_ahead (int_lap_physical_ahead) -> int_traffic_exposure_driver_race
No model consumer (leaf tables, read by tests / Python / app only):
  int_microsector_proximity, int_microsector_corner_class, int_sector_residual_decomposed (app: sector-decomposition),
  int_stint_power_law_fit (ml/src/powerlaw_fit.py), int_track_geometry (comment-only mention in dim_corners),
  int_tyre_surface_vs_bulk_decoupling (app: tyre-recovery-forecast), int_traffic_exposure_race,
  int_qualifying_decomposed (app: quali-vs-race-skill, plus int_qualifying_driver_summary)
```

Upstream dependencies outside the group (ref/source):

```
stg_telemetry_position -> int_microsector_crossings, int_microsector_corner_class
stg_laps, stg_track_status, stg_pits, stg_results, dim_circuits -> int_pit_loss_circuit
stg_laps, stg_track_status -> int_sc_hazard_history
dim_corners, dim_compounds_season, circuit_reference, race_to_track, stg_weather -> int_pit_strategy_cost_curve / _value
int_compound_cliff_predicted, int_lap_air_state, stg_lap_tyre_qa, stg_pits -> int_pit_strategy_value
stg_laps, stg_lap_tyre_qa, stg_tyre_allocations, stg_race_control, stg_results, race_to_track -> int_stint_geometry
int_lap_residual_decomposed, compound_hardness_scale, dim_circuits -> int_power_law_lap
int_lap_residual_decomposed_qualifying, int_lap_residual_decomposed -> int_qualifying_decomposed
stg_laps_qualifying, stg_session_status_qualifying, stg_results_qualifying -> int_qualifying_segments / _push_laps
stg_sector_times, stg_laps, stg_lap_tyre_qa, int_lap_residual_decomposed, int_lap_air_state -> int_sector_residual_decomposed
int_lap_fuel_state, int_compound_cliff_predicted, stg_laps -> int_synthetic_teammate
int_field_pace_curve, stg_weather -> int_track_evolution
source('bronze_f1','raw_telemetry'), race_to_track -> int_track_geometry
int_lap_physical_ahead -> int_traffic_exposure_driver_race
int_lap_thermal_proxy, int_lap_residual_decomposed -> int_tyre_surface_vs_bulk_decoupling
macros: compound_cliff_wear_s, power_law_beta_grid, trailing_sum / trailing_observation_count
```

Notes that apply to several models:

- DuckDB `GREATEST`/`LEAST` skip NULL arguments (confirmed by running `select least(NULL,0.0)` = 0.0). Any `LEAST(x, 0)` or `GREATEST(x, 0)` therefore turns an unknown into 0. Called out where it bites.
- DuckDB `CONCAT` treats NULL as the empty string (confirmed: `concat('a','_',NULL,'b')` = `a_b`). This is why `int_stint_geometry.stint_id` is never NULL (see that section).
- Several identity tests (sector, qualifying 7-term) check identities that hold by construction (the residual is defined as the remainder). They guard against NULL/join slips, not against wrong maths.

---

## 1. int_microsector_corner_class  (SOUND)

1. Purpose: classify each of the 20 micro-sectors of a race lap as low / medium / high / flat / mixed / straight / link / unknown / no_geometry from corner apex speed and geometry.
2. Flow: reads `stg_laps`, `stg_telemetry_position`, `dim_corners`. Read by: no model (tests `assert_microsector_corner_class_covers_panel`, `assert_microsector_flat_high_disjoint`; Python/DA work).
3. How it works:
   - Green racing laps (lap >= 2, valid, status '1', not SC/VSC/red) joined to on-track position samples (l.68-109).
   - Lap length per race = median of `distance_m / relative_distance` over mid-lap samples 0.25 to 0.95 of every on-track lap (l.113-121). Median is robust, unit is metres.
   - Per corner: minimum speed within +/-50 m of the apex on each lap, then median over laps (l.162-189). The equality join uses 100 m buckets so each corner lists every bucket its window touches (l.137-160); `ABS(distance - apex) <= 50` (l.176) is the real filter, so no fan-out.
   - Apex class thresholds 120 / 200 / 280 km/h (l.225-231). Each apex is placed at -1, 0, +1 lap lengths so a corner near the line lands in exactly one micro-sector (l.236-251).
   - Micro-sector m spans [m, m+1) * L/20 (l.264-274). `inside` counts apexes per micro-sector; `near` counts apexes within 100 m before or 150 m after the micro-sector (l.300-322), which decides link vs straight.
4. Maths check: SOUND. Units are consistent (m, km/h). The three-copy wrap and the half-open interval give each apex exactly one micro-sector. Minimum within a window of noisy samples is slightly biased low, but it is applied the same way to every corner and the thresholds are pre-registered. `MIN(cp.apex_class)` (l.283) is only read when `apex_class_n = 1`, so the alphabetical MIN is harmless. A corner with no green-lap speed and no borrowed geometry gives class `unknown`, which a test forbids on panel races.
5. Fills:
   - l.79-81 `COALESCE(flag, FALSE)` on SC/VSC/red: a NULL flag counts as not neutralised; `track_status = '1'` already guards, so no number moves.
   - l.201 `COALESCE(a.apex_speed_kph, b.apex_speed_kph)`: borrows the apex speed from the nearest season's same corner when this race has no green lap (documented, flagged in `apex_speed_borrowed`).
   - l.285 `COALESCE(BOOL_OR(apex_speed_borrowed), FALSE)`; l.342 `COALESCE(race_corners_n, 0)` gives 'no_geometry'.
   - l.230 `ELSE 'high'` (200 to <280 km/h) and l.347 `ELSE 'straight'` are the intended default branches.
6. Tests: unique (year, race, microsector); `race_microsector_id` unique; `microsector` in 0..19; `lap_length_m` 3000..7500; `corner_class` accepted values; singular `assert_microsector_corner_class_covers_panel` (N rows per race, no unknown) and `assert_microsector_flat_high_disjoint` (checks the 280 km/h split). These check coverage and class consistency, not the apex speed itself.

---

## 2. int_microsector_crossings  (SOUND)

1. Purpose: the interpolated session-clock time at which each driver reaches each of the 20 fixed track positions on every lap.
2. Flow: reads `stg_telemetry_position` only. Read by `int_microsector_proximity` (and tests `assert_microsector_car_ahead_is_previous_crossing`, `assert_microsector_corner_class_covers_panel`).
3. How it works: unwrapped coordinate `u = lap_number + relative_distance`; consecutive samples per driver (ordered by session time) form pairs (l.43-60); a pair is kept only if exactly one boundary `floor(u*N)` lies between (l.63-73); crossing time is linear interpolation `t0 + (k/N - u0)/(u1-u0) * (t1-t0)` (l.83-85); `bracket_s = t1 - t0`; `on_track` needs both ends 'OnTrack'; DRS state is the earlier sample's. A boundary crossed twice keeps the first crossing (QUALIFY l.104-108).
4. Maths check: SOUND. Interpolation is on u (lap fraction), which is exactly what the boundary is defined on. `boundary_k // N` is the lap and `% N` the micro-sector, so micro-sector N-1 closes into the next lap's boundary 0 correctly (checked against the has_next logic downstream). A jump over two or more boundaries is dropped, never invented (documented). Not-NULL guard is implicit (`u1 > u0` false on NULL). No division by zero (`u1 > u0` filtered).
5. Fills: none. (l.37 rounding to 6 dp is for byte-stability only.)
6. Tests: unique (year, race, driver, boundary_k); `crossing_time_s` not null; `microsector` 0..19; `bracket_s` > 0; `drs_state` accepted values. The telescoping property is tested downstream by `assert_microsector_lap_total_identity` (sum of micro-sector times vs `lap_time_s`, with tolerance), which is a real maths check on this model.

---

## 3. int_microsector_proximity  (QUESTIONABLE)

1. Purpose: the micro-sector panel: time per micro-sector, field-relative time `y_s`, gap to the car ahead (entry), gap band, validity reasons, DRS state.
2. Flow: reads `int_microsector_crossings`, `stg_track_status`, `stg_pits`, `int_stint_geometry` (neutralised laps). Read by: no model; tests `assert_microsector_*` (5), Python.
3. How it works:
   - Crossings flagged `in_pit` (inside the driver's pit window, l.139-147), then ordered per (race, boundary) by (crossing_time, driver) over all laps and drivers (l.157-172). Car ahead = previous on-track crossing of that boundary by a different driver within `proximity_max_gap_s` (300 s) (l.188-211). Own previous crossing means alone, so NULL (not zero).
   - Micro-sector time = next boundary time minus this one (needs `next_boundary_k = boundary_k + 1`, l.299, 337).
   - Invalid reasons in fixed order (l.311-328): lap1, pit_lane, no_next_crossing, off_track, wide_bracket (>1 s), non_green_flag (status not '1' at either end or a non-green event inside), post_restart (race-wide: this lap or the 2 after any driver's SC/VSC/red lap).
   - `y_s = time_s - median(time_s)` over cars with the same (race, lap_number, microsector) when at least 8 timed cars (l.342-363).
   - Gap band step function and lapped-car rule (l.405-427).
4. Maths check: the clock, order and gap are right; two points are questionable.
   - QUESTIONABLE l.342-352 / 366-371: the field median is taken over cars with the same lap *number*. The header says whatever hits the field "at that moment" cancels, but cars sharing lap number n cross a given micro-sector up to a full lap-time apart (leader versus last car on the lead lap), and lapped cars sit on a lower lap number at the same wall-clock time. Track evolution, wind and temperature changes inside that spread do not cancel. The effect per micro-sector is small (about 4 s sectors) but it is not what the header claims.
   - QUESTIONABLE l.247 `LEAD(gap_ahead_s) AS exit_gap_ahead_s` is not gated on `has_next`, whereas `drs_state_exit` is (l.430). If the next recorded crossing is not boundary k+1, the "exit gap" belongs to a later boundary. The column is documented as a check-only outcome, so the exposure is limited.
   - Minor: `proximity_max_gap_s = 300` means almost any earlier car counts as "car ahead"; correctness of exposure relies on the gap bands (>3 s is the reference band), so this is consistent but worth knowing.
   - Sound parts: the car-ahead definition handles lapped cars via the lap-number test (l.364); pit crossings are dropped before ordering (l.167); `status_event_inside` checks non-green events in (start, end] (l.291-298); post-restart rule `laps_since_neutralised BETWEEN 1 AND 2 OR = 0` uses the race-wide neutralised lap set, a deliberately broad choice.
5. Fills:
   - l.127-130 `COALESCE(pit_out_time_s, pit_in_time_s + 120)`: an open stop gets a 120 s pit window (var `proximity_pit_window_open_s`); crossings in it are dropped, so over-long windows drop good rows, never add numbers.
   - l.264-266 `COALESCE(flag, FALSE)` (neutralised); l.313 `COALESCE(end_in_pit, FALSE)`; l.314 `COALESCE(has_next, FALSE)` -> 'no_next_crossing'; l.320-321 `COALESCE(status, '?') != '1'` -> a missing status drops the row as non_green (conservative).
   - l.425 `ELSE '5_gt3_reference'`: every valid gap of 3 s or more, including a lapped car beyond the 3 s window, goes to the reference band by design.
6. Tests: unique key and `microsector_id`; accepted values for reasons, bands, DRS; `lap_id` relationship to `stg_laps`. Singular: `assert_microsector_validity_rules` (valid rows are priced, band edges match the gap, lapped rule, `y_s` needs the minimum field, season Gate A of 90% valid), `assert_microsector_excludes_pit_lane`, `assert_microsector_car_ahead_is_previous_crossing` (independent re-derivation), `assert_microsector_lap_total_identity`, `assert_microsector_agrees_with_blue_flags`. These test maths (identity, re-derivation, blue-flag agreement), not only shape. None tests the lap-number field-median assumption.

---

## 4. int_pit_loss_circuit  (QUESTIONABLE)

1. Purpose: empirical pit-lane loss per circuit (seconds), shrunk toward the global median.
2. Flow: reads `stg_track_status`, `stg_results`, `dim_circuits`, `stg_laps`, `stg_pits`. Read by `int_pit_strategy_cost_curve`, `int_pit_strategy_value`.
3. How it works: per stop, `loss = (in_lap - ref) + (out_lap - ref)` where `ref` is the driver's median valid lap that race (l.43-52, 80-81). In-lap = `pit_in_lap_number`, out-lap = `pit_out_lap_number` (stg_pits guarantees in+1) (l.92-101). Stops with an SC / VSC / red-flag in-lap or out-lap are dropped (l.102-106); the loss must land in [8, 60] s (l.109-116). Median per venue (`circuit_id`), global median, then `(n * venue_median + 15 * global_median) / (n + 15)` (l.146-150).
4. Maths check:
   - SOUND: sums and signs; one observation per stop; venue pooling; join fan-out checked on Bronze: no `race_id` has two different slugs across track_status and results (191 races, 191 slug pairs), so the `UNION` slug map (l.31-36) does not double stops.
   - QUESTIONABLE l.43-52: the baseline `ref` is the whole-race median lap. It ignores the trend over the race (fuel burn, tyre age): an early stop is measured against a median that is faster than the laps around it (early laps are heavy), a late stop against one that is slower. Over many stops the median of loss mixes that bias, but it enters every loss number and is not corrected.
   - QUESTIONABLE l.113-115: the [8, 60] window truncates both tails before the median. It protects against red flags and slow stops, but it also hides any real cluster outside the window; median is robust so the effect is small.
   - QUESTIONABLE (labelling): the "EB shrink" (l.146-150) is a fixed pseudo-count blend of two medians, not an estimated variance ratio. Reasonable, but not Empirical Bayes in the strict sense.
   - Back-to-back stops: an in-lap that is also the previous stop's out-lap would be counted in two stops. Not guarded; probably rare.
5. Fills: l.79 `COALESCE(cm.circuit_id, m.race_slug)`: a circuit with no `dim_circuits` match uses its slug as its own venue (no pooling across event names, no number invented).
6. Tests: `circuit_slug` not null and unique; `circuit_id` relationship to `dim_circuits`; `pit_loss_s_empirical` and `pit_loss_s_shrunk` in [8, 60]; singular `assert_pit_loss_excludes_neutralised` rebuilds the stop population independently and compares counts (it re-uses the same slug map, so it would not catch a fan-out there; the Bronze check above did). Mostly population and range checks, not the loss formula itself.

---

## 5. int_pit_strategy_cost_curve  (QUESTIONABLE)

1. Purpose: `Total_Cost(L)` surface: for each stint and horizon scope ('window' = this stint through the next stint's last lap; 'race' = through the driver's last lap), the cost of pitting after L valid laps.
2. Flow: reads `int_stint_geometry`, `stg_weather`, `race_to_track`, `dim_compounds_season` (through macro `compound_cliff_wear_s`), `circuit_reference`, `int_pit_loss_circuit`, `int_sc_hazard_history`. Read by `int_pit_strategy_value` (and tests).
3. How it works: `cost(L) = sum old-set wear at ages (a0+1 .. a0+L) + sum new-set wear at ages 1 .. H-L + baseline_delta * (H-L) + pit_lane_loss * discount(L)` with `discount(L) = 1 - (1-m)(1 - (1-h)^L)`, m = 0.5, h = shrunk any-caution hazard per lap. L = H is the no-stop candidate (no pit term, l.389-399). Wear per age comes from the shared macro (linear wear with hold past onset, saturating cliff ramp, capped at 10 s/lap), cumulated by age (l.164-225). Total and wear columns are rounded to 6 dp so plateau ties resolve to the earliest lap (l.478-490).
4. Maths check:
   - SOUND: the separable structure; the monotone discount (`assert_pit_discount_monotone`); counting in valid laps consistently for horizon and L; the `candidate_lap_number` join (l.492-498); no-stop candidate has no pit cost.
   - QUESTIONABLE l.418 and l.100: age basis differs between the two sets. The old set starts at `MIN(age_in_stint) - 1` over valid laps. Since out-laps are invalid (stg_laps `is_valid_lap` excludes pit laps, and lap 1), the first valid lap of a fresh set is age 2, so a0 = 1 and the old set is charged wear(2), wear(3), ... The new set is charged from age 1 (`new_c.age_laps = laps_on_new_set`, assumption 2 "fitted new, age 1"). So the new set is priced one lap younger than the same set is priced when it is the old set. The new-set wear is understated by about `gradient * (H-L)`, which makes stopping earlier look cheaper than it is. Size is small (wear gradient is a few hundredths of a second per lap) but systematic.
   - QUESTIONABLE l.363-381: `0.005 * (clamp(T - opt_low_new, 0, 30) - clamp(T - opt_low_old, 0, 30))` carries three magic constants (0.005 s per degree, 30, 20) and uses stint-mean track temperature. It is consistent with `int_compound_cliff_predicted` (same 0.005 and clip), so the two curves agree, but there is no compound-to-compound base pace offset (soft vs hard), only wear and this temperature term. A move from a soft to a hard compound is priced with no pace difference between compounds. The header says this is deliberate (grip peak ratio dropped, W42); owner rules on whether it stays.
   - QUESTIONABLE l.355-356: a missing curve row is treated as zero wear (`COALESCE(old_0.cum_wear_s,0)` is correct for start age 0, but `COALESCE(new_c.cum_wear_s, 0.0)` also hides a next-stint compound with no fitted curve, giving a free new tyre). The no-stop case relies on the same zero, so the two cases cannot be told apart in the output.
   - QUESTIONABLE l.262: `COALESCE(sc.any_hazard_per_lap_shrunk, 0.0)` is commented as "2018 only", but it applies to any stint with no hazard row, not just 2018, and it silently removes the SC discount for that stint.
   - QUESTIONABLE (modelling): l.387-399 values the stop at lap L with the chance that a caution has appeared "within L laps" but still charges wear for all L laps on the old set. In reality a caution at lap j < L would move the stop to j. This is an expected-cost approximation and a design choice. It lumps VSC with SC in the hazard (`any_hazard`) and applies the single multiplier m to both.
   - INNER JOIN `old_c` at age `start_age + L` (l.401-406): candidates with age above `pit_strategy_max_age_laps` (160) drop out silently. Rare for normal stints.
5. Fills:
   - l.232-236 and l.257: pit loss `COALESCE(empirical, seed, 21.0)` and a second `COALESCE(cpl.pit_lane_loss_s, 21.0)`: scales the pit term for every candidate of a circuit with no measurement.
   - l.255 `COALESCE(next_compound, compound)`: in 'race' scope (no known next stint) the next set is the same compound as the current one.
   - l.262 hazard 0.0 (see above).
   - l.355 `COALESCE(old_0.cum_wear_s, 0.0)` (correct when start age = 0), l.356 `COALESCE(new_c.cum_wear_s, 0.0)` (see above).
   - l.367-368, 375-376: `COALESCE(track_temp_c, 30.0)`, `COALESCE(opt_temp_low, 20.0)`: missing temperature or optimum feeds a 10 C delta into the baseline term (small: 0.005 s per C).
   - l.390 `WHEN laps_on_new_set = 0 THEN 0.0` (no-stop has no pit term, intended).
   - Macro `compound_cliff_wear_s`: `COALESCE(wear_gradient, 0.0)` and plateau `COALESCE(severity, 0.0)`: a compound with no fitted gradient has zero wear (free tyre); the macro also returns NULL on unknown age/laps_past_cliff (NULL-safe).
6. Tests: unique (stint, scope, offset); not-null on key columns; `sc_probability` and `pit_discount_factor` in [0, 1]; singular `assert_pit_discount_monotone` (real maths: waiting never raises the stop's cost), `assert_pit_loss_pushes_optimum_later` (re-minimises at +15 s pit loss; tests the separability property, not that the cost numbers are right), `assert_compound_wear_bounded`, `assert_compound_pace_units`. None checks the age-basis consistency noted above.

---

## 6. int_pit_strategy_value  (QUESTIONABLE)

1. Purpose: per stint, the optimal pit lap (argmin of the cost curve), the actual pit lap, the opportunity cost in seconds and a verdict (optimal / overran / undercut_forced / early / unknown).
2. Flow: reads `int_stint_geometry`, `int_compound_cliff_predicted`, `race_to_track`, `circuit_reference`, `int_pit_loss_circuit`, `stg_pits`, `int_lap_air_state`, `int_pit_strategy_cost_curve`, `stg_lap_tyre_qa`, `int_stint_end_regime`. Read by `fct_stint_features`, `fct_driver_isolation_stint`.
3. How it works: rank the curve per (stint, scope) by `(total_cost_s, offset)` and keep rank 1 (l.185-219). Actual cost = curve row where offset = the stint's valid-lap count (l.238-246). The verdict uses the 'window' scope, falling back to the 'race' scope (l.416-430). The actual stop lap is the latest pit-in inside the stint span from the last tyre fragment's first lap to the end lap (l.317-372). Verdict compares offsets with a +/-1 lap band; an early stop that lands in `[first_threat - 2, first_threat + 3]` is `undercut_forced` (l.497-524). `optimal_pit_lap = candidate_lap_number + 1` (l.215). Confidence = share of candidate laps more than 1 s worse than the minimum (l.224-232).
4. Maths check:
   - SOUND: the argmin and tie rule; offsets (not lap numbers) used for the comparison, so invalid laps do not shift the verdict; one actual stop per stint via MAX (l.359-372); `optimal_pit_lap = last valid lap + 1` is consistent with stg_pits recording the lap on which the car entered the pit lane, because the pit in-lap is not a valid lap.
   - QUESTIONABLE l.471 and l.492-495: `GREATEST(actual_cost - optimal_cost, 0.0)`. "Non-negative by construction" is true when the actual offset is on the curve. If the actual offset is missing, the difference is NULL and DuckDB's GREATEST returns 0.0, so a missing value becomes "no opportunity cost". Same shape on l.469-470: stints with actual stop but no optimum (verdict 'unknown') report cost 0.0, not NULL.
   - QUESTIONABLE l.502-524: if `actual_offset` is NULL, `ABS(...) <= band` and `>` evaluate to NULL, so the CASE falls through to `ELSE 'early'` (or `undercut_forced`) instead of 'unknown'. A stint whose actual offset is not on the curve gets labelled as an early stop. Rare, but it is a silent wrong label.
   - QUESTIONABLE l.423-428: `COALESCE(window actual cost, race actual cost)` is paired with `COALESCE(window optimum, race optimum)`. If a window optimum exists but its actual cost does not, the actual cost comes from the race scope and is compared with a window optimum: two horizons mixed in one difference. Unlikely, not guarded.
   - QUESTIONABLE (design, owner rules): `first_undercut_threat_lap` (l.161-164, 516-522) uses gap to the car AHEAD from `int_lap_air_state` (FastF1 DriverAhead telemetry, not the X/Y physical-ahead measure) below `pit_loss + 1 s`. Header admits 95.5% of stints have such a lap, so the threshold fires early in nearly every stint; the `-2` margin at l.519 is a magic constant. The verdict name suggests a threat from a car behind; the code measures the gap ahead.
5. Fills:
   - l.117-121, 126: pit loss COALESCE(empirical, seed, 21.0), source 'default'; l.479 `COALESCE(pit_lane_loss_s, 21.0)`, l.480 'default', l.481 TRUE (imputed flag): output labels follow the fill.
   - l.131 `COALESCE(CAST(pit_loss_imputed_flag AS BOOLEAN), TRUE)`.
   - l.156 `COALESCE(la.min_gap_s, 999.0)`: only feeds `min_gap_in_window_s`, which is not in the final select (no effect); l.162 `COALESCE(cpl.pit_lane_loss_s, 21.0)`.
   - l.331-336 `COALESCE(MIN(lap) FILTER(last fragment), MIN(lap))`: fall back to the whole run when the last-fragment filter is empty.
   - l.469-470, 490-491 `THEN 0.0`: described above; l.475 `COALESCE(confidence, 0.0)`; l.523 `ELSE 'early'`.
6. Tests: `stint_id` not null, unique; `opportunity_cost_s` and `opportunity_cost_race_s` in [0, 6000]; verdict, horizon_source, pit_loss_source accepted values; `pit_lane_loss_s` in [8, 60]; confidence in [0, 1]; singular `assert_pit_ended_stints_have_stop` (checks every pit-ended stint has an actual stop) and `assert_pit_not_taken_from_joined_boundary`. These check population and range, not the cost maths; the range test on the cost (>= 0) is satisfied by the GREATEST clip.

---

## 7. int_power_law_lap  (SOUND)

1. Purpose: the one set of laps every power-law degradation fit and its grading read (slick laps, tyre age 1 to 50).
2. Flow: reads `int_lap_residual_decomposed`, `int_stint_geometry`, `race_to_track`, `dim_circuits`, seed `compound_hardness_scale`. Read by `int_stint_power_law_fit`, `int_cell_power_law_fit`, `fct_power_law_training`.
3. How it works: filter to weight-corrected lap time present, slick, age 1-50, `correction_weight = 1`, no SC/VSC/red, not a major outlier (l.62-72). Target `y_s = weight_corrected_lap_time` (fuel-corrected only). Hardness identity = lap's own compound name for 2018, `compound_code` (C1-C5) for 2019+; rank from the seed by (identity, era) (l.97-110, 137-140).
4. Maths check: SOUND. A filter-and-label model; no arithmetic beyond selection. The target choice (fuel-corrected, no seed-priced terms) is argued in the header and enforced by `assert_power_law_no_seed_columns`. 2025 has a NULL rank by construction (known, kept in the lap set). The set mixes laps in traffic (no air-state filter), which the pooled fit later absorbs; not a maths error. The `geom` join is by `lap_id` (unique), no fan-out; `track` join by `race_id` through `race_to_track` (unique by test on that model).
5. Fills: l.67 `COALESCE(correction_weight, 0) = 1`: a lap with no weight is excluded.
6. Tests: `lap_id` unique, not null; age 1-50; compound label accepted values; era accepted values; `y_s` not null; singular `assert_power_law_no_seed_columns` (column list), `assert_hardness_rank_2018_from_lap_name`, `assert_power_law_fit_bounds`. Shape and lineage, no maths needed.

---

## 8. int_stint_power_law_fit  (SOUND)

1. Purpose: per stint, fit `y = intercept + alpha * age^beta` by profiling beta over a grid (descriptive, not a training target).
2. Flow: reads `int_power_law_lap` and the `power_law_beta_grid` macro. Read by no model (Python `ml/src/powerlaw_fit.py`; tests).
3. How it works: stints need >= 2 distinct ages and a non-zero variance (l.59-62). For each of 57 betas (0.20 to 3.00 step 0.05) `REGR_SLOPE/REGR_INTERCEPT/REGR_R2(y, age^beta)` (l.66-79); keep highest R^2, smallest beta on a tie (l.81-89); `r2_linear` taken at beta = 1 (beta_k = 20); edge flag for beta_k in (4, 60); `fit_eligible` = >= 8 laps and age span >= 7 (l.99-124).
4. Maths check: SOUND. Argument order for the REGR functions is (dependent, independent) as required. Beta grid is exact integers divided by 20, so beta_k 20 is exactly 1. Picking the best of 57 betas by R^2 inflates R^2 and pushes beta to the grid edge; the header says so and calls it "a description, not a target" (reported, never gated). The alpha sign is not constrained (a negative alpha would mean pace improving with age, which can win on noise); the header accepts this.
5. Fills: none.
6. Tests: `stint_id` not null, unique; `beta`, `r2`, `fit_eligible` not null; singular `assert_power_law_fit_bounds` (beta in the grid, R^2 not below the linear fit, T50) and `assert_power_law_no_seed_columns`. `assert_power_law_fit_bounds` checks the profiled fit never does worse than a line, which is a real property of the maths.

---

## 9. int_qualifying_segments  (SOUND)

1. Purpose: recover Q1/Q2/Q3 time windows for each qualifying session from the session status timeline and each driver's official segment bests.
2. Flow: reads `stg_session_status_qualifying`, `stg_results_qualifying`, `stg_laps_qualifying`. Read by `int_qualifying_push_laps`.
3. How it works: matches each official best time to the lap that set it (tolerance 0.0005 s), chained so Q2's anchor must come after Q1's, Q3's after Q2's (l.112-175); per segment takes first/last anchor lap time; segment start = first green after the last chequered flag inside the bracket, else the last green in the bracket, else the first anchor lap (l.234-302); each window runs to the next segment's start, Q1 open at the bottom, Q3 open at the top (l.369-372).
4. Maths check: SOUND. The anchor chain handles identical times in two segments. Bracketing uses the previous segment's first anchor as the lower search bound and this segment's first anchor as the upper bound (documented against 2021 Spa and 2022 Montreal cases). Windows are contiguous by construction (start = prior end), so no lap can fall into two windows (no fan-out in `int_qualifying_push_laps`). The 0.0005 s tolerance is on the same source precision.
5. Fills: l.149 and l.173 `COALESCE(a.anchor_s, -1.0)` (no previous anchor means no lower bound); l.246 and l.268 `COALESCE(prev anchor, -1.0)`; l.289-294 `COALESCE(green..., first_anchor_s)`: if no green resolves, the segment opens at its first anchor lap (the latest it can have opened); l.321-324 terminal event `COALESCE(finished, aborted, finalised)`.
6. Tests: `quali_segment_id` not null, unique; relationships to `race_to_track`; segment accepted values; singular `assert_quali_segment_matches_official` (each official time was set inside the segment assigned to it; a real check on the recovery).

---

## 10. int_qualifying_push_laps  (SOUND)

1. Purpose: lap-grain push-lap gate for qualifying: 107% of the segment best, or the driver's own segment best.
2. Flow: reads `stg_laps_qualifying`, `int_qualifying_segments`. Read by `int_lap_residual_decomposed_qualifying`, `int_constructor_structural_pace_qualifying`.
3. How it works: assign each lap to a segment by `lap_start_time_s` window (l.57-75); segment best = min valid lap time; driver segment best likewise; `ratio_to_segment_best = lap_time / NULLIF(segment_best, 0)` (l.119); `is_push_lap = valid AND (lap <= 1.07 * segment_best OR lap = driver_segment_best)` (l.123-132).
4. Maths check: SOUND. 107% is applied per segment (correct reference). Windows are contiguous so the LEFT JOIN yields one row per lap. Only the fallback `'Q'` (l.60) for a session with no segments uses a whole-session reference (documented). The equality `lap_time = driver_segment_best` compares values from the same column, so no float mismatch.
5. Fills: l.60 `COALESCE(s.quali_segment, 'Q')`; l.123-132 `COALESCE(valid AND ..., FALSE)`: a lap with unknown validity is not a push lap.
6. Tests: `lap_id` not null, unique; relationships; `quali_segment` and `is_push_lap` not null; singular `assert_quali_segment_matches_official` covers the segment assignment. No direct test of the 107% maths.

---

## 11. int_qualifying_decomposed  (WRONG)

1. Purpose: public qualifying lap decomposition plus the quali-versus-race skill differential.
2. Flow: reads `int_lap_residual_decomposed_qualifying`, `int_lap_residual_decomposed`. Read by `int_qualifying_driver_summary` and the app page `quali-vs-race-skill` (reads this table's parquet).
3. How it works: carries the qualifying decomposition columns; per driver and segment takes the residual of the driver's best lap (l.68-80); averages across segments contested (l.82-91); race side is the average of `driver_skill_residual_s` over the driver's race laps with `correction_weight = 1` and no rain (l.96-108); `quali_vs_race_skill_delta_s = quali_avg - COALESCE(race_avg, 0.0)` (l.145-147).
4. Maths check:
   - WRONG l.145-147 versus header l.6-8 and schema.yml (line 2359-2362: "Positive = qualifying specialist"): both residuals are "positive = slower" (`int_lap_residual_decomposed.sql` l.7 and the qualifying model l.12). `quali - race` is therefore positive when the driver is slower in qualifying than in the race, which is a RACE specialist. The documented meaning is inverted. The arithmetic is fine; the sign claim is wrong, and the app's methodology text repeats the wrong claim ("positive means relatively faster in qualifying", `app/src/features/quali-vs-race-skill/methodology.tsx` l.16-17). An earlier audit script (`_roadmap/.../r2_quali_vs_race_sign.py`) noted a related sign problem on the page.
   - QUESTIONABLE (same line): the quali residual and the race residual come from two different decompositions with different baselines (segment field pace vs race field pace curve); their difference is a difference of two residuals that are each relative to a different reference. Reasonable as a heuristic, not a like-for-like skill difference.
   - Segment-skill extraction (l.68-80) is sound: one observation per segment, equality `lap_time = driver_segment_best` is on the same column.
5. Fills: l.104 `COALESCE(rainfall_flag, FALSE) = FALSE` (NULL rain counted as dry); l.146 `COALESCE(race_skill_race_avg_s, 0.0)`: a driver with no race residual (no weight-1 dry laps) gets a delta equal to their qualifying residual, and the app computes `race_skill_s = quali_skill_s - delta_s`, so it shows a race skill of exactly 0.0 for that case; l.154 `NULL::BOOLEAN AS quali_traffic_flag` (never populated); l.156 `FALSE AS dnq_flag` (constant). The app query filters `dnq_flag IS NOT TRUE AND quali_traffic_flag IS NOT TRUE`; both filters are no-ops.
6. Tests: `lap_id` not null, unique; `quali_skill_residual_s` and `quali_segment` not null; singular `assert_qualifying_7term_identity` (the residual is defined as the remainder, so this identity holds by construction and does not test the maths of the components). No test on the sign or the delta.

---

## 12. int_qualifying_driver_summary  (SOUND)

1. Purpose: one row per driver-weekend qualifying summary for the ML feature contract.
2. Flow: reads `int_qualifying_decomposed`. Read by `fct_cliff_prediction_features`.
3. How it works: count of push laps; mean constructor component; mean of the constructor SE; MIN of `quali_pace_delta_s` and `ratio_to_segment_best` (best lap, since both are higher = slower); MAX of the session-constant skill and contested-segment count (a no-op collapse of constants) (l.97-109). The race-skill delta is deliberately not carried (forward reach).
4. Maths check: SOUND. MIN is the right pick for "higher = slower" quantities. MAX of a constant is value-preserving. Averaging `constructor_component_se_s` over laps (l.103) is an average of standard errors, not a pooled SE, and the name says "se_mean"; laps within a weekend share most of the fit, so it is a reasonable label. Averages are lap-count weighted (a driver with more push laps weights their own laps more, which only affects a within-driver average).
5. Fills: none in this file (the mart COALESCEs `quali_push_laps_n` to 0 for drivers without a row).
6. Tests: unique (year, race, driver); not nulls; relationships to `race_to_track` and `dim_drivers`. Shape only.

---

## 13. int_sc_hazard_history  (SOUND)

1. Purpose: point-in-time safety-car / VSC hazard per racing lap, per circuit and season (rates from earlier seasons only), with an EB-shrunk version.
2. Flow: reads `stg_track_status`, `stg_laps`; macros `trailing_sum`, `trailing_observation_count`. Read by `int_pit_strategy_cost_curve`, `fct_cliff_prediction_features`.
3. How it works: onsets = rows with status code '4' (SC) and '6' (VSC) per race (l.51-59); exposure = max lap number per race (l.64-71); per circuit-season totals; trailing sums over seasons strictly before S (RANGE frame ending 1 PRECEDING); global pooled rate lagged the same way (l.124-146); `shrunk = (prior_onsets + global_rate * 600) / (prior_laps + 600)` (l.216-239).
4. Maths check: SOUND. Rate = sum of onsets over sum of laps (not an average of per-race rates), correct for unequal race lengths; the shrinkage is a standard Gamma-Poisson style blend with a 600-lap prior; the macro frame ends at 1 PRECEDING, so no row sees its own season. Checked on Bronze: SC-status rows are never repeated back to back (149 SC rows, 0 repeats), so onset counts are not inflated by duplicate status rows. Season 2018 is NULL by construction (no prior). Monza 2019 has no 2018 prior because the 2018 Italian GP is the known gap; that only thins the prior, it does not bias it. The "any" hazard adds SC and VSC onsets and treats them as one event type per lap (downstream choice).
5. Fills: l.78-79 `COALESCE(onsets, 0)` (a race with a status timeline but no SC rows counts as zero onsets, correct); l.192-196 `COALESCE(prior_*, 0)` for the companion counts; l.201-205, 217-237 `COALESCE(prior_onsets, 0)` inside the rate and shrunk numerators: a debut season has zero prior exposure so the shrunk rate equals the global prior (documented). The raw rate stays NULL there (NULLIF).
6. Tests: unique (circuit, season); counts not null; rates in [0, 1]; singular `assert_sc_hazard_probability_bounds` and `assert_sc_hazard_no_forward_leakage` (real property check that no row sees its own or later seasons).

---

## 14. int_sector_residual_decomposed  (QUESTIONABLE)

1. Purpose: lap physics components spread over the three sectors by time share, with a sector-level skill residual against a field sector median.
2. Flow: reads `stg_sector_times`, `stg_laps`, `stg_lap_tyre_qa`, `int_lap_residual_decomposed`, `int_lap_air_state`. Read by no model (app `sector-decomposition`).
3. How it works: sector times for valid laps with tyre QA 'ok' (l.36-55); field sector baseline = median of all drivers' sector times in a +/-3 lap window (self-join, l.75-105); each lap component (fuel, compound, constructor, dirty-air tax) times `sector_time / lap_time` (l.151-169); residual = `sector_time - field_sector_median - sum(allocated components)` (l.171-183); dominant component class by largest absolute value; consistency index = standard deviation of the sector residual over the driver-race-sector (l.245-247).
4. Maths check:
   - SOUND: shares `sector_time / NULLIF(lap_time, 0)` allocate each component, closed by `assert_sector_aggregates_to_lap`; NULL-guarded dominant class (l.210-216).
   - QUESTIONABLE l.155 vs l.171-183: the lap-grain components are defined against the lap model's baseline (field pace curve, trimmed mean, with its own smoothing and eligibility), but the sector baseline is a +/-3 lap median of raw sector times from every valid lap in the field (all compounds, fuel loads, traffic states). The residual absorbs the difference. The test header reports the residual sum differing from the lap residual by up to 64.7 s on one build ("real and expected"). So `sector_driver_skill_residual_s` is not the sector part of the lap skill residual; it is a different quantity, and the sector residuals do not sum to the lap residual. The file header acknowledges this (l.142-150).
   - QUESTIONABLE l.154 and l.134: shares divide by `stg_laps.lap_time_s`, not by the sum of the three sector times. If the sector times do not sum to the lap time (rounding, timing-line mismatch), the allocated components do not sum to the lap component. Tolerated by the existing test but not exact.
   - Minor: `field_sector_sample_n` is inflated (each window sample is repeated once per row of `a` in the group); it is not selected, so no effect. The sector consistency index is a standard deviation over residuals that include the baseline-mismatch noise.
5. Fills: none (comment l.67 says deliberately no COALESCE so a NULL tax gives a NULL sector value). `ELSE 'dirty_air'` (l.241) is only reachable after the NULL guard.
6. Tests: `sector_id` not null, unique; sector in (1,2,3); `sector_pace_delta_s` not null; singular `assert_sector_aggregates_to_lap` (does check component conservation, a real maths test) and `assert_sector_residual_identity` (holds by construction, tautological).

---

## 15. int_stint_end_regime  (SOUND)

1. Purpose: why each stint (tyre run) ended: green_pit, sc_pit, vsc_pit, red, race_end, retirement; plus the censoring flag used by stint-life models.
2. Flow: reads `int_stint_geometry`, `stg_results`. Read by `int_pit_strategy_value`, `fct_stint_features`, `fct_driver_isolation_stint`.
3. How it works: stint grain from `int_stint_geometry` (l.82-94); `is_censored_stint` = this is the driver's highest stint number (NULL numbers sort as -1) (l.117-119); end lap = last lap of the stint by `lap_in_stint` (l.126-140); end regime red > SC > VSC > green; `was_running_at_flag` from final status ('Finished', '+N Lap', disqualified at or near the final lap) (l.193-200); cause by precedence (l.232-240); confidence labels.
4. Maths check: SOUND. Precedence is explicit, censoring outranks regime, and the `LIKE '%Lap%'` test is the documented completion-status set. `is_stint_life_censored = COALESCE(cause <> 'green_pit', TRUE)` is total (no NULL). `PARTITION BY race_id, driver_id` without year is safe because `race_id` carries the year.
5. Fills: l.117-118 `COALESCE(stint_number, -1)` (unassigned laps sort first); l.170 `ELSE 'green'`; l.194-197 `COALESCE(status, '')` (missing result counts as not running unless disqualified); l.239 `ELSE 'green_pit'`; l.272 `COALESCE(..., TRUE)` (unassigned stints are censored).
6. Tests: `stint_id` not null, unique; accepted values for regime, cause, confidence; boolean columns not null; relationships; singular `assert_stint_end_cause_partition`, `assert_vsc_stop_censored`, `assert_pit_ended_stints_have_stop`, `assert_pit_not_taken_from_joined_boundary`. The partition test checks the label logic, so this is more than shape.

---

## 16. int_stint_geometry  (SOUND)

1. Purpose: foundation lap table: stint (tyre run) identity, ordinals, tyre age, compound, C-code, validity flags.
2. Flow: reads `stg_laps`, `stg_lap_tyre_qa`, `stg_tyre_allocations`, `race_to_track`, `stg_race_control`, `stg_results`. Read by the many models listed in the flow section (plus `fct_stint_features`).
3. How it works: joins fragments of FastF1 stints into runs when the compound is the same, tyre age continues by +1 and the previous fragment did not end under green (or a penalty was served within a lap) (l.120-210); `stint_id` is rebuilt from the run's first fragment (l.212-220); `lap_in_stint` is the chronological ordinal, `valid_lap_in_stint` counts valid laps only (l.222-246); `age_in_stint = tyre_life` (the set's own age, can exceed `lap_in_stint` on a used set); `compound_code` from the allocation table by lower-cased label (l.255-267).
4. Maths check: SOUND for what it does. Points noted, none wrong:
   - `age_in_stint` is the tyre's real age; consumers that count valid laps (cost curve) must keep the two bases apart (see int_pit_strategy_cost_curve).
   - `CONCAT` folds a NULL `stint_number` to an empty string, so laps FastF1 never assigned to a stint share one `stint_id` of the form `year_race_driver_`, per driver-race. `int_stint_end_regime` documents and handles this (cause NULL, censored). The `not_null` test on `stint_id` cannot catch it. The header says these laps "stay NULL", which is true of `stint_number` but not of `stint_id`.
   - `joins_previous` COALESCEs unknown to FALSE (conservative: no join).
   - `compound_code` join `LOWER(compound) = compound_label` per (year, circuit, label): a duplicate allocation row would fan out; the `lap_id` unique test would catch it.
5. Fills: l.156-172 `COALESCE(join-rule, FALSE)`; l.289 `CAST(NULL AS BOOLEAN) AS planned_vs_actual_flag` (constant NULL column); CONCAT NULL folding (see above).
6. Tests: `lap_id` unique, not null; `stint_id` not null; flags not null; age in [1, 100]; relationships (compound code, race, driver); many singular tests: `assert_stint_boundaries_match_pits`, `assert_tyre_run_key`, `assert_stint1_includes_lap1`, `assert_stint_geometry_2018_compound_code_null`, `assert_hardness_scale_no_gaps`, `assert_pit_not_taken_from_joined_boundary`. Good coverage of the run-joining logic.

---

## 17. int_synthetic_teammate  (QUESTIONABLE)

1. Purpose: for each ego driver and lap, compare the teammate's fuel-corrected lap time, adjusted to the ego's tyre state, to the ego's.
2. Flow: reads `int_lap_fuel_state`, `int_stint_geometry`, `int_compound_cliff_predicted`, `stg_laps`. Read by `fct_driver_skill_features`.
3. How it works: pairs = valid laps of two different drivers of the same constructor on the same lap (l.63-79); `skill_proxy = (tm_wc + (ego_expected_compound_pace - tm_expected_compound_pace)) - ego_wc` (l.128-133); `strategic_divergence_flag` = valid-lap ordinals differ by more than 3 (l.138-139); `pair_quality_weight = 1 / (1 + stddev(proxy over 5 rows))` (l.161-169).
4. Maths check:
   - SOUND: sign (positive = ego faster; teammate adjusted up when the ego tyre is slower, i.e. both expected paces are "seconds slower" terms); fuel handled by using weight-corrected times; teammate pairs by same lap, so track evolution and weather cancel.
   - QUESTIONABLE l.161-169: the weight is the standard deviation of the skill proxy over `ROWS BETWEEN 4 PRECEDING AND CURRENT ROW` per (race, ego, teammate). It includes the current lap's own value, so an outlier lap lowers its own weight, i.e. the weight depends on the outcome being weighted. The window is five *rows* of paired valid laps, not five consecutive laps, so after an SC or pit stop it spans many laps. The header says "stddev of teammate speed_residuals", but the code uses the skill proxy.
   - QUESTIONABLE (small): for constructors with three drivers on the same lap (reserve driver) the ego appears once per teammate; the yml unique key (year, race, ego, lap) would then fail, so this is presumably absent in Bronze.
   - `teammate_available_flag` (l.140) is always TRUE (the inner join guarantees a teammate lap); the identity test relies on it.
5. Fills: l.161-168 `COALESCE(STDDEV(...), 0.5)`: the first row of each pair (a single value has no standard deviation) gets a stddev of 0.5 s, so weight 0.667. Not a data-driven number.
6. Tests: unique (year, race, ego, lap); not nulls; relationships; singular `assert_synthetic_teammate_identity` (when both laps share compound and age, the adjusted teammate time must equal the unadjusted one within 1 ms). It checks the adjustment term is zero when it should be, a real maths check, but not the weight, sign or window.

---

## 18. int_track_evolution  (QUESTIONABLE)

1. Purpose: per race and lap, a linear rubber-in trend and a temperature-linked ambient term fitted to the field pace curve.
2. Flow: reads `int_field_pace_curve`, `stg_weather`. Read by `int_lap_residual_decomposed`, `int_constructor_structural_pace`, `int_dirty_air_tax_component`, `int_driver_race_paired_laps`, `int_driver_race_skill_loro`, `int_lap_normalized_pace`, `mart_corner_skill_driver`.
3. How it works: field pace (already fuel and compound corrected, restricted to clean-air laps, thin cells removed) per lap; weather per lap = the latest sample, ties broken by driver (l.32-47); OLS slope of pace on lap number with centred sums (l.79-98), clipped to at most 0 by `LEAST(slope, 0.0)`; `rubber_component = slope * (lap - mean_lap)` (centred, so it averages to zero within the race); residual regressed on track temperature (centred OLS) for the ambient term; unexplained = residual - ambient.
4. Maths check:
   - SOUND: centred OLS formulas are correct; the weather tie-break is deterministic; because the input is fuel and compound corrected, the trend is not fuel burn.
   - QUESTIONABLE l.85-92: `LEAST(slope, 0.0)` clips a positive slope to zero (documented: pace only improves with rubber). In a race with rising lap times through the field (rain arriving) the trend is forced flat and the rise lands in the residual and ambient terms. Also, a NULL slope (single lap, zero variance) becomes 0.0 through the NULL-skipping `LEAST`.
   - QUESTIONABLE l.133-147: the fit is sequential, not joint. The linear rubber trend is removed first, then temperature is regressed on what is left. Any temperature drift that is collinear with lap number is absorbed by the rubber slope, so the "rubber" term can contain a temperature trend and the "ambient" term only sees the part orthogonal to it. A joint fit of pace on lap and temperature would separate them differently.
   - The header describes the model as an "in-SQL linear approximation that captures ~80% of the rubber effect"; no check of that figure was possible here.
5. Fills: l.156-159 and l.162-164 `COALESCE(ambient, 0.0)`: a lap with no temperature (or a race with no ambient slope) gets no ambient correction and the whole residual stays "unexplained"; the `LEAST` NULL case above.
6. Tests: unique (year, race, lap); not nulls; relationship on `race_id`; singular `assert_track_evolution_monotone_dry` / `_wet`, `assert_residual_components_not_in_base`, `assert_lap_7term_identity`, `assert_thermal_variance_positive`. The monotone tests check the clipped slope sign, which holds by construction.

---

## 19. int_track_geometry  (WRONG)

1. Purpose: per season and circuit, 25 m bins of median X/Y/Z, gradient, Menger curvature and a lateral-acceleration proxy.
2. Flow: reads `source('bronze_f1','raw_telemetry')` directly (the layer contract in the README says staging only) and `race_to_track`. Read by no model (a comment in `dim_corners` mentions it).
3. How it works: median X/Y/Z/speed per 25 m of lap distance across all drivers and laps of a season-circuit (l.50-62); gradient = dZ / dDistance over the previous bin (l.89-92); Menger curvature `4A / (abc)` from previous, current and next bin (l.97-109); `lateral_accel_proxy_ms2 = speed_ms^2 * curvature` (l.125).
4. Maths check:
   - WRONG l.99-109 (`curvature_per_m`), l.125 (`lateral_accel_proxy_ms2`) and l.91 (`gradient_dz_ds`): the units are not metres. FastF1 position X/Y/Z are in 1/10 m. Verified on Bronze: for Bahrain 2023 VER lap 10 the summed X/Y path length is 53,388 raw units against a lap distance range of 5,360 m, a ratio of 9.96. So curvature computed from raw X/Y is per tenth of a metre, i.e. 10 times too small when labelled per metre, and `v^2 * kappa` is 10 times too small when labelled m/s^2. The gradient `dZ/ds` divides a raw (tenth-metre) Z difference by metres, so it is 10 times too large if Z has the same unit. The header says Z is "not verified as literal SI metres" but does not say X/Y are tenth-metre. The Menger formula itself is correct (`4 * |cross| / 2` = 4 x area). The spot check in the header (Monaco hairpin is the sharpest) tests rank, not scale.
   - The model has no consumer in the tree, so no downstream number is wrong today.
   - Not an error but a note: bins use the median over all drivers' lines, so curvature is that of the median line, and pit-lane samples (distance > 0) are included in the bin medians.
5. Fills: none (NULL at season edges and collinear points, by design).
6. Tests: unique (year, track, bin); not nulls. Shape only; nothing checks magnitudes or units.

---

## 20. int_traffic_exposure_driver_race  (SOUND)

1. Purpose: per driver and race, how much of the race was spent close behind the physical car ahead, and how much could not be measured (lapped, overlapping, unknown, lap 1).
2. Flow: reads `int_lap_physical_ahead`. Read by `int_traffic_exposure_race`.
3. How it works: lap partition by `validity_class` and neutralised flag; time within 1 s and measured time are summed on measured laps only (valid_same_lap and not neutralised); shares are ratios of sums with `NULLIF`; bunching = laps with any moment within 1 s over measured laps.
4. Maths check: SOUND. Ratios are sums over sums (time-weighted), denominators use `NULLIF`, the lap partition columns sum to `n_laps` (tested). Rounding to 3 or 4 dp (l.39-69) in an intermediate model breaks the README rule "no rounding in intermediate" but does not change a number meaningfully. `MIN(season)` and `GROUP BY race_id, driver_id` are consistent.
5. Fills: none (NULLIF only).
6. Tests: unique (race, driver); `share_time_close_behind` and `bunching_share` in [0, 1]; singular `assert_traffic_exposure_lap_partition` (partition sums to `n_laps`). The partition test is a real identity.

---

## 21. int_traffic_exposure_race  (SOUND)

1. Purpose: race-level roll-up of the driver-race exposure table.
2. Flow: reads `int_traffic_exposure_driver_race`. Read by no model.
3. How it works: sums counts and seconds across drivers; shares are pooled (sum of numerators over sum of denominators), not an average of driver shares (l.25-32); flip rate = flips over pairs.
4. Maths check: SOUND. Pooling is stated and implemented correctly; `NULLIF` on every denominator except `SUM(n_laps)` (always positive when a row exists). It sums values that were already rounded per driver (3 dp), which is negligible.
5. Fills: none.
6. Tests: `race_id` unique, not null; singular `assert_physical_ahead_flip_rate`. Shape plus a flip-rate bound.

---

## 22. int_tyre_surface_vs_bulk_decoupling  (QUESTIONABLE)

1. Purpose: for laps past the tyre cliff, split degradation into surface and bulk thermal load and give a recovery flag and recovery probability.
2. Flow: reads `int_lap_thermal_proxy`, `int_lap_residual_decomposed`. Read by no model (app `tyre-recovery-forecast`).
3. How it works: `surface_bulk_ratio = (S/2.864) / ((S/2.864) + (B/4.403))` where S and B are the two exponentially weighted push loads (tau 3 and 5 laps); the weight sums equal the literal weights in `int_lap_thermal_proxy` (1+.717+.514+.369+.264 = 2.864; 1+.819+.670+.549+.449+.368+.301+.247 = 4.403, checked); class 'bulk_driven' if ratio < 0.35 else 'mixed'; `recovery_flag` = average of next two laps' skill residual below the current one; `thermal_attribution_s = ratio * compound_component_s`; `recovery_probability = sigmoid(2 * (ratio - 0.5)) / (1 + 0.1 * laps_past_cliff)`.
4. Maths check:
   - SOUND: the ratio normalisation (steady push gives 0.5, ceiling 0.606) and the look-ahead windows (computed over all laps of the stint before the post-cliff filter, so LEADs reach beyond the cliff).
   - QUESTIONABLE l.78-79, 125, 134, 155, 166: a missing thermal load becomes 0.0, the ratio is then NULL (0 over 0), and every use re-defaults it to 0.5. The class becomes 'mixed', thermal attribution is half the compound component and the probability uses 0.5. These are invented values that pass the `not_null` and range tests.
   - QUESTIONABLE l.158-169: `recovery_probability` is an unfitted function (constants 2.0 and 0.1) described as an approximation to a logistic fit done in a notebook; it is not a probability estimated from data. It cannot exceed about 0.53 with ratio <= 0.606, and the outer `GREATEST(0, LEAST(1, ...))` is a no-op.
   - QUESTIONABLE l.154-156: `thermal_attribution_s = ratio * compound_component_s` multiplies a share of push load by the compound wear term; the ratio is the surface share of push load, not the share of degradation due to thermal damage. A heuristic label.
   - QUESTIONABLE l.138-150: `recovery_flag` selects laps after the cliff on the residual and asks whether later residuals are lower, which tends to be true by regression to the mean even with no recovery mechanism. The null hypothesis in the header is a logistic test not run in SQL.
5. Fills: l.78-79 `COALESCE(load, 0.0)`; l.125, 134, 155, 166 `COALESCE(surface_bulk_ratio, 0.5)`; l.156 `COALESCE(compound_component_s, 0.0)` (no compound term gives zero attribution); l.136 `ELSE 'mixed'`.
7. Tests: `lap_id` unique, not null; `surface_bulk_ratio` not null and in [0, 0.606]; `degradation_source` accepted values; `recovery_probability` in [0, 1]; `thermal_attribution_s` not null; singular `assert_degradation_source_classes_reachable`. These are shape and range. Note the `not_null` and range tests pass because of the 0.5 fill.

---

## Not covered by this group

`src_fits.yml`, `unit_tests_rating_chain.yml` and `_paired_laps.yml` describe models in the int_a to int_l range (fits sources, rating chain, paired laps); they hold no tests on the models above and were not audited here.

---

## Findings list

### WRONG

1. `int_track_geometry.sql` l.99-109, l.125 (and l.91): X/Y/Z are in 1/10 m (Bronze check: path 53,388 raw units over 5,360 m). `curvature_per_m` and `lateral_accel_proxy_ms2` come out 10 times too small; `gradient_dz_ds` 10 times too large if Z has the same unit. No model consumes it today.
2. `int_qualifying_decomposed.sql` l.145-147 (and header l.6-8; yml `schema.yml` l.2359-2362; app `methodology.tsx` l.16-17): both residuals are positive = slower, so `quali - race` is positive for a race specialist. The documented meaning "positive = qualifying specialist / faster in qualifying" is inverted.

### QUESTIONABLE

1. `int_pit_strategy_cost_curve.sql` l.418 and l.100: the new set is priced from age 1, while the old set (and every stint's first valid lap) starts at age 2 because out-laps are invalid. New-set wear is understated by about gradient x laps_on_new_set, which biases the optimum toward earlier stops.
2. `int_pit_strategy_cost_curve.sql` l.356: `COALESCE(new_c.cum_wear_s, 0.0)` gives a free new tyre when the next compound has no fitted curve; same zero as the no-stop case. Also l.262 `COALESCE(hazard, 0.0)` zeroes the SC discount for any stint with no hazard row, not only 2018.
3. `int_pit_strategy_cost_curve.sql` l.363-381: magic constants (0.005, 30, 20) and no compound base-pace offset between compounds.
4. `int_pit_strategy_value.sql` l.471, l.492-495, l.469-470: `GREATEST(NULL, 0.0)` returns 0.0, so a missing actual or optimal cost becomes "no opportunity cost" (0.0), not NULL.
5. `int_pit_strategy_value.sql` l.502-524: with a NULL `actual_offset` the verdict falls to `ELSE 'early'` instead of 'unknown'. l.423-428 can mix a race-scope actual cost with a window-scope optimum.
6. `int_pit_strategy_value.sql` l.161-164, l.516-522: undercut threat uses gap ahead, fires in about 95% of stints, with a hardcoded `-2` margin.
7. `int_qualifying_decomposed.sql` l.146: `COALESCE(race_avg, 0.0)` makes the delta equal to the qualifying residual, and the app then shows a race skill of exactly 0.0. l.154 and l.156: `quali_traffic_flag` NULL and `dnq_flag` constant FALSE make the app's two filters no-ops. l.145: difference of two residuals on different baselines.
8. `int_microsector_proximity.sql` l.342-352 and l.366-371: field median over cars with the same lap number, who cross at different clock times (up to a lap apart); the header claims the field effect cancels "at that moment". l.247: `exit_gap_ahead_s` is not gated on `has_next`.
9. `int_pit_loss_circuit.sql` l.43-52: baseline is the whole-race median lap (ignores fuel and tyre trend); l.113-115 hard truncation to [8, 60] s; l.146-150 labelled EB but a fixed pseudo-count blend.
10. `int_sector_residual_decomposed.sql` l.155 and l.171-183: sector baseline (field sector median) differs from the lap baseline, so the sector residual is not the sector share of the lap residual (test header: gap up to 64.7 s); l.154 divides by `lap_time_s`, not the sum of sector times.
11. `int_synthetic_teammate.sql` l.161-169: weight uses the stddev of the outcome itself including the current lap, over five paired rows (not five laps), with a 0.5 default for the first row; l.140 `teammate_available_flag` is constant TRUE.
12. `int_track_evolution.sql` l.85-92: `LEAST(slope, 0.0)` clips positive slopes and turns a NULL slope into 0.0; l.133-147: sequential rather than joint fit of rubber and temperature; l.156-164 COALESCE 0.0 for missing temperature.
13. `int_tyre_surface_vs_bulk_decoupling.sql` l.78-79, 125, 134, 155, 166: missing thermal load imputed as ratio 0.5; l.158-169 `recovery_probability` is an unfitted formula presented as a probability; l.154-156 `thermal_attribution_s` heuristic; l.138-150 recovery flag subject to regression to the mean.

### Notes (not findings)

- `int_stint_geometry.sql` l.212-220: `CONCAT` folds a NULL `stint_number` to `year_race_driver_`, so the `stint_id` not-null test cannot catch unassigned laps; handled in `int_stint_end_regime` l.103-121. The header says such laps "stay NULL", which holds for `stint_number` only.
- `int_track_geometry.sql` l.43 reads `raw_telemetry` directly, against the README layer contract (staging only).
- 2018 Italian GP (HD15 B): no race data; affects only the Monza 2019 SC prior (thinner, not biased). 2026 not audited.
