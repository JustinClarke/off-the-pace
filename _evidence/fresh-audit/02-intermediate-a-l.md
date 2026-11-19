# Fresh audit 02: intermediate models int_a to int_l

Scope: 38 files in `transform/models/intermediate/` matching `int_[a-l]*` (37 `.sql`, 1 `.py`).
Read only. Current Bronze is the only truth. 2018 Italian GP race session (HD15 B) has no Bronze and simply yields no rows. 2026 is set aside and not audited.
Line numbers are file lines in `transform/models/intermediate/<model>.sql` unless stated.

Verdict totals: SOUND 14, QUESTIONABLE 22, WRONG 2 (deg_sensitivity is WRONG only for its cliff-onset-shift half). See the end of the file for the ranked list.

---

## 1. Flow (edges inside this group, then upstream outside the group)

Edges between models in this group (A -> B means B reads A):

```
int_compound_cliff_predicted -> int_field_pace_curve
int_compound_cliff_predicted -> int_dirty_air_tax_component
int_compound_cliff_predicted -> int_lap_residual_decomposed
int_compound_cliff_predicted -> int_constructor_deg_sensitivity
int_lap_fuel_state -> int_field_pace_curve
int_lap_fuel_state -> int_constructor_structural_pace
int_lap_fuel_state -> int_dirty_air_tax_component
int_lap_fuel_state -> int_driver_race_paired_laps
int_lap_fuel_state -> int_driver_race_skill_loro
int_lap_fuel_state -> int_lap_residual_decomposed
int_lap_fuel_state -> int_lap_thermal_proxy
int_lap_fuel_state -> int_lap_normalized_pace
int_lap_air_state -> int_field_pace_curve
int_lap_air_state -> int_dirty_air_tax_component
int_lap_air_state -> int_driver_isolation_lap_panel
int_lap_air_state -> int_lap_normalized_pace
int_event_corrections -> int_constructor_structural_pace
int_event_corrections -> int_dirty_air_tax_component
int_event_corrections -> int_driver_race_paired_laps
int_event_corrections -> int_driver_race_skill_loro
int_event_corrections -> int_lap_residual_decomposed
int_event_corrections -> int_lap_normalized_pace
int_field_pace_curve -> int_constructor_structural_pace
int_field_pace_curve -> int_dirty_air_tax_component
int_field_pace_curve -> int_driver_race_skill_loro
int_field_pace_curve -> int_lap_residual_decomposed
int_field_pace_curve -> int_lap_normalized_pace
int_field_pace_curve -> int_track_evolution (outside group)
int_constructor_structural_pace -> int_lap_residual_decomposed
int_constructor_structural_pace -> int_circuit_x_constructor_interaction
int_constructor_structural_pace_qualifying -> int_lap_residual_decomposed_qualifying
int_lap_fuel_state_qualifying -> int_lap_residual_decomposed_qualifying
int_dirty_air_tax_component -> int_lap_residual_decomposed
int_dirty_air_tax_component -> int_driver_isolation_lap_panel
int_lap_residual_decomposed -> int_lap_anomaly_flags
int_lap_residual_decomposed -> int_lap_residual_stint_detrend
int_lap_residual_decomposed -> int_constructor_deg_sensitivity
int_lap_residual_decomposed -> int_driver_isolation_lap_panel
int_lap_anomaly_flags -> int_driver_isolation_lap_panel
int_lap_anomaly_flags -> int_lap_telemetry_aggregates
int_driver_isolation_lap_panel -> int_driver_isolation_lap_pace
int_constructor_car_fe_isolation -> int_driver_isolation_lap_pace
int_driver_isolation_lap_pace -> int_driver_isolation_stint_tyre
int_driver_isolation_lap_pace -> int_driver_isolation_lap_values
int_driver_isolation_stint_tyre -> int_driver_isolation_lap_values
int_constructor_car_fe -> int_driver_race_skill_loro
int_driver_race_paired_laps -> int_driver_race_skill_loro
int_driver_race_skill_loro -> int_driver_season_ratings
int_driver_race_skill_loro -> int_driver_circuit_affinity
int_driver_race_skill_loro -> int_driver_circuit_era_affinity
int_driver_season_ratings -> int_era_normalized_driver_rating
int_corner_metrics -> int_corner_skill_residuals
int_corner_skill_residuals -> int_corner_drift_from_early_stint
int_corner_skill_residuals -> int_lap_corner_inputs
int_corner_drift_from_early_stint -> int_lap_corner_drift
int_lap_physical_ahead -> int_traffic_exposure_driver_race (outside group)
```

Leaves inside the group (no consumer in `transform/models`): `int_driver_circuit_affinity`, `int_driver_circuit_era_affinity` (read by app exports, not by a model), `int_lap_normalized_pace` (documented leaf, "offline solver only").

Edges from this group to models outside it (consumers):

```
int_cell_power_law_fit -> fct_power_law_training
int_circuit_x_constructor_interaction -> fct_ghost_car_pace
int_compound_cliff_predicted -> int_pit_strategy_value, int_synthetic_teammate, fct_cliff_prediction_features, fct_ghost_car_pace
int_constructor_deg_sensitivity -> fct_ghost_car_pace
int_constructor_structural_pace -> fct_driver_skill_features, fct_ghost_car_pace
int_corner_metrics -> fct_telemetry_deltas
int_corner_skill_residuals -> mart_corner_skill_driver
int_dirty_air_tax_component -> fct_stint_features, mart_driver_season_summary, mart_metric_benchmark, mart_race_driver_summary
int_driver_isolation_lap_values -> fct_driver_isolation_lap, fct_driver_isolation_pair_lap
int_driver_isolation_stint_tyre -> fct_driver_isolation_race, fct_driver_isolation_stint
int_driver_race_paired_laps -> mart_race_driver_summary
int_driver_race_skill_loro -> mart_race_coverage, mart_race_driver_summary
int_era_normalized_driver_rating -> mart_driver_season_summary
int_event_corrections -> fct_cliff_prediction_features, mart_corner_skill_driver
int_lap_air_state -> int_pit_strategy_value, int_sector_residual_decomposed, fct_cliff_prediction_features, fct_stint_features, mart_race_coverage
int_lap_anomaly_flags -> fct_cliff_prediction_features, fct_driver_skill_features, fct_stint_features
int_lap_corner_drift, int_lap_corner_inputs -> fct_cliff_prediction_features
int_lap_fuel_state -> int_synthetic_teammate, fct_power_law_training, fct_stint_features
int_lap_proximity -> fct_cliff_prediction_features
int_lap_residual_decomposed -> int_power_law_lap, int_qualifying_decomposed, int_sector_residual_decomposed, int_tyre_surface_vs_bulk_decoupling, fct_cliff_prediction_features, fct_driver_skill_features, fct_ghost_car_pace, fct_lap_residuals, fct_stint_features, mart_degradation_history_envelope
int_lap_residual_decomposed_qualifying -> int_qualifying_decomposed
int_lap_residual_stint_detrend -> fct_cliff_prediction_features
int_lap_telemetry_aggregates -> fct_cliff_prediction_features, fct_driver_isolation_lap
int_lap_thermal_proxy -> int_tyre_surface_vs_bulk_decoupling, fct_cliff_prediction_features, fct_stint_features
```

Upstream outside the group (sources and refs):

- bronze_f1: `raw_telemetry` (int_lap_air_state), `raw_telemetry` + `raw_laps` (int_lap_physical_ahead)
- fits parquet sources: `fits.constructor_car_fe`, `fits.constructor_car_fe_isolation` (written by Python fitters, not audited here)
- staging: `stg_laps`, `stg_laps_qualifying`, `stg_telemetry`, `stg_telemetry_position`, `stg_weather`, `stg_pits`, `stg_results`, `stg_sector_times`
- intermediate (outside group): `int_stint_geometry`, `int_track_evolution`, `int_power_law_lap`, `int_qualifying_push_laps`
- dims/seeds: `dim_compounds_season`, `dim_corners`, `dim_circuits`, `race_to_track`, `race_scheduled_laps`, `circuit_reference`, `compound_hardness_scale`, `seed_manual_lap_exceptions`
- macros: `power_law_beta_grid`, `compound_cliff_wear` (cliff_*), `bayesian_shrinkage`, `posterior_variance`, `trailing_median`, `clamp_or_null`, `driver_isolation_pure_season_offset`, `fuel_regulatory_max_kg`, `circuit_id_from_name`

Note on a cycle-looking path that is not a cycle: `int_field_pace_curve -> int_track_evolution -> int_lap_residual_decomposed`, and `int_field_pace_curve -> int_lap_residual_decomposed` directly.

---

## 2. Model sections

Test notation: "shape" = not_null/unique/relationships/accepted_values/range only. "maths" = a test re-derives or pins a number. Singular tests are in `transform/tests/`.

### int_cell_power_law_fit
1. Purpose: pooled power-law tyre degradation fit per (race, compound hardness rank), the training target for the power-law ML model.
2. Flow: reads `int_power_law_lap` and macro `power_law_beta_grid()`. Read by `fct_power_law_training`.
3. How it works: keeps stints with at least 5 laps and at least 2 distinct tyre ages (54-69). For each beta on the grid 0.20..3.00 step 0.05 (macro, `generate_series(4,60)/20`) it computes x = age^beta, demeans x and y within stint (110-111), then alpha = Sxy/Sxx and SSE = Syy - Sxy^2/Sxx (131-132). The beta with the smallest SSE wins, ties to the smallest beta (140-143). `r2_within = 1 - SSE/Syy` (163). `curve_incr_{5,10,15,20}_s = alpha*(a^beta - 2^beta)` (165-172). `fit_eligible` = at least 3 stints and 40 laps (173).
4. Maths check: within-stint demeaning removes the per-stint intercept, and alpha through the origin on demeaned data is the right profile estimator. Cross join of grid by laps is bounded (57 betas). No division issue (WHERE sxx > 0 AND syy > 0 at 134). One hard-coded duplicate of the grid edge: `r.beta_k IN (4, 60)` at 164 duplicates the macro bounds; if the macro changes, the edge flag silently lies. The anchor `'2.0'` (36) duplicates a Python constant (comment 19, 35). No standard error is produced for alpha or beta, so downstream cannot weight cells by precision; that is a design gap, not an error. Alpha is allowed negative on purpose (22-26).
   Verdict: SOUND.
5. Fills: none (no COALESCE/ELSE). `MIN(compound_label)` etc at 76-79 pick one of possibly many labels; guarded by test `n_compound_labels = 1`.
6. Tests: unique (race_id, compound_hardness_rank); cell_id not_null/unique; beta/r2_within not_null; `n_compound_labels` accepted [1]. Singular: `assert_power_law_fit_bounds`, `assert_power_law_no_seed_columns`. Mostly shape; the bounds test checks ranges of fitted values.

### int_circuit_x_constructor_interaction
1. Purpose: per (constructor, race) circuit-specific bonus/penalty from prior visits to the same physical circuit.
2. Flow: reads `int_constructor_structural_pace`, `race_to_track`, `circuit_reference`. Read by `fct_ghost_car_pace`.
3. How it works: deviation = this race's constructor structural pace minus the constructor's season-to-date mean over strictly earlier rounds (86-90, 106). Then for the pairing (constructor, circuit) take the expanding window over strictly prior visits (122-126), mean `observed_mean_s`, population SD, count. Shrunk = n*mean/(n+3) (135-136). Round order uses `CAST(SPLIT_PART(race_id,'_',2) AS INTEGER)` (45) so 2023_10 sorts after 2023_2. Point-in-time, no forward reach.
4. Maths check: windows are right (ROWS ... 1 PRECEDING). Shrinkage to 0 with prior weight 3 is a normal-normal form with a hard-coded weight (136). Questionable points:
   - Line 106: the deviation from the season-to-date mean also contains genuine in-season car development (upgrades). A car that gets faster through the year looks "good at later circuits", and that is booked as a circuit effect.
   - Lines 120 and 157: `interaction_se_s` is `STDDEV_POP` of past deviations, a spread, not a standard error of the shrunk mean. It is 0.0 for n=1 (population SD of one value) and forced to 0.0 for n=0 by the COALESCE. A one-visit pairing therefore reports zero uncertainty. Also biased low (POP instead of SAMP).
   - The structural pace input is race-centred over the constructors present (unweighted mean), so the season-to-date mean is a mean of centred values; fine for deviations but the baseline is itself drifting as the field changes.
   Verdict: QUESTIONABLE.
5. Fills: 73 `COALESCE(cm.circuit_id, rm.circuit_key)` (falls back to the event slug, splits a double-header venue if the map misses). 155 `COALESCE(shrunk_interaction_s, 0.0)` (first visit gets an interaction of exactly 0 s, indistinguishable from a measured zero except via `interaction_obs_n = 0`). 156 `COALESCE(n_obs,0)`. 157 `COALESCE(observed_std_s,0.0)` (n<=1 gets "SE 0").
6. Tests: constructor_race_id not_null/unique, interaction not_null. Shape only. No test checks the point-in-time property or the shrinkage maths.

### int_compound_cliff_predicted
1. Purpose: per valid lap, expected tyre-wear pace term (hockey-stick: linear wear plus a bounded cliff ramp plus a temperature offset) and its first derivative.
2. Flow: reads `int_stint_geometry` (valid laps only), `race_to_track`, `dim_compounds_season`, `stg_weather`, macros `compound_cliff_wear_s`, `cliff_severity_span`, `cliff_ramp_slope_s_per_lap`. Read by `int_field_pace_curve`, `int_dirty_air_tax_component`, `int_lap_residual_decomposed`, `int_constructor_deg_sensitivity`, `int_pit_strategy_value`, `int_synthetic_teammate`, `fct_cliff_prediction_features`, `fct_ghost_car_pace`.
3. How it works: joins lap to the seed row for (track, season, compound) (104-108), to a per-lap track temperature (59-77, `DISTINCT ON (race, lap_number)` taking the latest `weather_session_time_s`, ties by driver_id), computes `laps_past_cliff = max(age - onset, 0)` (132-140), `ambient_temp_delta = clamp(track_temp - optimal_low, 0, 30)` (120-128), wear via macro = LEAST(gradient*(age - held) + severity*ramp_fraction, 10 s) (185-188), and `expected_compound_pace_s = wear + 0.005*ambient_temp_delta` (227-232). Derivative column (251-265).
4. Maths check:
   - Line 65-76: weather is taken as one value per (race, lap_number) by choosing the latest-timestamp reading across all drivers' rows; it is a field-wide track temperature at the end of that lap number, not the lap's own time. Lap numbers run out of phase across the field by tens of seconds; error is small for temperature but it is not what the comment implies.
   - Line 232: the temperature coefficient 0.005 s per degree C is a literal constant, not fitted (the header says all coefficients come from the seed). The quadratic and the unitless grip_peak were removed on purpose; this constant remains. Effect size: up to 0.15 s at the 30 C clip. It is the same for every compound and circuit.
   - Lines 136 and 141: `COALESCE(compound_cliff_onset_laps, 999.0)`. For a lap whose seed cell is missing, laps_past_cliff becomes 0 (not NULL) because age - 999 < 0. In the wear macro `COALESCE(gradient,0.0)*age + COALESCE(severity,0)*0` = 0.0, so `compound_wear_s` is 0.0 (not NULL) and `expected_compound_pace_s` is 0.005*delta. The comment block at 157-172 says cell-less laps are "NULL, unknown is what they now say". That is only true for onset/severity/gradient passthrough columns; the wear total and pace total are priced as a free tyre for these laps. These are laps whose compound is unknown. Line 254 also gives `expected_degradation_rate_s_per_lap = 0` on the same laps (COALESCE(gradient,0) with laps_past_cliff = 0).
   - Wear is `gradient*age` anchored at age 0, not relative to a fresh lap. This is fine only because the field base subtracts the same curve (field pace curve uses the same term), so it cancels in residuals. It would not cancel if used alone.
   - Line 141: `cliff_onset_passed = age > COALESCE(onset,999)` is FALSE for cell-less laps, so such laps look "pre-cliff" to every consumer.
   Verdict: QUESTIONABLE (cell-less laps priced as zero wear, constant 0.005, one-reading weather).
5. Fills: 122 `COALESCE(track_temp_c, 30.0)` and 123 `COALESCE(compound_optimal_temp_low, 20.0)` (a lap with no weather gets delta 10 C, i.e. +0.05 s; no seed gets the same). 136 and 141 `COALESCE(onset, 999.0)` (laps_past_cliff 0, cliff never passed). Macro: `COALESCE(gradient,0.0)` and `COALESCE(severity,0.0)` (wear 0), 254 `COALESCE(compound_wear_gradient, 0.0)` (rate 0), 255 and 264 `ELSE 0.0`. 126 and 30.0 clip.
6. Tests: not_null on compound_wear_s, compound_wear_gradient, expected_compound_pace_s (these pass on the 0.0 fill, so they cannot detect the issue); lap_id unique. Singular: `assert_compound_pace_units`, `assert_compound_wear_bounded`, `assert_compound_wear_not_extrapolated`, `assert_degradation_rate_follows_wear_hold`, `assert_no_cap_valued_wear`, `assert_cliff_predictions_valid`, `assert_field_base_drift_tracks_observed`, `assert_pace_delta_flat_by_race_fifth`, `assert_race_to_track_covers_all_races`. The wear/derivative tests do check the maths of the curve (bounds, hold, derivative). Nothing checks the cell-less lap behaviour.

### int_constructor_car_fe
1. Purpose: typed pass-through of the de-biased constructor-by-race car fixed effect fitted outside dbt.
2. Flow: `source('fits','constructor_car_fe')`. Read by `int_driver_race_skill_loro`.
3. How it works: casts columns and builds an id (25-37). No logic.
4. Maths check: the fit itself is Python, outside this audit (could not check). SQL side is trivially correct.
   Verdict: SOUND (SQL only; the fit is not audited here).
5. Fills: none.
6. Tests: id unique/not_null, race_id and constructor_id relationships, car_fe_s not_null. Shape only. Also referenced by a unit test in `unit_tests_rating_chain.yml`.

### int_constructor_car_fe_isolation
1. Purpose: typed pass-through of the isolation-panel car term fitted outside dbt (car_iso_s, source flag, era).
2. Flow: `source('fits','constructor_car_fe_isolation')`. Read by `int_driver_isolation_lap_pace`.
3. How it works: casts only.
4. Maths check: nothing to check in SQL; fit not audited here.
   Verdict: SOUND (SQL only).
5. Fills: none. (`connectivity_note` and `car_term_source` pass through.)
6. Tests: id unique/not_null, relationships, `car_term_source` accepted values [driver_id, unidentified, not_estimated]. Shape only.

### int_constructor_deg_sensitivity
1. Purpose: per (season, constructor, compound) deviation of tyre degradation slope from the field, and a per-constructor "cliff onset shift" in laps, both empirical-Bayes shrunk.
2. Flow: reads `int_lap_residual_decomposed`, `int_compound_cliff_predicted`, `dim_compounds_season`. Read by `fct_ghost_car_pace`.
3. How it works, slope half (166-281): clean dry pre-cliff laps (correction_weight 1, no rain, valid_lap_in_stint > 1, cliff not passed), residual regressed on tyre age with stint fixed effects (demean within stint, 195-197), per cell slope = Sxy/Sxx (209). SE = sqrt(RSS/(n - n_stints - 1)/Sxx), floor 0.0001 (228-235). Cell qualifies at 30 laps and 5 stints. Field mean = precision-weighted mean of qualifying cells (245-247). tau^2 is DerSimonian-Laird: (sum w*dev^2 - (k-1)) / (sum w - sum w^2/sum w), floored at 0 (270-277). Shrunk deviation = dev*tau^2/(tau^2+se^2) (538).
   Cliff half (290-521, 568-579): residual regressed on (age, hinge = laps_past_cliff) with stint FE; extra hinge slope field-centred and shrunk the same way; converted to an onset shift by `-hinge_dev_shrunk*ref_depth / severity_used`, clamped to +/-3 (568-572).
4. Maths check:
   - Slope half: the form is right (FE slope, DL tau^2, shrink factor). The degrees of freedom `n_laps - n_stints - 1` are right for one slope plus stint intercepts. Concern at 228-235: the SE treats laps as independent. Laps within a stint are serially correlated (the isolation model measures lag-1 correlation itself) and laps in the same race share track evolution. The SE is therefore too small, tau^2 is overestimated (it absorbs noise as between-constructor spread because the DL formula subtracts only sampling variance from se^2), and shrinkage is weaker than it should be. Floor 0.0001 at 234 is harmless.
   - Line 232: `NULLIF(sxx,0)` plus `sxx > 0` in `qualifies` is fine; `slope_se` can be NULL for non-qualifying cells only if sxx = 0, then the `GREATEST(NULL,0.0001)` returns 0.0001 in DuckDB (GREATEST skips NULL). That gives a fake tiny SE to a cell with no slope; it is masked at 543 (`CASE WHEN qualifies THEN slope_se END`) but `1.0/(se*se)` at 258 uses the fake value. Not used in field mean (WHERE qualifies).
   - WRONG, cliff onset shift (468, 568-579, 584): the owner's own comment at 437-463 records this as a KNOWN DEFECT (08m). `severity_used` is the fitted cliff step in seconds (floored at 0.30), but the conversion `hinge_dev * ref_depth / severity` needs a rate (s per lap). hinge_dev is s per lap per lap past onset; times ref_depth gives seconds; dividing seconds by a step in seconds gives a unitless ratio, which is then published as "laps". The correct divisor is the ramp slope (severity / cliff_ramp_span_laps = severity / 2.5), so the shift is understated by a factor of 2.5 relative to a slope divisor. The regressor is also a linear hinge, while the fitted curve in `int_compound_cliff_predicted` saturates at onset + 2.5 laps, so the regression regressor and the curve it adjusts do not match. The output column is named `cliff_severity_used_s_per_lap` (584) but holds seconds. The `cliff_onset_shift_laps` column feeds `fct_ghost_car_pace`.
   - `COALESCE(clamp_or_null(...), 0.0)` at 568-574 maps a missing reference depth to a zero shift, which is the intended neutral value, but also hides cells where `severity_used` is NULL.
   Verdict: WRONG for `cliff_onset_shift_laps` and `cliff_onset_shift_se_laps` (units, known and acknowledged); slope half QUESTIONABLE (SE ignores correlation).
5. Fills: 180 and 183 `COALESCE(rainfall_flag,FALSE)`, `COALESCE(cliff_onset_passed,FALSE)` (a lap with unknown rain/cliff state is kept as dry and pre-cliff). 271-276 `COALESCE(tau2 numerator, 0)` and `GREATEST(...,0)` (undefined tau^2 becomes 0, meaning complete shrinkage to zero deviation). 468 `GREATEST(MEDIAN(severity), 0.30)` (floors severity; comment says the floor binds nowhere today). 509 `ELSE 0.0` and 539 `ELSE 0.0` (non-qualifying cells get a zero adjustment, flagged by `is_low_sample`). 547-548 `COALESCE(tau2,0)`, `ELSE 0.0` shrink factor. 568-574 `COALESCE(...,0.0)`, `-COALESCE(hinge_dev_shrunk,0.0)`. 587-589 `COALESCE(n_post,0)` etc. 591 `CURRENT_TIMESTAMP` makes the table non-deterministic across builds (`fit_timestamp`).
6. Tests: shape (not_null, accepted compound values, ranges: deg_slope within +/-0.25, shift within +/-3, shrink_factor 0..1). Singular `assert_deg_slope_centering`, `assert_cliff_hinge_centering`, `assert_low_sample_cliff_cells_unshifted` check centring and neutrality (maths-ish). None checks the units of the shift or SE realism.

### int_constructor_structural_pace
1. Purpose: per (race, constructor) car pace level relative to the other constructors in the race, via grouped medians (placeholder for the panel regression).
2. Flow: reads `int_lap_fuel_state`, `int_field_pace_curve`, `int_stint_geometry`, `stg_laps`, `int_event_corrections`, `int_track_evolution`. Read by `int_lap_residual_decomposed`, `int_circuit_x_constructor_interaction`, `fct_driver_skill_features`, `fct_ghost_car_pace`.
3. How it works: clean laps (correction_weight 1, not rain, 92-127), `pace_delta_s = lap_time_s - field_pace_smoothed_s` (107), per constructor-race median of pace_delta when more than 10 observations (133-148), then subtract the unweighted mean of constructor medians in that race (158-164, 179-180). SE = SD/sqrt(n) (185); CI = +/-1.96*SE (189-198).
4. Maths check:
   - Line 107: `lap_time_s` is raw (not fuel corrected) but `field_pace_smoothed_s` is built from fuel-corrected, compound-corrected times. So `pace_delta_s` contains this lap's fuel effect and tyre-wear effect. Fuel is common to all constructors at a lap number and cancels in the race-centring. Tyre effect (compound, age) does not cancel for a constructor on a different strategy. `int_lap_residual_decomposed` then also subtracts `compound_component_s` per lap, so a constructor's strategy-driven tyre cost is partly counted twice (once inside the constructor term, once as the compound term). The header (W51/FD3) records the compound dependence but not this overlap. Second-order but real.
   - Lines 185-198: the SE uses `STDDEV_POP/sqrt(n)` which is the SE of a mean of independent laps, applied to a median. Laps in one race are strongly correlated (traffic, tyre age, track evolution), so the interval is much too narrow (it shrinks like 1/sqrt(n) with n of order 50-60). The population (not sample) SD biases low by a small factor.
   - The constructor median pools both drivers' laps, so the "constructor" term includes the average driver skill of the two (header says so). Downstream the residual is therefore teammate-relative, with the driver's own laps inside the baseline (not leave-one-out).
   - If one driver has most of the laps (the other retires early), the median leans on one driver, so the term and the teammate's residual are biased. No per-driver balancing.
   - Lines 138-147: `CASE WHEN COUNT(pace_delta_s) > 10` guards the median, but `HAVING COUNT(*) > 10` counts rows including those with NULL pace_delta (LEFT JOIN to field pace); a constructor can survive HAVING with a NULL median and then NULL structural pace, while the schema test says not_null on `constructor_structural_pace_s`. Whether this occurs depends on the data; could not run the build to check.
   - Race mean (162) is an unweighted mean of however many constructors have data; a missing constructor shifts everyone's centring slightly.
   Verdict: QUESTIONABLE.
5. Fills: 125 and 126 `COALESCE(correction_weight,1.0)`, `COALESCE(rainfall_flag,FALSE)` (unknown = clean and dry). 184-188 `COALESCE(se,0.0)` (SE 0 when stddev NULL). 189-198 the CI `COALESCE` falls back to the point estimate (zero-width interval). 202 `CURRENT_TIMESTAMP`. 201 `NULL AS r_squared_within` (test checks range 0..1 on an all-NULL column, vacuous).
6. Tests: unique id, not_null on pace/se/CI columns, se between 0 and 1.0, CI high >= CI low. Singular `assert_constructor_coefficient_signs`, `assert_constructor_pace_propagates`. Shape plus ordering of the CI; no test on the SE being realistic.

### int_constructor_structural_pace_qualifying
1. Purpose: qualifying counterpart: per (race, constructor) pace relative to the field in the qualifying session.
2. Flow: reads `int_qualifying_push_laps`. Read by `int_lap_residual_decomposed_qualifying`.
3. How it works: push laps only (39), each driver's best lap in each Q segment (73), delta to the segment median of all push laps (49, 64), delta centred on the segment mean of those best laps (83, 94), constructor median over drivers and segments (108), minus mean of constructor medians per race (122, 137).
4. Maths check: structure is reasonable, per-segment centring handles track evolution. Concerns:
   - Lines 110, 139-152: `STDDEV_POP` for n_obs = 1 returns 0 (not NULL), so the COALESCE never fires and a constructor with one best lap gets SE 0 and CI of zero width. With two drivers over up to three segments, n_obs is 1 to 6; the SE is built from tiny samples.
   - The baseline (median of all push laps, 49) differs from the centring set (best laps only, 83). This is corrected by `segment_centre`, so fine.
   - A constructor with drivers in different segments (one eliminated in Q1) mixes segment-normalised deltas; segments differ in field composition, so Q1 deltas are relative to a slower field than Q3.
   Verdict: QUESTIONABLE.
5. Fills: 139-152 same COALESCE pattern as the race model (SE 0.0, CI falls back to point). `HAVING COUNT(*) >= 1` (115) lets n=1 through.
6. Tests: constructor_race_id unique/not_null, pace not_null. Shape only.

### int_corner_drift_from_early_stint
1. Purpose: per (lap, corner) change of the corner residuals relative to the driver's own early-stint level.
2. Flow: reads `int_corner_skill_residuals`, `int_stint_geometry`. Read by `int_lap_corner_drift`.
3. How it works: baseline = mean of the three residuals over valid laps 1-6 of the stint (82-99); drift = residual minus baseline for valid lap 7 onwards, NULL when stint has fewer than 7 valid laps or fewer than 3 baseline observations (116-142).
4. Maths check: arithmetic is right and the baseline window is fixed per stint with drift NULL inside it (114, 119), so no leakage into the window laps themselves. The baseline includes valid lap 1, which may be an out-lap or first lap on cold tyres, so the reference level is biased slow (the other models in this family drop out-laps). Residuals underneath are relative to a trailing-5 field median (not to a fixed reference), so drift mixes tyre effect with the evolution of the field median. The mid-corner residual it differences inherits the unit problem recorded under `int_corner_skill_residuals`.
   Verdict: QUESTIONABLE (inherits upstream; baseline includes lap 1).
5. Fills: none (NULL policy is explicit). Threshold constants 6, 7, 3.
6. Tests: corner_id unique/not_null and a few not_null. Shape only. Inherits `assert_corner_trailing_window_no_forward_reach` indirectly only through the parent.

### int_corner_metrics
1. Purpose: per (driver, lap, corner) braking point, minimum speed, and full-throttle-return point from telemetry.
2. Flow: reads `stg_telemetry`, `dim_corners`. Read by `int_corner_skill_residuals`, `fct_telemetry_deltas`.
3. How it works: join telemetry samples to corner windows on `distance_m BETWEEN start AND end` (66-69). Window = apex - 250 m to apex + 150 m, clipped at the neighbouring apex (dim_corners). `braking_point_m` = first distance with brake on (55), `v_min_kph` = minimum speed in window (57), `throttle_point_m` = first distance at or after apex with throttle exactly 100 (59-64).
4. Maths check:
   - Line 61: `throttle_pct = 100` is an exact equality on a measured percentage channel. If the channel reports 99.x or caps at 100 only sometimes, the exit point is NULL or late. Other models in the same family use `>= 98` or `>= 99.5` (int_lap_telemetry_aggregates 101, 126).
   - Window overlap by design (clipped at neighbour apex): the stretch between two apexes belongs to both corners, so the "first brake sample in window" of corner B can be brake-on from the end of corner A, and `v_min` of corner A's window can be the minimum of corner B's approach. The corner measures are not independent across neighbours.
   - Braking that starts earlier than apex - 250 m is truncated to the window start (cannot be detected), so very long braking zones bias the braking point late.
   - No filter on `source_channel`; the other telemetry model filters to `'car'` to avoid forward-filled duplicates. MIN is insensitive to duplicates so no numeric harm, but a sample count would be.
   Verdict: QUESTIONABLE.
5. Fills: none; NULL when no sample qualifies.
6. Tests: unique combination (year, race, driver, lap, corner), not_null on keys and v_min, relationships. Singular `assert_corner_skill_sign_convention`, `assert_telemetry_deltas_null_when_side_missing`. Shape plus a direction check; no test of units.

### int_corner_skill_residuals
1. Purpose: per (lap, corner) seconds lost versus the trailing-5-lap field median in braking, mid-corner and exit.
2. Flow: reads `int_corner_metrics`, `int_stint_geometry`, `stg_laps`, `stg_sector_times`, macros `trailing_median`, `trailing_observation_count`. Read by `int_corner_drift_from_early_stint`, `int_lap_corner_inputs`, `mart_corner_skill_driver`.
3. How it works: field median of each metric per (race, corner) over all drivers at lap_number - 5 .. - 1 (RANGE frame, 105-152), requires at least 5 observations. `dt_per_dm = 1 / (sector-2 speed trap in m/s)` (94). Braking loss = (field_braking_m - own_braking_m) * dt_per_dm (202-203). Mid-corner = (field_v_min - own_v_min) * 1/(field_v_min in m/s) (212-216). Exit = (own_throttle_m - field_throttle_m) * dt_per_dm (224-225). Total = sum (252-254).
4. Maths check:
   - WRONG, line 212-216 (units). `(field_v_min_kph - own_v_min_kph)` is in km/h and the multiplier `1/(v_ms)` is s/m, so the product is km/h * s/m, which is a dimensionless number equal to `3.6 * dv / v`. It is not seconds and has no distance in it. The time lost over a corner of length L is roughly `L*dv/v^2`. The published value matches that only if L equals the minimum speed in km/h numerically (about 100 m at 100 km/h, 250 m at 250 km/h). No corner length is used, so the number scales with the corner speed rather than the corner geometry. The header and the model call all three terms "seconds lost" and add them (252-254). The sign test `assert_corner_skill_sign_convention` checks direction only, so this passed.
   - Lines 94, 202, 224: braking and exit distances are converted with the sector-2 speed trap of that lap. The trap speed is a top-speed-type number (200-330 km/h) that varies lap to lap with slipstream and DRS. Time cost of a throttle-point shift is distance divided by the car speed at the exit (often 100-200 km/h), so exit time is understated relative to a speed-at-corner conversion, and the conversion is noisy by lap.
   - Lines 255-261: `corner_residual_unexplained_s` is the constant 0.0 whenever all three parts exist (a constant presented as "unexplained residual", always zero by construction).
   - Field median includes the driver's own prior laps and all cars regardless of tyre state or fuel, over a trailing 5-lap window; this lets the baseline move with the evolution of the track within the stint. Aggregating a median over a RANGE frame then `QUALIFY ROW_NUMBER() = 1` per (corner, lap_number) (167-170) is correct because every driver at the same lap number sees the same frame.
   Verdict: WRONG (mid_corner_residual_s units, line 212-216; total_residual inherits); braking/exit QUESTIONABLE (trap-speed conversion).
5. Fills: 227 `corner_unmapped_flag = (sample_n IS NULL OR < 5)`; 255-261 constant 0.0 for unexplained; NULL elsewhere by explicit rule (no COALESCE).
6. Tests: corner_id unique/not_null, flags not_null. Singular `assert_corner_closure`, `assert_corner_inputs_lap_grain_closure`, `assert_corner_skill_sign_convention`, `assert_corner_trailing_window_no_forward_reach`. The closure test passes trivially because the "unexplained" is 0.0 by construction. No unit test.

### int_dirty_air_tax_component
1. Purpose: per-lap dirty-air time cost = declared theta (0.331 s) times the previous lap's dirty-air share, clamped to [0, 5].
2. Flow: reads `int_lap_fuel_state`, `int_field_pace_curve`, `int_compound_cliff_predicted`, `int_stint_geometry`, `int_lap_air_state`, `int_event_corrections`, `int_track_evolution`. Read by `int_lap_residual_decomposed`, `int_driver_isolation_lap_panel`, `fct_stint_features`, `mart_driver_season_summary`, `mart_metric_benchmark`, `mart_race_driver_summary`.
3. How it works: lagged share over the full stint sequence (182-193; LAG default 0.0 for the first lap of a stint). The calibration panel (290-313) is only used to count `calibration_sample_n`; theta is a declared var `theta_air_label_value = 0.331`, fitted outside dbt (2018-2025). `dirty_air_tax_s = clamp(theta*share_lag1, 0, 5)` (348-353). SE = 0.15*tax (358). Confidence = n/(n+500) (363-365). Running total per driver-race, NULL once any lap is unknown (366-375, 391-393).
4. Maths check:
   - The tax is a one-bit treatment times a constant, so it equals 0.331 s or 0 s on every lap (share is 0 or 1, `int_lap_air_state` 243-250). Within a dirty run the cost is the same however close the car is (no gap or time dependence). The comment at 56-57 says per-season theta ranged from +0.418 (2018) to -0.011 (2024); the pooled value is imposed on all seasons. The owner ruled it; flagging only the size of the heterogeneity.
   - Line 358: `dirty_air_tax_se_s = 0.15 * tax` is declared as a convention, not an estimate (header, test `assert_dirty_air_se_is_declared_convention`). Anything reading it as an SE is wrong; it is 0 on clean laps.
   - Lines 363-365: `tax_calibration_confidence = n/(n+500)` with n around 139k is 0.9964 for every lap; it carries no information and is not a confidence in theta.
   - Line 329: `calibration_sample_n` counts rows of the panel including those with NULL lag, so it is not the n of the fit.
   - Line 187: the LAG default 0.0 prices the first lap of every stint (the out-lap after a stop) as clean. The previous lap was in the pit lane, so clean is plausible, but it is a default, not a measurement.
   - The partial residual built at 252-255 (and its INNER JOIN to field pace) is not used to estimate anything here.
   Verdict: QUESTIONABLE (convention SE, decorative confidence, pooled theta across seasons with very different estimates).
5. Fills: 187 `LAG(...,1,0.0)` (first lap of stint share 0). 308-309 `COALESCE(correction_weight,1.0)`, `COALESCE(rainfall_flag,FALSE)` (calibration only). 350-351 clamp lines. 394-396 `COALESCE(flag,FALSE)`. Downstream `int_lap_residual_decomposed` fills 0.0 where this model has no row.
6. Tests: lap_id unique/not_null, tax range 0..5, confidence 0..1, flag not_null. Many singular tests (`assert_dirty_air_fill_only_where_base_unmeasured`, `assert_dirty_air_mean_excludes_unmeasured`, `assert_dirty_air_se_is_declared_convention`, `assert_dirty_air_tax_covers_spine`, `assert_dirty_air_tax_null_only_when_unmeasured`, `assert_theta_panel_has_measured_base`, `assert_prior_season_labels_frozen`, `assert_aero_penalty_negative`, others). Good NULL-policy coverage; none tests the size of theta against the data.

### int_driver_circuit_affinity
1. Purpose: per (driver, physical circuit) shrunk teammate gap, and the deviation from the driver's own average.
2. Flow: reads `int_driver_race_skill_loro`, `circuit_reference` (via `circuit_id_from_name`). No model consumer (app export reads it).
3. How it works: per (driver, circuit) mean and SD of the race teammate gaps (82-93); driver global mean (96-103); shrunk = (n*mean + 5*global_mean)/(n+5) (125-130); posterior variance = 1/(n/sigma2 + 1/sigma_prior^2) with sigma2 the average within-cell variance and sigma_prior the SD of all cell means (109-113, 133-137). Affinity = shrunk - global mean (165-166). CI = +/-1.96*SE.
4. Maths check:
   - Lines 125-137 mix two different priors: the mean weight is a fixed pseudo-count 5, while the variance uses the estimated sigma2 and sigma_prior^2. A consistent normal-normal shrinkage has weight sigma2/sigma_prior^2. The point estimate and the interval therefore do not describe the same posterior.
   - Line 111: `COALESCE(within_cell_stddev_s, 0)` makes every n=1 cell contribute variance 0 to sigma2_residual, biasing sigma2 downward (cells with one race are many). A small sigma2 makes the SE too small.
   - Line 112: sigma_prior is the SD of raw affinity levels across all driver-circuit cells. That includes between-driver level differences and sampling noise; the prior that matters for shrinking toward the driver's own mean is the spread of circuit effects around that mean. This overstates prior variance, so intervals are closer to sigma2/n.
   - The prior mean (global_driver_mean) is computed over the same races that include this cell, a mild double use.
   - The input is a teammate-relative gap, so a driver's affinity at a circuit depends on who the teammate was each year; pooling across teammates is by design.
   - Lines 178-180: `_shrinkage_lower/upper_bound` are the min/max of raw and global mean; the test checks the shrunk value lies between them, which holds for any weight in [0,1].
   Verdict: QUESTIONABLE.
5. Fills: 69 `COALESCE(cm.circuit_id, f.circuit_key)`; 111 `COALESCE(stddev,0)`; 135 `NULLIF(sigma2,0)` and `NULLIF(sigma_prior^2,0)` (NULL SE when zero); 142-143 `NULLIF(n+5,0)`.
6. Tests: unique/not_null, relationships, SE between 0 and 2, confidence 0..1. Singular `assert_affinity_ci_brackets_mean`, `assert_affinity_shrinkage_bounds`. A unit test in `unit_tests_rating_chain.yml` checks the deviation arithmetic on toy data. The CI test checks bracketing, not coverage.

### int_driver_circuit_era_affinity
1. Purpose: same as above but split by era (pre2022, post2022), using a car-removed signal (`driver_skill_field_s`).
2. Flow: reads `int_driver_race_skill_loro`, `circuit_reference`. No model consumer.
3. How it works: as above, per (driver, circuit, era), shrink toward the driver's within-era mean with weight 5, variance components pooled per era (138-145), cells with n_obs < 2 get NULL shrunk values (160-180).
4. Maths check:
   - Same concerns as above: fixed weight 5 versus estimated variances (162-179), zero-filled sigma2 (141), prior SD from all cell means (142).
   - Lines 205-208: `era_label` hard-coded to '2018–2021' and '2022–2024'. `era_key = 'post2022'` is every season from 2022 on, so 2025 rows are labelled "2022–2024". Display error. (2026 is set aside.)
   - Signal `driver_skill_field_s = driver_median_pace_delta - car_fe_s` depends on the Python car fixed effect; if `car_fe_s` is NULL for a race the row is dropped (103), so coverage follows the fit.
   - n_obs >= 2 gating removes the n=1 posterior but sigma2 still uses n=1 cells with zero (141).
   Verdict: QUESTIONABLE.
5. Fills: 91 `COALESCE(cm.circuit_id, f.circuit_key)`; 141 `COALESCE(stddev,0)`; 97 `ELSE 'post2022'`; 205-208 CASE with no ELSE (NULL era_label for any other key).
6. Tests: unique, not_null, era accepted values, SE 0..2. Singular `assert_affinity_ci_brackets_mean`, `assert_affinity_min_races`, `assert_era_affinity_shrinkage_bounds`. Shape and bounds; the label mismatch is not tested.

### int_driver_isolation_lap_pace
1. Purpose: isolated pace p(d,l) per Omega lap with the car term removed, sign flipped to positive = faster.
2. Flow: reads `int_driver_isolation_lap_panel`, `int_constructor_car_fe_isolation`. Read by `int_driver_isolation_lap_values`, `int_driver_isolation_stint_tyre`.
3. How it works: `pace_isolated_gain_s = -(y_s - car_iso_s)` (63); LEFT JOIN on (year, race, constructor).
4. Maths check: sign flip is right (y positive = slower, car_iso on the same scale). Join is on a unique key (constructor_car_fe_isolation id), no fan-out.
   Verdict: SOUND.
5. Fills: 62 `COALESCE(car_term_source,'no_fit_row')` (label only). No numeric fill; missing car term gives NULL gain (explicitly never 0).
6. Tests: lap_id unique/not_null, relationships, accepted values for phases and car_term_source. Shape only. Test T43 is cited in the header (`assert_isolation_sign_convention` sits on the residual model, not here).

### int_driver_isolation_lap_panel
1. Purpose: the clean-lap panel Omega and the field-centred isolated time y_s for the driver-isolation chain.
2. Flow: reads `int_lap_residual_decomposed`, `int_lap_anomaly_flags`, `int_dirty_air_tax_component`, `int_stint_geometry`, `int_lap_air_state`. Read by `int_driver_isolation_lap_pace`.
3. How it works: Omega = valid laps with weight 1, normal or clean_cliff, dry compounds, not in/out lap, known compound component and cliff state, a measured lagged air state (own tax row or "thin cell" repricing at theta*share_lag1 where the tax component has no row, only for races with more than 50% of laps air-measured), at least 8 laps on the same lap number (`isolation_min_field_n`). x = lap_time - compound_component - dirty_air_tax; y = x - median over Omega laps of that lap number. Tyre phase early/mid/cliff from `laps_past_cliff` and valid_lap_in_stint <= 5; recovery overlay after a run of dirty-air laps (looks backward only).
4. Maths check: the header argument holds. Fuel, base, rubber and ambient are functions of (race, lap) only, so subtracting the lap median cancels them exactly; the model does not read them. `field_median` (200-207) is taken over whichever cars passed the filters on that lap, so the reference changes composition from lap to lap (slow cars drop out when in traffic with unmeasured air, in-laps, etc.). y is then relative to a moving field subset, not to a fixed set. This is an accepted design (tested by `assert_isolation_field_centring`). Thin-cell repricing reuses the tax formula (clamp 0..5), and a singular test (`assert_isolation_thin_cell_tax_matches_component`) confirms equality. The recovery rule uses BOOL_AND and strict gap logic.
   Verdict: SOUND (note the moving field subset).
5. Fills: 126 `LAG(...,1,0.0)` first lap of stint treated as clean (documented). Race filter, thresholds are vars. `CASE WHEN rec.lap_id IS NULL THEN FALSE` for is_dirty_air_lap (laps outside the valid-lap recovery table get FALSE). `COALESCE(a.is_rain_lap,FALSE)`.
6. Tests: wide shape tests (not_null on every column, accepted phases). Singular `assert_isolation_base_invariance` (re-derives y from the residual chain, a real maths test), `assert_isolation_field_centring`, `assert_isolation_phase_partition`, `assert_isolation_recovery_share`, `assert_isolation_thin_cell_tax_matches_component`.

### int_driver_isolation_lap_values
1. Purpose: tier-1 per-lap pure skill gain (pace gain plus a declared per-season offset, currently 0).
2. Flow: reads `int_driver_isolation_lap_pace`, `int_driver_isolation_stint_tyre`. Read by `fct_driver_isolation_lap`, `fct_driver_isolation_pair_lap`.
3. How it works: joins the stint line summaries on `stint_id` (one row per stint), pure_skill = pace + macro offset (79-81), flag `tyre_phase = 'cliff'` as extrapolated (84).
4. Maths check: join key is unique per stint (test), no fan-out. The header (3-6) says that on a post-cliff tyre pure skill is "the extrapolated pre-cliff pure line"; the code at 79 simply adds the offset to the measured pace of that lap and only flags `pure_is_extrapolated`. The two statements do not agree, but the flag lets consumers exclude those laps and the header says aggregates do. Note it as documentation mismatch.
   Verdict: SOUND.
5. Fills: macro `driver_isolation_pure_season_offset` has `ELSE 0.0` for any season not in the var map; var is empty, so 0.0 everywhere (explicit CAST).
6. Tests: shape (unique, relationships, accepted values). No maths test directly.

### int_driver_isolation_stint_tyre
1. Purpose: per-stint pace line on early/mid laps, and per-season noise parameters (sigma, lag-1 autocorrelation, effective-sample factor) used for SEs downstream.
2. Flow: reads `int_driver_isolation_lap_pace`. Read by `int_driver_isolation_lap_values`, `fct_driver_isolation_race`, `fct_driver_isolation_stint`.
3. How it works: line laps = early/mid, not recovery, with a car term (65-71). OLS via REGR_SLOPE, REGR_SXX etc (74-87), slope guarded by n >= min stint laps (6) and Sxx > 0 (97-102). Residual sum of squares GREATEST(Syy - Sxy^2/Sxx, 0) (105-118). Season sigma = sqrt(sum SSR / sum(n-2)) (165-174). Season rho1 = pooled lag-1 correlation of line residuals over adjacent laps (153-163). neff factor = (1-rho+)/(1+rho+), rho+ = max(rho,0) (185-190). Slope SE = sigma/sqrt(Sxx*f) (202-204).
4. Maths check: the maths is right. DF is n-2 per stint. The AR(1) variance inflation `(1+rho)/(1-rho)` is the standard approximation for a trend slope. Two limits: pooled rho from OLS residuals of short lines (6+ laps) is biased downward (about -1/n) and is floored at 0, so the floor protects against that but does not correct a true positive rho that is understated; sigma and rho are season-wide, not per driver or circuit; cross-driver correlation in the same race (shared track evolution) is not modelled. These are accepted approximations and well documented.
   Verdict: SOUND.
5. Fills: 92 `COALESCE(n_line_laps,0)`; slope CASE without ELSE (NULL, explicit); `GREATEST(...,0.0)` clip on SSR.
6. Tests: shape (unique stint_id, relationships, not_null counts). No maths test. Header cites a leakage test T48 in ML manifest tests.

### int_driver_race_paired_laps
1. Purpose: one row per (race, driver, lap, teammate) with own lap time minus teammate lap time on the same lap number.
2. Flow: reads `int_lap_fuel_state`, `stg_laps`, `int_event_corrections`, `int_track_evolution`. Read by `int_driver_race_skill_loro`, `mart_race_driver_summary`.
3. How it works: clean panel (weight 1, not rain, lap time present), self-join on race, constructor, lap_number, different driver (88-95).
4. Maths check: join is at (race, constructor, lap_number), at most one row per direction for two-driver cars; for a three-driver car (mid-season swap) rows multiply by the number of teammates, intended. Fuel and field pace cancel because both drivers share the lap number. The clean filter lets in laps where the drivers are on different compounds or tyre ages, in traffic, or after different pit timing. A pit stop staggering effect is not removed, so a driver who stops earlier is on fresher tyres on later laps; the paired median then reads part of strategy as skill. The design was ruled by the owner (FD5 C); noted, not decided.
   Verdict: SOUND.
5. Fills: 76-77 `COALESCE(correction_weight,1.0)`, `COALESCE(rainfall_flag,FALSE)` (unknown as clean/dry).
6. Tests: unique combination, not_null on every column. Singular `assert_mart_race_ci_brackets_rating`. Unit test in `unit_tests_rating_chain.yml` checks lap pairing on toy data. Shape plus one toy maths check.

### int_driver_race_skill_loro
1. Purpose: race-level driver rating: median of lap-by-lap gap to the teammate; also the median pace delta, the leave-one-out car baseline and a field-anchored rating.
2. Flow: reads `int_lap_fuel_state`, `int_field_pace_curve`, `stg_laps`, `int_event_corrections`, `int_track_evolution`, `race_to_track`, `int_constructor_car_fe`, `int_driver_race_paired_laps`. Read by `int_driver_season_ratings`, `int_driver_circuit_affinity`, `int_driver_circuit_era_affinity`, `mart_race_coverage`, `mart_race_driver_summary`.
3. How it works: `driver_skill_loro_s` = median of the paired deltas (194-196, 265). `driver_median_pace_delta_s` = median of lap time minus smoothed field pace (167). `loro_car_baseline_s` = (car sum - own)/(n-1) (228-233). `driver_skill_field_s` = median pace delta - car_fe_s (279). Mean variant (282-283).
4. Maths check: the rating is antisymmetric for two-driver cars by construction (tested). The median of paired deltas is spread-independent. `clean_lap_count` counts every clean lap while `paired_lap_count` counts paired ones; downstream shrinkage uses race counts, not either lap count. A driver with few paired laps (early retirement) has a rating as heavily weighted as a full-distance one: no precision weighting at race level. `driver_skill_field_s` needs the Python car FE; where it is NULL the row has no field rating.
   Verdict: SOUND (with the unweighted-race caveat).
5. Fills: 236 `COALESCE(pa.paired_lap_count,0)`; 155-156 `COALESCE(...)` clean filters (unknown as clean/dry). NULL where no teammate (explicit).
6. Tests: unique/not_null/relationships (shape). Singular `assert_teammate_rating_antisymmetric` (a maths test), `assert_mart_race_teammate_gap`, `assert_mart_race_ci_brackets_rating`. Toy-data unit test of the paired-median arithmetic.

### int_driver_season_ratings
1. Purpose: per (driver, season) shrunk mean of the race-level teammate gaps.
2. Flow: reads `int_driver_race_skill_loro`. Read by `int_era_normalized_driver_rating`.
3. How it works: per (driver, season) mean and SD of race gaps (39-50); season mean over drivers (53-61); variance components pooled across all seasons (64-69); shrunk = (n*mean + 5*season_mean)/(n+5) (83-88); posterior variance via macro (91-95); CI +/-1.96*SE.
4. Maths check: same mixed-prior structure as the affinity models (fixed weight 5 versus estimated variances, lines 83-95). The prior mean is the season mean of driver means, near zero because teammate gaps cancel; that makes the shrink target 0 for everyone. `sigma2_residual` zero-fills n=1 drivers (66). The rating is relative to the teammate only, so drivers in strong teams and weak teams are on different, non-comparable scales (the header says this). Season SD (57) is computed but not used.
   Verdict: QUESTIONABLE.
5. Fills: 66 `COALESCE(stddev,0)`; 98-99 `NULLIF(n+5,0)`; 94 `NULLIF` on variances.
6. Tests: shape plus SE 0..2 and confidence 0..1. Singular `assert_era_rating_shrinkage_bounds`, `assert_rating_confidence`.

### int_era_normalized_driver_rating
1. Purpose: publishes the season rating on one scale across the 2022 boundary; since WI-14b it applies no era offset and keeps the bridge-driver shift only as a diagnostic.
2. Flow: reads `int_driver_season_ratings`. Read by `mart_driver_season_summary`.
3. How it works: bridge drivers (at least 8 races each side, 76-82), their pre-minus-post mean shift (111-119), mean, SD and SE of the shifts (123-131). `era_adjusted_rating = shrunk_residual_s` (154). CI = rating +/- 1.96 * SE (179-181).
4. Maths check: no offset is applied, consistent with a teammate-relative rating that cancels era changes. The diagnostic shift compares shrunk residuals of different car/teammate situations, so it is dominated by teammate change; it is reported, not used. Line 156: `COALESCE(shrunk_residual_se_s, 0)`; if the SE is NULL (n_races 0, or zero variance in the shrinkage macro), the published SE is 0 and the CI collapses to the point estimate, which overstates certainty. The upstream test requires non-NULL SE, so it should not happen now, but nothing here guards it. `era_label` is not here; the era split is via the var 2022.
   Verdict: QUESTIONABLE (SE zero-fill at 156).
5. Fills: 156 `COALESCE(se,0)`; `COALESCE`-free otherwise; `low_anchor_sample_flag = COUNT(*) < 3` (130).
6. Tests: shape plus SE range 0..3. Singular `assert_era_offset_shrinks_gap`, `assert_mart_season_uncertainty_carried`, `assert_rating_top_season_well_supported`.

### int_event_corrections
1. Purpose: per-lap classification of races control events and outliers into a correction class and weight.
2. Flow: reads `stg_laps`, `seed_manual_lap_exceptions`. Read by `int_constructor_structural_pace`, `int_dirty_air_tax_component`, `int_driver_race_paired_laps`, `int_driver_race_skill_loro`, `int_lap_residual_decomposed`, `int_lap_normalized_pace`, `fct_cliff_prediction_features`, `mart_corner_skill_driver`.
3. How it works: fastest lap of the race (31-38); previous/next lap controlled flags via LAG/LEAD over the driver's laps (56-72); yellow = status contains 2 and none of 4-7 (81-83); outlier ratios to the race fastest lap (126-154); manual overrides from a seed by lap or by driver for the whole race (176-205); class and weight CASE (233-273).
4. Maths check:
   - Lines 31-38 and 136-154: the outlier test is `lap_time > 1.40 * race fastest lap` and the soft band is 1.20-1.40. The fastest lap is the minimum over all laps, including laps flagged deleted or generated, and over the whole race. In a race that starts wet and dries, or with a red-flag stop, the denominator is a single fast lap from a different condition, so a large share of valid wet laps become "outliers" (weight 0); in the opposite case a fast stray lap shrinks the threshold. A fixed percentage of one extremal lap is a fragile rule. Rain laps are separately handled downstream but this exclusion happens first.
   - Weights: restart and pre-controlled laps get 0.3, soft outliers 0.6, local yellow 0.6, but every consumer in this group filters on `correction_weight = 1.0` (structural pace, paired laps, dirty air calibration, deg sensitivity), so the 0.3 and 0.6 values never act as weights; they are in effect 0 (exclude). The names suggest a graded weight that is not applied.
   - `is_lap_after_restart` (115-119) is computed but not used in class or weight; it is consumed in the label eligibility downstream.
   - Lap 1 (standing start) and in/out laps are not flagged here; `is_pit_lap` gets weight 0.0 (266-267), so the pit lap is excluded, but whether the out-lap is flagged `is_pit_lap` depends on the staging definition.
   - Manual join: if the seed has both a lap-specific row and a driver-wide row they are coalesced (190-192), lap-specific winning. A duplicated seed row would fan out the lap; there is no uniqueness test on the seed here.
   Verdict: QUESTIONABLE.
5. Fills: 107-108, 115-118, 122 `COALESCE(...,FALSE)` (no neighbouring lap means not controlled); 142 and 153 `ELSE FALSE` (null lap time or null fastest means not outlier); 272 `ELSE 1.0` (anything unclassified is full weight); class `ELSE 'clean'` (251).
6. Tests: unique lap_id, unique combination, relationships. Singular `assert_event_driven_excluded_or_weighted`. Shape plus one consistency check; the outlier threshold behaviour is not tested.

### int_field_pace_curve
1. Purpose: field reference pace per race and lap number (trimmed mean of fuel- and compound-corrected clean-air lap times, 5-lap smoothed with neutralisation boundaries).
2. Flow: reads `int_lap_fuel_state`, `int_stint_geometry`, `int_lap_air_state`, `int_compound_cliff_predicted`. Read by `int_constructor_structural_pace`, `int_dirty_air_tax_component`, `int_driver_race_skill_loro`, `int_lap_residual_decomposed`, `int_lap_normalized_pace`, `int_track_evolution`.
3. How it works: eligible laps: not first valid lap of stint, not last two valid laps of a non-final stint, lap time under 107% of the fastest lap at that lap number, air state free or tow, fuel and compound known (196-238). Value = fuel-corrected time minus expected compound pace (205). Trim: PERCENT_RANK between 0.10 and 0.90 (245-262). Cells with fewer than 5 eligible laps have no base (277, 288). Smoother: centred window of 5 rows inside a green segment (neutralised lap numbers split segments, restart-adjacent laps average only themselves, 303-323).
4. Maths check: the trim, window and boundary rules are consistent and each is tested. Observations:
   - The base is built only from clean-air or tow laps, so it is the pace of cars that are free to run; this is the intended counterfactual reference, and consistent with the dirty-air tax being charged on top.
   - The window is `ROWS ... 2 PRECEDING AND 2 FOLLOWING` over the rows of `trimmed`, which contains only lap numbers with at least one eligible lap. If a lap number has no eligible laps the window spans a gap of more than 5 laps. Probably rare; cannot verify without running.
   - The base subtracts `expected_compound_pace_s`, so the seed curve flows into every residual by design (W51/FD3 note in the structural pace model); and `weight_corrected_lap_time` uses the fuel model.
   - Lines 227: the in-lap rule uses `valid_lap_in_stint < stint_length_valid - 1`.
   Verdict: SOUND.
5. Fills: `COALESCE(...,FALSE)` flags for neutralised laps (96-103). No numeric default: thin cells give NULL on purpose.
6. Tests: unique (year, race, lap), shape. Singular: `assert_field_pace_honest_range`, `assert_field_pace_restart_cells_own_mean`, `assert_field_pace_smoothing_respects_boundaries`, `assert_label_window_has_measured_base`, `assert_pace_delta_flat_by_race_fifth`, `assert_residual_skips_thin_field_cells`, track evolution monotone tests. Good maths coverage.

### int_lap_air_state
1. Purpose: air-state classification per lap (free, tow, drs-train, dirty), dirty-air share, time in dirty air, thermal loads.
2. Flow: reads `int_stint_geometry`, `bronze_f1.raw_telemetry` (source directly), `stg_laps`. Read by `int_field_pace_curve`, `int_dirty_air_tax_component`, `int_driver_isolation_lap_panel`, `int_lap_normalized_pace`, `int_pit_strategy_value`, `int_sector_residual_decomposed`, `fct_cliff_prediction_features`, `fct_stint_features`, `mart_race_coverage`.
3. How it works: gap in seconds = FastF1 distance-to-car-ahead divided by the follower's own speed in m/s (99-102). Sector proxy = thirds of relative distance (104-108). Per (lap, third): median gap, DRS flag (157-162). State: gap over 2.0 free; third 2 under 1.5 dirty; thirds 1/3 under 1.0 DRS-train or tow, else free (177-186). Lap share = 1 if the middle third is dirty (242-250). Tow benefit = -0.15 per tow third (253). Intensity = 1/max(gap,0.3) in the middle third (188-192). Time in dirty air = sum of sample elapsed time with gap under 1.5 s (141-143). Unmeasured laps (no gap and not the leader) are NULL (290-291, 340-367). Thermal loads are exponentially weighted sums of intensity over 5 and 10 laps (383-404).
4. Maths check:
   - Line 101: converting distance to time with the follower's speed assumes the car ahead goes at the same speed; `int_lap_proximity` header calls this assumption exactly false when catching a slower car. Gap in seconds is understated or overstated depending on closing speed. Direct crossing times in proximity avoid it.
   - Lines 104-108: sectors are thirds of relative distance, an approximation by the author's own comment, not the real sector boundaries. The dirty-air bit reads only the middle third, so a car in traffic for the other two thirds counts as clean; and the share is 0 or 1 (a single bit per lap) which is the treatment downstream.
   - Lines 141-143: `dt_s` is the raw difference between consecutive sample times with no clamp. A telemetry dropout adds its entire length to `time_in_dirty_air_s` if the sample after it has a short gap (the physical-ahead model clamps dt at 1.0 s for this reason). The schema test caps the column at 900 s, not at lap length.
   - Line 253: tow benefit is a constant -0.15 s per tow third (not fitted); it is output but `int_lap_normalized_pace` records that it makes fits worse and does not apply it.
   - Line 190: intensity floor 0.3 s caps intensity at 3.33.
   - Thermal loads: weights 0.600, 0.240, 0.096, 0.038, 0.015 (decay 0.4, sum 0.989) and 0.25*0.75^k (sum to 10 terms 0.944) are unnormalised truncated geometric sums; fine as features but not "loads" in any units. LAG defaults 0.0 at stint start (385-403) and rounding to 4 dp.
   - Line 356 `COALESCE(air_state_dominant,'free_air')` applies to measured laps only (leader laps or laps with some gap), so it labels the leader's lap free_air, which is justified; but an SC lap keeps its air_state while its share, intensity and time are forced to 0.0 (342, 351, 365), so state and numbers disagree on neutralised laps.
   Verdict: QUESTIONABLE.
5. Fills: 343 `COALESCE(share,0.0)`, 347 `COALESCE(tow,0.0)`, 352 `COALESCE(intensity,0.0)`, 356 `COALESCE(state,'free_air')`, 366 `COALESCE(time_in_dirty_air_s,0.0)` (measured laps with no dirty samples read as 0 s). 342, 351, 365 `WHEN is_neutralised_lap THEN 0.0`. 385-403 LAG default 0.0. 290 `COALESCE(position,0) != 1` (NULL position is not the leader, so unmeasured). 190 `GREATEST(gap,0.3)`.
6. Tests: lap_id unique/not_null, s2 gap >= 0, time_in_dirty_air in 0..900. Singular `assert_air_state_unmeasured_is_null`, `assert_dirty_air_share_monotone`, `assert_stint_boundary_integrity`, and others. The monotone test checks the monotonicity of the share in the gap, a real maths property; nothing tests the speed-based conversion.

### int_lap_anomaly_flags
1. Purpose: classify each lap as normal, mistake, clean_cliff, event_driven or conditions; flag usable laps; mark in and out laps.
2. Flow: reads `int_lap_residual_decomposed`. Read by `int_driver_isolation_lap_panel`, `int_lap_telemetry_aggregates`, `fct_cliff_prediction_features`, `fct_driver_skill_features`, `fct_stint_features`.
3. How it works: per-driver-race mean and SD (54-65, z-score only for traceability); trailing 7 laps by lap_number (70-95): median of residual, then MAD of the window (98-116), floored at 0.10 s; `mad_score = |res - median|/MAD` (138-144); class rule 220-244: event or exclude -> event_driven; rain -> conditions; positive mad_score > 3 with cliff passed -> clean_cliff; positive spike without cliff -> mistake; else normal.
4. Maths check:
   - Lines 103-106, 236, 242: `mad_score > 3.0` uses the raw MAD, not the normal-consistent MAD (1.4826 x). A raw-MAD threshold of 3 is about 2.0 sigma for normal noise (3/1.4826), so roughly 2% of clean laps in each tail pass for a normal distribution, and only the upper side is used. The name "3" reads as a 3-sigma rule.
   - Lines 70-95: window is `lap_number BETWEEN lap-6 AND lap` over the whole race (not the stint), so it spans pit stops and tyre changes, includes the lap being scored, and includes neutralised laps. A step change after a stop contaminates 3-4 laps of baseline. The median of 7 including the lap itself dampens the score of an isolated spike by pulling the median only slightly, but a persistent cliff shifts the median within 4 laps and the cliff stops looking anomalous.
   - Line 244 `ELSE 'normal'` and 262-264 `ELSE TRUE`: a lap whose residual is NULL (no field base, no compound cost) has a NULL `mad_score`, so the comparisons are false and it is classed 'normal' and `usable_for_modelling = TRUE`. NULL is not "normal".
   - Only positive deviations are anomalies; fast outliers (a deleted-time lap or timing glitch) are never flagged.
   - Lines 168-172: `is_out_lap = lap_in_stint = 1` also flags lap 1 of the race (standing start) and `is_in_lap` flags the last lap of the final stint (the chequered lap), which is not a pit in-lap. Documented as exclusion by effect, but misnamed.
   - `cliff_candidate_flag` feeds an ML label and depends on `driver_skill_residual_s`, which depends on the interaction/structural terms. Circularity with the cliff seed is a leakage concern outside this audit.
   Verdict: QUESTIONABLE.
5. Fills: 131 `ELSE 0.0` z-score when SD is 0 or NULL (a driver with a single clean lap gets z = 0); 143 `ELSE 0.0` mad_score; 216 `COALESCE(rainfall_flag,FALSE)`; 105 floor 0.10.
6. Tests: unique id, relationships, not_null. Singular `assert_mad_floor` (checks the floor). Shape plus one numeric check; the threshold semantics are not tested.

### int_lap_corner_drift
1. Purpose: lap-grain summary of corner drift (mean, SD, max per phase, coverage).
2. Flow: reads `int_corner_drift_from_early_stint`. Read by `fct_cliff_prediction_features`.
3. How it works: group by lap_id, AVG, STDDEV_SAMP, MAX of the three drifts, counts and coverage (36-83).
4. Maths check: aggregation correct. `STDDEV_SAMP` is NULL for a lap with one drift, correct. The mean treats corners equally regardless of length. Inherits the unit issue of the mid-corner term and the lap-1 baseline.
   Verdict: SOUND (as an aggregator; inherits upstream issues).
5. Fills: none.
6. Tests: lap_id unique/not_null and not_null counts. Shape only.

### int_lap_corner_inputs
1. Purpose: lap-grain summary of corner residual inputs (mean, SD, max, coverage).
2. Flow: reads `int_corner_skill_residuals`. Read by `fct_cliff_prediction_features`.
3. How it works: group by lap, counts and aggregates (73-114).
4. Maths check: correct aggregation. `corner_input_coverage` divides by `NULLIF(COUNT(*),0)`. Inherits the mid-corner unit problem (mean of a mislabelled number is still a mislabelled number).
   Verdict: SOUND (as an aggregator; inherits upstream).
5. Fills: none.
6. Tests: lap_id unique/not_null, counts not_null; singular `assert_corner_inputs_lap_grain_closure`. Shape and a closure check.

### int_lap_fuel_state
1. Purpose: fuel mass per lap and fuel-corrected lap time.
2. Flow: reads `int_stint_geometry`, `stg_laps`, `race_to_track`, `dim_circuits`, `race_scheduled_laps`, macro `fuel_regulatory_max_kg`. Read by seven intermediate models and three marts (see section 1).
3. How it works: initial fuel = regulatory maximum (105 kg in 2018, 110 kg from 2019), burn rate = initial / scheduled laps (69-71); `fuel_mass_kg = max(initial - rate*(lap_number-1), 0)` (105-108); penalty = mass * `weight_penalty_factor` per circuit (125); corrected time = lap time - penalty (126-127). Only valid laps (48).
4. Maths check:
   - Fuel at lap start with a linear burn from the full limit is a modelling assumption: every car starts at the regulatory maximum and burns evenly over the scheduled distance, with no per-car fuel saving, no lift-and-coast, no SC burn reduction. It is the same for every driver, so for within-lap comparisons it cancels; it matters for absolute offsets and for degradation (fuel burn and tyre wear are both linear in lap number, collinear unless stints differ).
   - Lines 130-131: `fuel_delta_vs_expected = (initial - mass) - rate*lap_number`. With `mass = initial - rate*(lap-1)` this is `rate*(lap-1) - rate*lap = -rate` for every lap (an off-by-one between the two expressions). The column is a constant, not a deviation. No model or app code reads it (grep), so no number depends on it, but it is wrong if anyone does.
   - The clamp `GREATEST(...,0)` (105-108) applies only for laps beyond the scheduled distance.
   - INNER joins (91-96) are guarded by singular tests.
   Verdict: QUESTIONABLE (assumption set; one dead but wrong column).
5. Fills: 105-108 `GREATEST(..., 0.0)`; `NULLIF(scheduled_laps,0)` (71).
6. Tests: lap_id unique/not_null, fuel parameters not_null. Singular `assert_fuel_curve_monotonicity`, `assert_fuel_load_matches_scheduled_distance`, `assert_push_residual_fuel_neutral`, `assert_race_to_track_covers_all_races`, `assert_stint_boundary_integrity`, `assert_field_base_drift_tracks_observed`, `assert_pace_delta_flat_by_race_fifth`. Reasonable maths coverage of the fuel curve; none tests `fuel_delta_vs_expected`.

### int_lap_fuel_state_qualifying
1. Purpose: constant fuel placeholder for qualifying laps so the residual identity closes.
2. Flow: reads `stg_laps_qualifying`. Read by `int_lap_residual_decomposed_qualifying`.
3. How it works: `fuel_mass_kg = 12.0`, `fuel_component_s = 12.0 * 0.035` (40-41).
4. Maths check: two hard-coded literals (12 kg, 0.035 s/kg = 0.42 s), not taken from `dim_circuits.weight_penalty_factor` which the race model uses, and not fitted. It is a per-lap constant, so it only shifts the level of the qualifying residual by -0.42 s for every lap; it does not move rank order. It appears in the residual as if measured.
   Verdict: QUESTIONABLE (invented constants).
5. Fills: both columns are constants (lines 40, 41).
6. Tests: unique combination, lap_id unique/not_null, relationships. Shape only.

### int_lap_normalized_pace
1. Purpose: lap time with a dirty-air penalty (theta_time * seconds in dirty air) removed, for an offline solver.
2. Flow: reads `int_lap_air_state`, `stg_laps`, `int_lap_fuel_state`, `int_field_pace_curve`, `int_event_corrections`, `int_track_evolution`. No consumer.
3. How it works: theta_time = COVAR_POP(partial_residual, time_in_dirty_air) / VAR_POP(time_in_dirty_air) over clean valid laps (153-163); penalty = clamp(theta*time, 0, 5) (189-194); normalized = lap time - penalty (217).
4. Maths check:
   - The pooled slope has the selection problem the header describes for the step term: slower cars spend more time in traffic, so a cross-sectional slope carries car pace deficit. The header argues only against the step, and keeps the pooled slope. The partial residual (126-127) subtracts fuel but not compound/tyre cost, so tyre age (correlated with traffic within a stint) also leaks into the slope.
   - The panel is not capped by a season window (unlike the dirty-air tax component's `theta_air_fit_season_max`), so adding a season moves theta and relabels history.
   - Line 158: `COALESCE(...,0.004)` falls back to a literal when the covariance is undefined.
   - `clamp_or_null` returns NULL when exposure is NULL, so normalized pace is NULL for unmeasured laps (correct).
   Verdict: QUESTIONABLE (leaf, low impact).
5. Fills: 158 literal 0.004; clamp bounds 0 and 5.
6. Tests: lap_id unique/not_null, normalized pace between 0 and 210, penalty 0..5 and not_null. Shape and range only.

### int_lap_physical_ahead (Python model)
1. Purpose: measurement of how close each car is to the physical car ahead, from X/Y positions only, one row per lap; explicitly not a time-loss or a cause.
2. Flow: reads `int_stint_geometry` (spine), `bronze_f1.raw_telemetry` (Source = 'pos'), `bronze_f1.raw_laps`. Read by `int_traffic_exposure_driver_race`.
3. How it works: per race, build a reference polyline from the fastest clean lap (136-147), project every sample on it (149-154), unwrap progress per car (155-160), flag parked samples (161-166), interpolate each other car to the follower sample time with a bracket under 1 s (173-196), pick the nearest car ahead within 300 m (194-198), classify the sample (201-210), gap in seconds = time for the follower to reach the point where the car ahead is now, read from its own progress (214-221, `_follower_time_gap`). Per lap reduction with a 5% unknown tolerance and 4-sample class thresholds (249-293).
4. Maths check: units are consistent (polyline coordinates in 1/10 m; `f` divided by 10 gives metres, 192; target multiplied back by 10, 217). The time gap is a crossing time, not a distance over speed, so it needs no equal-speed assumption. `dt_s` is clamped to 1 s (238) so dropouts cannot dominate. Class precedence puts unknown above clear (never clear air on missing data, 210). Known limits are documented (96-99% agreement with proximity, identity flips 0.2-0.8%). Points to note:
   - The 10 m side-by-side and 15 m overlap thresholds are fixed. The 15 m off-track and 5 m in 10 s parked thresholds are fixed constants.
   - Line 75: `OPEN_S = 120.0` duplicates the dbt var `proximity_pit_window_open_s`; the two can drift.
   - Line 220: gaps over 30 s or negative become NaN. A same-lap sample with a car ahead but NaN gap is classed same_lap with no gap, and `close` is false, so it counts as not close; consistent with the intent.
   - `is_within_1s_of_car_ahead` is FALSE for a valid lap with no car within 300 m (clear) and for a lap whose nearest gap is over 30 s; the header states this.
   - The ordering of rows `sort_values(['driver_id','session_time_s'])` assumes `session_time_s` is monotone within a driver; ties are handled by a stable sort.
   - Cannot check performance or data-dependent facts (reference lap availability) without running.
   Verdict: SOUND.
5. Fills: 238 `.fillna(0.0)` for the last sample's dt (the final sample of a driver has dt 0, no effect on sums). 343 `fillna(0)` on counts for laps with no data (counts, with validity forced to 'unknown', 335). `no_data` laps are 'unknown', never clear.
6. Tests: unique (race, driver, lap), validity accepted values, gap range 0..30. Singular `assert_physical_ahead_agrees_with_proximity`, `assert_physical_ahead_classes_exhaustive`, `assert_physical_ahead_flip_rate`, `assert_physical_ahead_lapped_share`, `assert_physical_ahead_unknown_never_clear_air`, `assert_traffic_exposure_lap_partition`. Good: agreement and invariants are tested.

### int_lap_proximity
1. Purpose: per-lap true pairwise gap to the car ahead and behind from crossing times of 100 track bins (position channel).
2. Flow: reads `stg_telemetry_position`, `stg_results`, `stg_pits`, `int_stint_geometry`. Read by `fct_cliff_prediction_features`.
3. How it works: bin = floor(relative_distance*100) (46); crossing time = first sample time in the bin (72); drop pit-window crossings (139-150); in each (race, bin) order crossings by time, the previous crossing is the car ahead and the difference is the gap (174-227); per lap scalars: min and median gap, share of bins within 1/2/3 s, time within 1 s (sum of bin durations clamped at 5 s), train share, identity stability, comparison to FastF1's driver ahead (256-331, 426-508).
4. Maths check:
   - Line 46: `relative_distance` is FastF1's per-lap normalised distance (fraction of the lap's own integrated distance). Two drivers' bin k are therefore not exactly the same physical point; per-lap distance scatter of tens of metres is a gap error of 0.1-0.2 s at 250 km/h. The header's "same clock at the same point in space" is exact only if relative_distance was identical across laps. For a 1 s threshold this is not negligible. Not verifiable without the data.
   - Lines 110-114: bin duration defaults to 1.0 s for each driver's last crossing, and the lead is across the lap rollover with a tie-break; clamped at 5 s. Fine.
   - Lines 278-283: share within N s is `AVG(CASE WHEN gap < N THEN 1 ELSE 0)` over all bins, so a bin with NULL gap (first car through a bin, or a same-driver neighbour) counts as not-close: correct for a leader, but it also silently counts bins with no valid neighbour (after the pit filter removes the car ahead) as clean.
   - Line 239-243: `ahead_own_gap_s` for train detection needs the second car ahead to differ from the first.
   - Lines 451-486: neutralised laps get 0.0 for every share (a constant), unmeasured laps NULL. `COALESCE(...,0.0)` is applied to measured laps only.
   - Includes lapped cars as "ahead on track" by design.
   Verdict: QUESTIONABLE (bin identity across laps; 2018 Australia and Bahrain have no position data and are NULL).
5. Fills: 112 `COALESCE(LEAD - time, 1.0)` (last crossing duration), 455-486 `COALESCE(share, 0.0)` for measured laps and `0.0` on neutralised laps; 131 `COALESCE(pit_out, pit_in + 120)`.
6. Tests: lap_id unique/not_null, bin count 1..100, gap 0..300, share ranges, `share_lap_within_1s not_null` (note: contradicts the NULL-for-unmeasured policy if it fires). Singular `assert_proximity_agrees_with_blue_flags`, `assert_proximity_excludes_pit_lane`, `assert_proximity_train_subset_of_within1s`, `assert_proximity_crossing_total_order` (mentioned in header), `assert_physical_ahead_agrees_with_proximity`. Includes cross-source agreement; the bin-identity error is not tested.

### int_lap_residual_decomposed
1. Purpose: lap-grain residual identity: pace delta to the field base split into fuel, compound, constructor, dirty-air tax and a driver-skill residual.
2. Flow: reads `int_field_pace_curve`, `int_lap_fuel_state`, `int_stint_geometry`, `stg_laps`, `int_compound_cliff_predicted`, `int_track_evolution`, `int_constructor_structural_pace`, `int_dirty_air_tax_component`, `int_event_corrections`. Read by ten models (section 1).
3. How it works: `pace_delta_s = lap_time - base` (344); `driver_skill_residual_s = pace_delta - fuel - compound - constructor - dirty_air_tax` (354-360). Rubber and ambient are informational (in the base).
4. Maths check: the identity closes algebraically and is tested. Points:
   - The constructor term was estimated from lap times that were not fuel- or tyre-corrected (see structural pace), so a constructor's strategy-dependent tyre cost is partly in both `constructor_component_s` and `compound_component_s`.
   - The constructor term is the median over both teammates' laps including this driver's own, so the residual is teammate-relative, not an absolute skill; the comment calls it "driver_skill".
   - Constructor fill (line around 229 `COALESCE(cs.constructor_structural_pace_s, 0.0)`): laps in races or constructors with no structural row (all-wet races, thin constructors) carry the car level in the residual. Documented, flagged by `constructor_pace_is_filled`.
   - Dirty-air fill: `CASE WHEN da.lap_id IS NULL THEN 0.0` for tax, SE and cumulative tax. The test confirms the zeros fall only where the base is unmeasured, so the residual is unaffected, but lap-grain readers see 0.0 as clean air.
   - `correction_weight` is carried, not applied here.
   Verdict: QUESTIONABLE.
5. Fills: constructor_component_s `COALESCE(...,0.0)` (flagged), dirty_air_tax_s / se / cumulative `0.0` where no row, `dirty_air_tax_confidence = COALESCE(...,0.0)`, `dirtiest_air_lap_in_race_flag = COALESCE(...,FALSE)`, `is_lap_after_restart = COALESCE(...,FALSE)`. Rubber/ambient are NULL when unmeasured (TX-30 e).
6. Tests: not_null on the key components, tax range 0..5, fill flag consistency. Singular: `assert_residual_decomposition_identity`, `assert_lap_7term_identity`, `assert_example_identity_closure`, `assert_field_base_component_neutral`, `assert_residual_components_not_in_base`, `assert_pace_delta_requires_field_base`, `assert_residual_skips_thin_field_cells`, `assert_dirty_air_tax_covers_spine`, `assert_sector_aggregates_to_lap` and others. Strong identity coverage; the double-count of tyre cost in the constructor term is not tested.

### int_lap_residual_decomposed_qualifying
1. Purpose: residual identity for qualifying push laps.
2. Flow: reads `int_qualifying_push_laps`, `stg_laps_qualifying`, `int_lap_fuel_state_qualifying`, `int_constructor_structural_pace_qualifying`, `race_to_track`, `dim_compounds_season`. Read by `int_qualifying_decomposed`.
3. How it works: base = segment median of push laps (73); fuel = constant; wear = gradient * tyre_life (131-132); constructor from the qualifying coefficient; residual = lap - base - fuel - compound - constructor (174-180).
4. Maths check: many silent zero fills.
   - Lines 162, 174: `COALESCE(base_track_pace_s, lap_time_s)` makes the pace delta and residual zero for a lap without a segment base, an invented zero residual.
   - Lines 122-123: constructor `COALESCE(...,0.0)`; 131 `COALESCE(compound_wear_gradient,0.0)*tyre_life` (a lap with no seed cell gets no tyre cost; a NULL tyre_life makes the product NULL and the sum COALESCEs it to 0).
   - Lines 115-116: rubber and ambient hard-coded 0.0 (qualifying has no track evolution term), dirty air 0.0 constant (134-135), fuel 0.42 s constant (from `int_lap_fuel_state_qualifying`).
   - Wear uses `gradient * tyre_life` with no cliff or grip, fine for push laps.
   - The constructor coefficient is derived from each driver's best lap, but the residual is computed for every push lap, so the sum of residuals is biased negative on best laps.
   Verdict: QUESTIONABLE.
5. Fills: lines 115, 116, 122, 124, 131, 134, 135, 162-180 as above.
6. Tests: lap_id unique/not_null, residual not_null (can never fail because of the COALESCEs), segment not_null. Shape only; the not_null on the residual is satisfied by the zero fill.

### int_lap_residual_stint_detrend
1. Purpose: per-stint linear drift of the residual over pre-cliff laps, to detrend the label.
2. Flow: reads `int_lap_residual_decomposed`. Read by `fct_cliff_prediction_features`.
3. How it works: for stints with at least 3 non-NULL pre-cliff residuals, REGR_SLOPE(residual, lap_in_stint), else 0.0 (24-34).
4. Maths check: the fit uses every pre-cliff lap with a residual, with no correction_weight filter, so restart, yellow, out-lap, and traffic laps are in the regression and an out-lap residual at lap_in_stint = 1 (slow) dominates the slope of a short stint. Slope is against `lap_in_stint` (which counts invalid laps), not tyre age. The fallback 0.0 mixes "no data" with "measured zero slope", and an all-post-cliff stint has no row at all (the consumer must handle the missing row). Stints with fewer than 3 laps have no detrending.
   Verdict: QUESTIONABLE.
5. Fills: 27-30 `ELSE 0.0` and `COALESCE(slope,0.0)`.
6. Tests: stint_id unique/not_null, drift not_null. Shape. Singular `assert_cliff_class_horizon_partition` references it.

### int_lap_telemetry_aggregates
1. Purpose: per-lap powertrain aggregates and telemetry-cliff drift features versus the stint's early baseline.
2. Flow: reads `stg_telemetry` (source_channel = 'car'), `int_lap_anomaly_flags`. Read by `fct_cliff_prediction_features`, `fct_driver_isolation_lap`.
3. How it works: per-sample LAG/LEAD derivatives (51-79), flags (82-149), per-lap aggregates (152-181), baseline = stint average over laps 2-5 excluding in and out laps (230-255), drift = baseline minus lap value (276-280).
4. Maths check:
   - Lines 233-253: the baseline is a stint-wide window average, so for laps 2-5 the baseline includes laps after the one being scored (laps 3-5 for lap 2), and each baseline lap is compared to a baseline that contains itself. For laps 6 onward it is a fixed reference, fine, but the early laps leak future information and have drift pulled toward 0.
   - Baseline laps are not filtered for SC/VSC or incidents, so one neutralised lap in laps 2-5 corrupts the stint baseline.
   - Line 170: `lap_corner_min_speed_kph` = AVG of every local speed minimum below 75% of the lap's max. The set of minima changes with data noise (plateaus count several times because `<=` is used on both sides, 108-109) and with the number of slow corners the sample cadence resolves, so the mean level is not a stable corner-speed measure; the drift can come from changes in which minima are detected.
   - Line 171: `lap_brake_onset_m` = AVG of the distances of all brake onsets in the lap. If one brake event is missed or added the mean moves by hundreds of metres. `braking_point_drift_m` is a difference of two such means, not a per-corner braking point change.
   - Line 136 wheelspin proxy is full throttle with no speed gain at under 85% of max speed; this also happens uphill or at constant speed; called a proxy.
   - Line 97: short upshift tests `prev_rpm < 0.92 * lap_max_rpm`.
   Verdict: QUESTIONABLE.
5. Fills: 118 `COALESCE(prev_brake,FALSE)` (first sample not a brake onset); counts via CASE with no ELSE give NULL ratios (166, 173). `ELSE 0`/`0.0` flags.
6. Tests: lap_id unique/not_null, stint_id not_null, 0..1 ranges on four shares. Shape and range only.

### int_lap_thermal_proxy
1. Purpose: push-intensity proxy (stint baseline pace minus current lap, fuel-corrected) and two exponentially weighted loads.
2. Flow: reads `int_stint_geometry`, `stg_laps`, `int_lap_fuel_state`, macros `trailing_median`, `trailing_observation_count`. Read by `int_tyre_surface_vs_bulk_decoupling`, `fct_cliff_prediction_features`, `fct_stint_features`.
3. How it works: baseline = expanding median of the stint's valid fuel-corrected lap times strictly before the lap (110-113); `push_residual = baseline - lap` (127); surface load = sum over lags 0-4 of max(residual,0) with weights 0.717, 0.514, 0.369, 0.264 (e^{-k/3}); bulk load over lags 0-7 with 0.819...0.247 (e^{-k/5}) (144-163).
4. Maths check: weights match the stated time constants (e^{-1/3} = 0.717, e^{-1/5} = 0.819). Baseline is strictly causal. Residual is computed on fuel-corrected time so burn-off does not read as push. Remaining design points: the baseline lap time includes tyre degradation, so a rising baseline absorbs wear; the clipping `GREATEST(...,0)` discards slow laps; a lap with NULL prior residual contributes 0 (documented); `min_observations=1` means the baseline for lap 2 is a single lap.
   Verdict: SOUND.
5. Fills: 146-162 `COALESCE(LAG(push_residual,k),0)` (missing or invalid prior laps contribute 0 load), rounding to 4 dp.
6. Tests: lap_id unique/not_null, observations n not_null >= 0. Singular `assert_no_future_leakage` (causality, a maths property), `assert_push_residual_fuel_neutral`, `assert_stint_boundary_integrity`. Good.

---

## 3. Verdict table

| Model | Verdict |
|---|---|
| int_cell_power_law_fit | SOUND |
| int_circuit_x_constructor_interaction | QUESTIONABLE |
| int_compound_cliff_predicted | QUESTIONABLE |
| int_constructor_car_fe | SOUND (pass-through) |
| int_constructor_car_fe_isolation | SOUND (pass-through) |
| int_constructor_deg_sensitivity | WRONG (onset shift units); slope half QUESTIONABLE |
| int_constructor_structural_pace | QUESTIONABLE |
| int_constructor_structural_pace_qualifying | QUESTIONABLE |
| int_corner_drift_from_early_stint | QUESTIONABLE |
| int_corner_metrics | QUESTIONABLE |
| int_corner_skill_residuals | WRONG (mid-corner units) |
| int_dirty_air_tax_component | QUESTIONABLE |
| int_driver_circuit_affinity | QUESTIONABLE |
| int_driver_circuit_era_affinity | QUESTIONABLE |
| int_driver_isolation_lap_pace | SOUND |
| int_driver_isolation_lap_panel | SOUND |
| int_driver_isolation_lap_values | SOUND |
| int_driver_isolation_stint_tyre | SOUND |
| int_driver_race_paired_laps | SOUND |
| int_driver_race_skill_loro | SOUND |
| int_driver_season_ratings | QUESTIONABLE |
| int_era_normalized_driver_rating | QUESTIONABLE |
| int_event_corrections | QUESTIONABLE |
| int_field_pace_curve | SOUND |
| int_lap_air_state | QUESTIONABLE |
| int_lap_anomaly_flags | QUESTIONABLE |
| int_lap_corner_drift | SOUND (aggregator) |
| int_lap_corner_inputs | SOUND (aggregator) |
| int_lap_fuel_state | QUESTIONABLE |
| int_lap_fuel_state_qualifying | QUESTIONABLE |
| int_lap_normalized_pace | QUESTIONABLE |
| int_lap_physical_ahead (py) | SOUND |
| int_lap_proximity | QUESTIONABLE |
| int_lap_residual_decomposed | QUESTIONABLE |
| int_lap_residual_decomposed_qualifying | QUESTIONABLE |
| int_lap_residual_stint_detrend | QUESTIONABLE |
| int_lap_telemetry_aggregates | QUESTIONABLE |
| int_lap_thermal_proxy | SOUND |

Counts over 38 files: SOUND 14, QUESTIONABLE 22, WRONG 2 (`int_corner_skill_residuals`, `int_constructor_deg_sensitivity`).

---

## 4. Findings, ranked

### WRONG

1. `int_corner_skill_residuals.sql:212-216` mid_corner_residual_s is not seconds. `(field_v_min_kph - own_v_min_kph) * 1/(field_v_min_kph*1000/3600)` is km/h divided by m/s: a dimensionless 3.6*dv/v with no corner length. It is summed with two true-seconds terms at 252-254 and presented as "seconds lost". Implied corner length equals the minimum speed in km/h numerically. Flows to `int_corner_drift_from_early_stint`, `int_lap_corner_drift`, `int_lap_corner_inputs`, `fct_cliff_prediction_features`, `mart_corner_skill_driver`.
2. `int_constructor_deg_sensitivity.sql:468, 568-579, 584` cliff_onset_shift_laps divides seconds by a step in seconds (`severity_used`, a fitted level shift in seconds floored at 0.30) where a rate (severity / 2.5 s per lap) is needed; result is unitless but published as laps, and the output column is mislabelled `cliff_severity_used_s_per_lap`. The owner's own comment at 437-463 records this as a known defect (08m). The hinge regressor is linear and unbounded while the fitted cliff curve saturates after 2.5 laps. Feeds `fct_ghost_car_pace`.

### QUESTIONABLE (most impactful first)

3. `int_compound_cliff_predicted.sql:136, 141, 254` laps with no seed cell (unknown compound) get `laps_past_cliff = 0` and wear 0.0 through `COALESCE(...,999.0)`, `COALESCE(gradient,0.0)`; the pace term is 0.005*delta (232), a free tyre, while the header (157-172) says these laps are NULL. Also `:232` 0.005 s per degree is a literal and `:65-76` weather is one latest reading across drivers per lap number.
4. `int_constructor_structural_pace.sql:107, 185-198` pace delta is not fuel- or compound-neutral (raw lap time minus a corrected base), so tyre/strategy cost sits in both the constructor term and `compound_component_s`; the SE is `STDDEV_POP/sqrt(n)` of laps (assumes independence, applied to a median), too narrow, and falls back to SE 0 and a zero-width CI.
5. `int_lap_anomaly_flags.sql:236, 242, 103-106` `mad_score > 3.0` uses an unscaled MAD (about 2 sigma); `:70-95` window spans stints and includes the lap itself; `:244, 262-264` NULL-residual laps are classed 'normal' and usable.
6. `int_lap_air_state.sql:101, 104-108, 141-143, 243-250` gap in seconds uses the follower's speed; sectors are thirds of relative distance; dirty-air is one bit from the middle third; `dt_s` is unclamped so telemetry dropouts inflate `time_in_dirty_air_s` (physical_ahead clamps at 1 s).
7. `int_lap_proximity.sql:46` bins by per-lap `relative_distance`, so bin k is not the same physical point for two drivers or two laps; a 1 s threshold can be moved by tens of metres of scatter. `:112` last-crossing duration defaults to 1.0 s.
8. `int_lap_telemetry_aggregates.sql:233-253, 170-171` baseline over laps 2-5 includes the scored lap and later laps (leakage for early laps) and SC laps; `lap_brake_onset_m` and `lap_corner_min_speed_kph` are means over a variable set of events, so their drift is not a braking-point or corner-speed change.
9. `int_dirty_air_tax_component.sql:358, 363-365` SE is a declared 15% convention, confidence n/(n+500) is 0.996 everywhere; pooled theta imposed although per-season values range from +0.418 to -0.011 (header 56-57).
10. Shrinkage models mix a fixed prior weight 5 with estimated variance components: `int_driver_circuit_affinity.sql:125-137`, `int_driver_circuit_era_affinity.sql:162-179`, `int_driver_season_ratings.sql:83-95`. sigma2 zero-fills n=1 cells (`:111`, `:141`, `:66`) and prior SD is the spread of all cell means including between-driver level (`:112`, `:142`, `:67`).
11. `int_circuit_x_constructor_interaction.sql:106, 120, 157` deviation includes in-season car development; "SE" is population SD (0 for n=1).
12. `int_constructor_structural_pace_qualifying.sql:110, 139-152` `STDDEV_POP` of 1 gives SE 0, CI width 0.
13. `int_event_corrections.sql:31-38, 136-154` outlier thresholds are multiples of a single race-wide fastest lap (can include deleted/generated laps and wet-to-dry changes); weights 0.3 and 0.6 never act because consumers require weight 1.0 (`:264-271`).
14. `int_lap_residual_decomposed_qualifying.sql:162, 174` `COALESCE(base,lap_time)` gives zero residual for baseless laps; constructor and wear COALESCE to 0 (122-123, 131); fuel constant 0.42 s from `int_lap_fuel_state_qualifying.sql:40-41` (hard-coded 12 kg and 0.035 s/kg).
15. `int_lap_residual_decomposed.sql` constructor term `COALESCE(...,0.0)` leaves the car level in wet-race residuals (flagged), dirty-air tax `0.0` where no row (reads as clean at lap grain); constructor term overlaps the compound term (see 4).
16. `int_constructor_deg_sensitivity.sql:228-235` slope SE ignores serial and cross-driver correlation; tau^2 inflated.
17. `int_driver_circuit_era_affinity.sql:207` era_label '2022–2024' applied to every season from 2022 (includes 2025).
18. `int_era_normalized_driver_rating.sql:156` `COALESCE(se,0)` collapses a NULL SE to a zero-width CI.
19. `int_lap_fuel_state.sql:130-131` `fuel_delta_vs_expected` is the constant `-rate` (off-by-one between `lap_number-1` and `lap_number`); unconsumed.
20. `int_lap_residual_stint_detrend.sql:27-34` no weight filter, regression against `lap_in_stint` including out-lap; 0.0 conflates no-data and zero slope.
21. `int_corner_metrics.sql:61, 55` exact `throttle_pct = 100` and braking truncated at the window start; overlapping windows share stretches.
22. `int_corner_drift_from_early_stint.sql:82-99` baseline includes valid lap 1 and inherits the mid-corner unit problem.
23. `int_lap_normalized_pace.sql:153-163` pooled slope confounded by car pace and tyre age, no season cap, fallback 0.004 at 158 (leaf).
24. `int_lap_fuel_state.sql:105-108` single full-tank linear-burn assumption for every car (documented; matters for absolute offsets).

### Could not check

- The Python fits behind `int_constructor_car_fe` and `int_constructor_car_fe_isolation`, and the theta_air 0.331 fit (external scripts).
- Data-dependent facts (row counts, NULL rates, whether any constructor has a NULL median at HAVING, window gaps in the field pace smoother, relative_distance scatter) because no build or query was run.
- `int_power_law_lap`, `int_stint_geometry`, `int_track_evolution` and the macros `trailing_median`/`clamp_or_null` internals were read only where needed.
- Test severities (warn vs error) in `schema.yml` were not extracted.
