# Fresh audit 04: MARTS (transform/models/marts, incl. marts/new_data)

Scope: 24 SQL models (19 in marts/, 5 in marts/new_data/) plus marts/schema.yml, _coverage.yml, _provenance.yml, new_data/_new_data.yml. Read-only review: no dbt run, no warehouse query, so nothing below is a measured row count. Where a finding depends on how often a NULL occurs, it says so. Paths are relative to /Users/justin/github/off-the-pace/transform/models/marts unless stated. 2026 not audited. 2018 Italian GP (2018_14) is the known source gap; mart_race_coverage is the model that labels it.

Verdict tally: SOUND 12, QUESTIONABLE 11, WRONG 1.

---------------------------------------------------------------------
## 0. Flow (text edges)

Upstream outside this group (intermediate / staging / seeds / reference):
- int_lap_residual_decomposed -> fct_lap_residuals, mart_degradation_history_envelope, fct_driver_skill_features, fct_cliff_prediction_features, fct_ghost_car_pace, fct_stint_features
- int_dirty_air_tax_component -> mart_metric_benchmark, mart_driver_season_summary, mart_race_driver_summary, fct_stint_features
- int_driver_race_skill_loro, int_driver_race_paired_laps -> mart_race_driver_summary; int_driver_race_skill_loro -> mart_race_coverage
- int_era_normalized_driver_rating -> mart_driver_season_summary
- int_driver_isolation_lap_values -> fct_driver_isolation_pair_lap, fct_driver_isolation_lap; int_driver_isolation_stint_tyre -> fct_driver_isolation_stint (and unreferenced stint CTE in _race); int_lap_telemetry_aggregates -> fct_driver_isolation_lap, fct_cliff_prediction_features
- int_constructor_structural_pace, int_circuit_x_constructor_interaction, int_constructor_deg_sensitivity, int_compound_cliff_predicted -> fct_ghost_car_pace
- int_cell_power_law_fit, int_power_law_lap, int_lap_fuel_state -> fct_power_law_training
- int_corner_metrics -> fct_telemetry_deltas; int_corner_skill_residuals -> mart_corner_skill_driver
- int_stint_geometry, int_stint_end_regime, int_pit_strategy_value, int_lap_thermal_proxy -> fct_stint_features
- int_lap_air_state, stg_lap_tyre_qa, stg_laps, race_to_track -> mart_race_coverage
- stg_laps, stg_laps_qualifying -> fct_speed_traps, fct_speed_traps_season, fct_track_limits, fct_track_limits_driver_session
- stg_jolpica_pit_stops, stg_pits, source(bronze_f1.raw_results) -> fct_pit_stop_crosscheck
- source(fits.degradation_isotonic) -> mart_degradation_history_envelope
- reference: dim_drivers (debut_year), dim_constructors (pu_family) -> fct_lap_residuals, fct_driver_skill_features; dim_circuits -> envelope, coverage, race summary, skill/cliff features; dim_compounds_season -> fct_cliff_prediction_features
- seed driver_isolation_method_scores -> all three fct_driver_isolation_{lap,stint,race}

Edges inside the group:
- fct_lap_residuals -> mart_metric_benchmark, mart_race_coverage, mart_race_driver_summary, mart_driver_season_summary, mart_build_provenance
- mart_race_coverage -> mart_race_driver_summary
- mart_race_driver_summary -> mart_driver_season_summary (n_races_unrated only)
- fct_driver_isolation_pair_lap -> fct_driver_isolation_lap, fct_driver_isolation_stint, fct_driver_isolation_race
- fct_driver_isolation_lap -> fct_driver_isolation_stint, fct_driver_isolation_race
- fct_cliff_prediction_features -> fct_power_law_training (dirty_air_share_lap only)
- fct_ghost_car_pace -> fct_ghost_race_finish
- fct_track_limits -> fct_track_limits_driver_session
- No in-group readers: fct_driver_skill_features, fct_stint_features, fct_telemetry_deltas, mart_corner_skill_driver, mart_degradation_history_envelope, mart_build_provenance, mart_metric_benchmark, the 4 other new_data marts.

Marts that reach the app export (scripts/export_app_data.py references): fct_lap_residuals, fct_driver_skill_features, fct_ghost_car_pace, fct_ghost_race_finish, fct_stint_features, fct_telemetry_deltas, fct_cliff_prediction_features, fct_driver_isolation_race, fct_driver_isolation_stint, fct_power_law_training, mart_build_provenance, mart_corner_skill_driver, mart_degradation_history_envelope, mart_driver_season_summary, mart_metric_benchmark, mart_race_coverage, mart_race_driver_summary.
Marts the assistant reads (scripts/assistant_query_views.py, app/src/assistant): fct_lap_residuals, fct_ghost_race_finish, fct_stint_features, fct_telemetry_deltas, mart_race_driver_summary; plus via assistant cards/sql in app/src: mart_driver_season_summary, mart_race_coverage, mart_corner_skill_driver (queries.ts, seasonKinds.ts, raceKinds.ts).
ML consumers (ml/src): fct_cliff_prediction_features (features.py, schema.py, intervals.py), fct_lap_residuals and fct_stint_features (features.py, evaluate.py, schema.py), fct_power_law_training and mart_degradation_history_envelope (powerlaw.py).
Not exported, no consumer beyond tests: fct_driver_isolation_lap, fct_driver_isolation_pair_lap (exporter comment says unexported; used by scripts/validate_driver_isolation.py), all 5 marts/new_data models.

---------------------------------------------------------------------
## 1. fct_lap_residuals  (marts/fct_lap_residuals.sql)

1. Purpose: lap-grain residual table (identity pace_delta = fuel + compound + constructor + dirty_air + driver_skill_residual) with an ml_eligible flag. Consumers: app export, assistant views, ML features.py, mart_metric_benchmark / race_coverage / race_driver_summary / driver_season_summary / build_provenance, Power BI exposure.
2. Flow: reads int_lap_residual_decomposed, dim_drivers, dim_constructors. Read by the five marts above.
3. How: thin projection; LEFT JOINs dim_drivers (debut_year) and dim_constructors (pu_family) on id (both unique-tested, no fan-out). ml_eligible (lines 106-111) = correction_weight = 1.0 AND compound_component_s IS NOT NULL AND compound_component_s <= 10 AND ABS(constructor_component_s) <= 10 AND lap_time_s IS NOT NULL.
4. Maths: no arithmetic of its own. Notes: ml_eligible does not require driver_skill_residual_s or base_track_pace_s to be non-NULL (lines 106-111), so "eligible" laps can have a NULL residual; downstream AVG/QUANTILE skip them but n_clean_laps in mart_race_driver_summary still counts them (see that model). driver_debut_year comes from dim_drivers.debut_year = MIN(race_year) in the data (dim_drivers.sql:31), so for any driver already racing in 2018 it is 2018, not a true debut; presentational only. Upstream fills reach this table: constructor_component_s is 0.0 where no structural-pace row exists (int_lap_residual_decomposed.sql:286, flagged by constructor_pace_is_filled, which this mart does NOT carry); dirty_air_tax_s is 0.0 where there is no int_dirty_air_tax_component row (int_lap_residual_decomposed.sql:310). Verdict: SOUND (pass-through; the fills are upstream and documented there).
5. Fills: none in this file (the join of dim attributes leaves NULL, not defaults). Inherited 0.0 fills described above.
6. Tests: schema.yml: not_null x14, unique on lap_id, relationships x4, accepted_values x1. Singular: assert_residual_variance_shrinks, assert_every_lap_race_rated_or_explained, assert_dirty_air_fill_only_where_base_unmeasured, assert_driver_skill_residual_reasonable, assert_dirty_air_mean_excludes_unmeasured, assert_ai_mart_counts_consistent. Upstream assert_residual_decomposition_identity / assert_lap_7term_identity test the identity. Mostly shape plus some value-range; the identity is checked upstream, not on this mart.

## 2. mart_metric_benchmark  (marts/mart_metric_benchmark.sql)

1. Purpose: per-season distribution (p05/p50/p95/mean/sd/n) of six lap metrics over ml_eligible laps so the assistant can say what is typical. Consumer: app export, assistant held stub.
2. Flow: fct_lap_residuals, int_dirty_air_tax_component. Nothing in-group reads it.
3. How: UNION ALL of six (metric, race_year, v) streams; the dirty-air stream is INNER JOINed to int_dirty_air_tax_component on lap_id with non-NULL tax (lines 41-47) so the 0.0 fill is excluded. Grouped by (metric_name, race_year); QUANTILE_CONT, AVG, STDDEV over non-NULL v.
4. Maths: correct. All metrics share unit seconds ('s' literal). Pools all laps of a season (lap-weighted; long-stint drivers weigh more) which is a design choice. STDDEV is NULL at n=1; no division. Verdict: SOUND.
5. Fills: no COALESCE. The literal 's' is a label.
6. Tests: unique_combination (metric_name, race_year), not_null x6, accepted_values x2; singular assert_dirty_air_mean_excludes_unmeasured, assert_ai_mart_counts_consistent. The dirty-air exclusion is value-tested; the rest is shape.

## 3. mart_build_provenance  (marts/mart_build_provenance.sql)

1. Purpose: one row per build with label version, theta, window, dbt invocation. Consumer: app export (git sha added there), assistant cards/build.ts.
2. Flow: fct_lap_residuals, race_to_track; dbt vars. Nothing reads it in-group.
3. How: MIN/MAX race_year, COUNT DISTINCT race_id from fct_lap_residuals; scheduled count from race_to_track; CROSS JOIN of two one-row CTEs.
4. Maths: trivial and correct. n_races counts races with lap residuals, n_races_scheduled counts the seed, so the gap (e.g. 2018_14, 2021_12) is visible. model_version is a hard NULL (line 33). Verdict: SOUND.
5. Fills: CAST(NULL) for model_version only (honest NULL).
6. Tests: _provenance.yml not_null on each column and accepted_values on one; assert_build_provenance_one_row_matches_vars (value test of vars vs row).

## 4. mart_race_coverage  (marts/mart_race_coverage.sql)

1. Purpose: one row per scheduled race: what was measured and a first-match coverage_reason (SOURCE_UNAVAILABLE, NO_RACING_LAPS, ALL_WET_NO_DRY_PAIRS, NO_TELEMETRY, TYRE_QA_QUARANTINED, TYRE_LIFE_PARTIAL, OK). Consumer: app export, assistant (raceKinds.ts, cards), mart_race_driver_summary.
2. Flow: race_to_track, stg_laps, fct_lap_residuals, int_lap_air_state, stg_lap_tyre_qa, int_driver_race_skill_loro, dim_circuits. Read by mart_race_driver_summary.
3. How: seven one-row-per-race CTEs LEFT JOINed onto the race list; shares are AVG(CASE WHEN ... THEN 1.0 ELSE 0.0 END). has_telemetry = air_measured_share > var(isolation_thin_min_air_measured_share)=0.5 (line 122-123). 2018_14 gets n_bronze_lap_rows = 0 and SOURCE_UNAVAILABLE (line 138), correctly distinct from zero laps.
4. Maths: shares are proper fractions over the right grain (lap rows per race); no fan-out because every CTE is grouped on race_id (dim_circuits join is on unique circuit_key). Notes: (a) the 0.90 tyre-life threshold is a Jinja literal (line 80 set min_tyre_life_share), not a dbt var, so it can drift from bronze_checks MIN_LAP_KEY_SHARE; (b) a race with laps but no air rows becomes has_telemetry = FALSE via COALESCE(..., 0.0) (line 122) and reads NO_TELEMETRY; this is a reasonable "unmeasured" reading; (c) rain_lap_share treats NULL rainfall_flag as not rain. Verdict: SOUND.
5. Fills: l.121-124: COALESCE counts to 0 (n_bronze_lap_rows, n_lap_rows, n_ml_eligible_laps, n_rated_drivers) - true zero counts, no number is built from them. COALESCE(air_measured_share, 0.0) (122) forces has_telemetry FALSE when absent (intended). Shares themselves are left NULL when no data.
6. Tests: _coverage.yml unique/not_null on race_id, not_null + accepted_range on share columns, accepted_values on coverage_reason; singular assert_every_lap_race_rated_or_explained (every race with laps is rated or has a reason). Partly value-level.

## 5. mart_race_driver_summary  (marts/mart_race_driver_summary.sql)

1. Purpose: driver x race teammate gap (rating_s) with a distribution-free CI, component means, positions gained, reason columns. Consumer: app export, assistant (heavily), mart_driver_season_summary.
2. Flow: fct_lap_residuals, int_dirty_air_tax_component, stg_results, int_driver_race_paired_laps, int_driver_race_skill_loro, dim_circuits, mart_race_coverage. Read by mart_driver_season_summary.
3. How: rating_s = driver_skill_loro_s (median of paired lap gaps to teammate). CI: for each (race, driver) the n = paired laps sorted by gap; macro median_ci_order_rank (macros/median_ci_order_rank.sql) gives j = largest k with P(Bin(n,.5) <= k-1) <= 0.025; ci_low = x_j, ci_high = x_{n-j+1}. NULL below n = 6. Component means are AVG over ml_eligible laps; dirty-air mean over measured laps only via the int_dirty_air_tax_component join. teammate = the rated same-constructor driver with most clean laps. constructor_rank = RANK of AVG(constructor_component_s) per race. positions_gained NULL for grid_position 0.
4. Maths check:
   - CI order-statistic formula verified by hand: n = 6 gives j = 1 (P(X<=0)=1/64 = 0.0156 <= 0.025, P(X<=1)=7/64 = 0.109), n = 5 gives none; interval [x_1, x_6] has coverage 1 - 2/64 = 96.9%. Correct. The CI is for the median of the paired gap and brackets rating_s by construction (same population); assert_mart_race_ci_brackets_rating tests this, including n and median equality.
   - QUESTIONABLE (assumption, line 69-75): the CI treats the paired laps as independent draws. Lap gaps within a race are autocorrelated (stint, traffic, tyre state), so the interval is too narrow. No effective-n correction. Not a formula error; the owner rules on whether to widen.
   - QUESTIONABLE: constructor_rank (156-163) ranks AVG(constructor_component_s) over ml_eligible laps, and constructor_component_s is the 0.0 fill (not the structural pace) for any constructor with no structural-pace row in that race (int_lap_residual_decomposed.sql:286). A filled constructor therefore ranks as "exactly field average" and is averaged in with real values; the fill flag constructor_pace_is_filled exists upstream but is not used here. How often: not measured.
   - n_clean_laps = COUNT(*) of ml_eligible laps (line 37), but ml_eligible does not require a non-NULL residual, so the count can exceed the laps behind any given mean. Minor.
   - Ties: RANK() on constructor_rank (ties possible only on equal averages, practically none except fills). rating_trust_label thresholds 6/12 match the macro minimum.
   - Division: none unguarded. Verdict: QUESTIONABLE (constructor_rank with filled 0.0, CI independence assumption).
5. Fills: COALESCE(r.has_dnf, FALSE) line 189: a driver with no stg_results row is shown as not DNF (it is "unknown"); COALESCE(n_dirty_air_measured_laps, 0) line 205 (true count). CASE ... ELSE 'suppressed' (line 196) is a label for paired_lap_count NULL or < 6 (intended). No sum-of-components with NULL-to-0.
6. Tests: unique_combination, not_null x11, relationships x4, accepted_range x5, accepted_values x4; singular assert_mart_race_ci_brackets_rating (value-level, strong), assert_mart_race_teammate_gap, assert_mart_positions_gained_pit_lane, assert_reason_iff_missing, assert_every_lap_race_rated_or_explained, assert_dirty_air_mean_excludes_unmeasured, assert_median_ci_order_rank_known_values (macro). Good maths coverage on the CI; none on constructor_rank.

## 6. mart_driver_season_summary  (marts/mart_driver_season_summary.sql)

1. Purpose: driver x season summary for "22nd of 22" style answers: rating_s (shrunk teammate-relative gap), CI, rank, percentile, component means, rank_separated_from_next. Consumer: app export, assistant (parity.07b, seasonKinds).
2. Flow: fct_lap_residuals, int_dirty_air_tax_component, int_era_normalized_driver_rating, mart_race_driver_summary. Nothing in-group reads it.
3. How: primary_team = constructor with the most ml_eligible laps; teammate = other driver with most laps in that constructor; ratings INNER JOINed to primary_team; RANK over rating_s per season; LEAD(ci_low) in (rating_s, driver_id) order for rank_separated_from_next = ci_high < next_ranked_ci_low; percentile = 1 - (rank-1)/NULLIF(n_drivers-1,0).
4. Maths check:
   - Percentile and rank are correct (rank 1 = lowest, most-negative gap; n_drivers = 1 gives NULL, not a divide). RANK ties give equal rank and equal percentile; the LEAD order breaks ties by driver_id, so with an exact tie the lower-id driver is compared to the next, which is acceptable.
   - rank_separated_from_next compares one driver's ci_high with the next driver's ci_low only; a sound conservative separation test.
   - QUESTIONABLE (lines 143-150): constructor_rank = RANK of AVG(constructor_component_s) per season over ml_eligible laps. Same issue as the race mart: 0.0-filled constructor laps (wet races with no structural-pace row) are averaged into the season mean, biasing a constructor toward the middle. Also lap-weighted, so a constructor with many wet laps is pulled to 0.
   - QUESTIONABLE (lines 56-67 vs 72-77): the `components` CTE computes mean_dirty_air_tax_s over ml_eligible laps including the 0.0 fill, but it is not selected (the select uses dair.mean_dirty_air_tax_s from the measured-only CTE). Dead column, harmless, but it is the exact trap the header warns about; leave note for cleanup.
   - n_drivers counts only drivers that have a rating AND a primary team (ratings INNER JOIN primary_team), not every driver of the season, so "22nd of 22" can be "22nd of 19" if rated drivers are fewer; the denominator is correct for the rank but is the rated count.
   - Unit: all seconds; rating CI comes unchanged from int_era_normalized_driver_rating (not audited here). Verdict: QUESTIONABLE (constructor_rank with fills).
5. Fills: COALESCE(u.n_races_unrated, 0) line 173 and COALESCE(n_dirty_air_measured_laps, 0) line 174 are counts. CASE WHEN dair.mean IS NULL THEN 'NO_MEASURED_LAPS' is a reason label. teammate_gap_s is NULL when no teammate (not 0). No NULL-to-0 inside a sum.
6. Tests: unique_combination, not_null x14, relationships x2, accepted_range x7, accepted_values x1; singular assert_mart_season_teammate_gap, assert_mart_season_uncertainty_carried, assert_dirty_air_mean_excludes_unmeasured, assert_ai_mart_counts_consistent. Rank, percentile and rank_separated_from_next are not value-tested beyond ranges.

## 7. fct_driver_skill_features  (marts/fct_driver_skill_features.sql)

1. Purpose: driver-race feature vector (clean-lap residual stats, synthetic-teammate proxy, constructor index, circuit traits) for the driver-skill extraction use. Consumer: app export and several app pages (driver-consistency, wet-race-specialist), Power BI exposure; no ML code in ml/src reads it.
2. Flow: int_lap_residual_decomposed, int_lap_anomaly_flags, int_synthetic_teammate, int_constructor_structural_pace, race_to_track, dim_circuits, dim_drivers, dim_constructors. Nothing in-group reads it.
3. How: clean filter = correction_weight 1.0 AND anomaly_class NOT IN (mistake, conditions) AND is_rain_lap FALSE (applied to AVG/STDDEV/MEDIAN/COUNT through CASE). Synthetic teammate: weighted mean of proxy by pair_quality_weight, INNER JOINed back to the clean laps. constructor_index_confidence_final = LEAST(panel_observations_n / 500, 1).
4. Maths check:
   - QUESTIONABLE (lines 117-118): driver_skill_proxy_mean_s = AVG(proxy * weight) / AVG(weight). AVG skips rows where proxy is NULL in the numerator but the denominator AVG(weight) still includes those rows' weights if the weight is non-NULL. int_synthetic_teammate defines proxy as NULL when no teammate lap (line 133) and weight from a 5-lap STDDEV window (line 162-169), so a row can have NULL proxy and a non-NULL weight; then the mean is biased toward 0. Not verifiable without data; the clean form is SUM(proxy*w)/SUM(w) over rows with a proxy.
   - QUESTIONABLE: clean_lap_count (line 90) counts laps passing the filter regardless of whether driver_skill_residual_s is NULL, while the mean/stddev/median skip NULL residuals (WI-01 makes NULL residuals real). The count can exceed the n behind the mean.
   - Rows with anomaly_class NULL (no match in int_lap_anomaly_flags) drop out of every clean aggregate silently (NULL NOT IN (...) is not true). Conservative, but invisible.
   - constructor_index_confidence_final: a heuristic saturating at 500 laps; not a probability; fine as a labelled proxy.
   - ml_eligible_lap_share is usable_for_modelling share over all laps, a different definition from fct_lap_residuals.ml_eligible; name collision only. Verdict: QUESTIONABLE.
5. Fills: line 213 COALESCE(ta.strategic_divergence_share, 0.0): a driver-race with no synthetic-teammate row (no clean teammate-paired lap) is shown as 0.0 divergence = "never diverged", which is a default entering a number (the true value is unknown). Line 212 COALESCE(teammate_available_flag, FALSE) is consistent with "no teammate row". BOOL_OR(COALESCE(rainfall_flag, FALSE)) line 99: NULL treated as dry.
6. Tests: unique_combination, relationships x4, value range expectations (dbt_expectations between) at model level; no singular test. Shape plus ranges; no maths test.

## 8. fct_stint_features  (marts/fct_stint_features.sql)

1. Purpose: one row per tyre-run stint for pit-strategy and stint-life work: length, compound, thermal load, cumulative dirty-air tax, cliff lap, end-of-stint pace falloff slope, strategy verdict, tyre_management_score, censoring and cut-short fields. Consumer: app export, assistant, ML (features.py, evaluate.py, schema.py), pit-strategy page.
2. Flow: int_stint_geometry, int_stint_end_regime, stg_laps, int_lap_thermal_proxy, int_dirty_air_tax_component, int_lap_air_state, int_lap_anomaly_flags, int_lap_residual_decomposed, int_pit_strategy_value, int_lap_fuel_state. Nothing in-group reads it.
3. How: many one-row-per-stint CTEs LEFT JOINed on stint_id; INNER JOIN to int_stint_end_regime (line ~312) so stints without an end-regime row are dropped. cumulative_dirty_air_tax_s = SUM over measured laps; NULL when none (TX-17). tyre_management_score = end_residual / opportunity_cost clamped to +/-3 via clamp_or_null (guarded: only when cost > 0).
4. Maths check:
   - WRONG (lines 148-155 and 217-230): end_of_stint_pace_falloff_s_per_lap is an OLS slope over the last 3 rows, but mean_x = AVG(valid_lap_in_stint) is over all 3 rows, mean_y = AVG(driver_skill_residual_s) skips NULL, the numerator SUM((x - mean_x)(y - mean_y)) skips rows whose y is NULL (NULL product), while the denominator SUM(POWER(x - mean_x, 2)) includes them. When one of the last 3 residuals is NULL (live since WI-01: unmeasured base gives NULL residual) the slope is computed from a mismatched set. Worked case: x = 1,2,3, y = (y1, y2, NULL) gives numerator (y2-y1)/2 over denominator 2 = (y2-y1)/4, half the true two-point slope; middle-NULL happens to come out right. n_laps counts rows (3), so the n < 3 gate does not catch it. How many stints are affected was not measured.
   - QUESTIONABLE: cumulative_dirty_air_tax_s for a partly measured stint is a sum over measured laps only (line 117), so it is not comparable across stints with different measured counts; n_dirty_air_measured_laps is carried so the reader can see it, and the header says so.
   - tyre_management_score ratio: unit is dimensionless (s / s); clamped both sides, NULL not clamped. end_residual comes from the stint's last lap by lap_in_stint (can be an in-lap or out-lap with a different pace regime). The cost > 0 guard avoids divide by zero. Sound apart from definitional questions.
   - slope_reliable and clean_slope_s_per_lap use REGR_SLOPE of weight_corrected_lap_time on age_in_stint, filtered to valid laps; NULL if age is constant or missing. Fine.
   - stint_length_laps = MAX(lap_in_stint) while starting_tyre_age_laps = MIN(age_in_stint) - 1 (used tyres): consistent definitions. Verdict: WRONG for the falloff slope when a trailing residual is NULL; rest SOUND/QUESTIONABLE as above.
5. Fills: line 281-282 COALESCE(n_dirty_air_measured_laps, 0) (count); `NOT COALESCE(rair.has_telemetry, FALSE)` (race with no air rows treated as no telemetry, a reason label). clamp_or_null keeps NULL (explicit anti-LEAST/GREATEST design). No NULL-to-0 inside the SUM (SUM skips NULL, but the count shown).
6. Tests: unique + not_null x12 on keys, relationships x3, between x3, accepted_range, accepted_values x6; singular assert_stint_dirty_air_null_when_unmeasured, assert_stint_censoring_partition, assert_stint_end_cause_partition. The falloff slope is not value-tested. Mostly shape.

## 9. fct_cliff_prediction_features  (marts/fct_cliff_prediction_features.sql, 1024 lines)

1. Purpose: lap-grain ML feature table and labels (next_5_lap_cumulative_jump_s primary, laps_until_cliff_class, alternative horizons, survival weight, is_training_eligible). Consumer: ML (ml/src/features.py, schema.py, intervals.py, holdout_config.py), the xgboost_cliff_model exposure, fct_power_law_training (dirty_air_share_lap). Not exported to the app as a table beyond the export reference (2 hits) and not read by the assistant.
2. Flow: reads int_lap_residual_decomposed, int_lap_anomaly_flags, int_compound_cliff_predicted, int_lap_thermal_proxy, int_lap_air_state, int_lap_proximity, int_lap_corner_inputs, int_lap_corner_drift, int_event_corrections, int_qualifying_driver_summary, int_sc_hazard_history, int_lap_residual_stint_detrend, int_lap_telemetry_aggregates, dim_compounds_season, dim_circuits, race_to_track. Read by fct_power_law_training. It deliberately does not read int_synthetic_teammate (leakage guard).
3. How: LEFT-join assembly at lap grain (`base`), then window functions per stint for labels. Labels: jump_k = SUM_{i=1..k} LEAD(residual, i) - k * residual - drift * k(k+1)/2, only when LEAD(lap_in_stint, k) = lap_in_stint + k (no hole), clamped at +/-10k via clamp_or_null. cliff class = first later lap in the stint where residual(f) - residual(a) - (offset) * drift > 1.0 s, bucketed 0-2 / 3-5 / 6+ / none; NULL when an unmeasured lap could hide a crossing. survival_weight = 1/P(stint reaches lap) clipped to [0.25, 4], computed from strictly prior seasons.
4. Maths check:
   - Detrend arithmetic verified: drift * (1+2+3) = 6 and drift * (1+...+5) = 15, matching lines 727 and 739. The no-hole guard guarantees the intermediate laps exist. The cliff scan uses true lap offsets, so it matches the bucket names.
   - Survival weight: numerator and denominator are lagged together over prior seasons (ROWS UNBOUNDED PRECEDING AND 1 PRECEDING), so P is a real probability; 2018 has none and gets weight 1.0. QUESTIONABLE edge (lines 231-262): a (compound, lap_in_stint) cell first appearing in a late season has no earlier row, so n_reaching is NULL (not 0) and the weight falls back to 1.0 instead of the cap 4.0 that a true zero-prior reach would imply. Stated as intended in the comment; the owner rules.
   - QUESTIONABLE (lines 577-590): surface_bulk_ratio = (s/Ws) / NULLIF(s/Ws + b/Wb, 0) with s and b each COALESCEd to 0.0 inside the sum. If only one of cumulative_push_load_surface / bulk is NULL, the ratio becomes exactly 0.0 or 1.0, outside the stated [0, 0.606] range, and a NULL is turned into an invented number. If both are NULL the NULLIF gives NULL (correct). Whether the two ever disagree on NULL depends on int_lap_thermal_proxy; not verified.
   - QUESTIONABLE (line 552): drift_s_per_lap = COALESCE(det.drift_s_per_lap, 0.0): a stint with no fitted drift gets "no drift" and its detrended labels equal the raw jumps. Silent default entering the label of next_5_lap_cumulative_jump_s (the PRIMARY target), line 750-ish. The drift is also an OLS slope over the stint's own pre-cliff laps, so it uses future laps of the same stint; it is used only in labels (not as a feature), which is acceptable but means the label depends on the whole stint.
   - Legacy next_lap_degradation_jump_s and _detrended_s use LEAD(...,1) with no no-hole guard (lines 705-722), so across a missing lap they measure a two-lap jump while subtracting one lap of drift. Comment labels them legacy/diff-gate.
   - Left joins on (circuit, compound_code, season) to dim_compounds_season and on (circuit_slug, season) to int_sc_hazard_history rely on uniqueness of those keys (dim_compounds_season has a unique_combination test; the hazard join was verified one-to-one per the comment). Verdict: QUESTIONABLE (surface_bulk_ratio fabrication, drift default, survival edge). No arithmetic error found in the label formulas.
5. Fills: line 457 COALESCE(corner_drift_coverage, 0.0) and corner_input_coverage 0.0 (measured zero coverage, argued in the comment); COALESCE(quali_push_laps_n, 0); COALESCE(prior_racing_laps, 0), COALESCE(prior_seasons_n, 0) (source never NULL, per comment); COALESCE(correction_weight < 1.0, FALSE) event_flag_any (no correction row = no event); drift_s_per_lap 0.0 (552); survival_weight COALESCE(..., 1.0) (neutral weight, tested); surface_bulk_ratio inner COALESCE 0.0 (577-590, flagged); is_training_eligible COALESCE(..., FALSE). Many columns deliberately NOT filled (dirty-air, proximity, corner residuals, SC hazard), which is documented.
6. Tests: unique_combination, relationships x5, not_null x4, expect_between x2 at model level; singular assert_label_window_has_measured_base, assert_cliff_class_horizon_partition, assert_survival_weight_neutral_without_prior_curve, assert_event_driven_excluded_or_weighted, assert_prior_season_labels_frozen, assert_degradation_source_classes_reachable, assert_air_state_no_telemetry_share_by_season. Good coverage of the label construction and leakage; no test of surface_bulk_ratio range or the drift default.

## 10. fct_power_law_training  (marts/fct_power_law_training.sql)

1. Purpose: training frame for ml/src/powerlaw.py, one row per race x compound-hardness cell with a fit_eligible power-law fit; targets alpha_s, beta, curve increments; features from an allowlist. Consumer: ML (powerlaw.py), app export, degradation-simulator powerLaw.ts.
2. Flow: int_cell_power_law_fit, int_power_law_lap, fct_cliff_prediction_features, int_lap_fuel_state. Nothing in-group reads it.
3. How: cells filtered to fit_eligible; laps restricted to stints with >= 5 laps over >= 2 ages (same rule as the fit); per cell aggregates: MIN of track traits, AVG dirty_air_share_lap, AVG constructor_pace_s; per-cell stint_start_fuel_kg = AVG over distinct stints of MAX(fuel_mass_kg); track_temp_c = circuit-season median over all laps. final WHERE cf.dirty_air_share IS NOT NULL drops cells with no measured air state.
4. Maths: AVG over laps of dirty_air_share_lap with NULL laps skipped = mean over measured laps (the comment says so). stint start fuel = MAX within stint is correct if fuel only declines inside a stint (comment states it). era_code CASE ELSE 2 (line 161) maps any era other than '2018' and '2019-21' to 2, which includes 2026 and any unseen era silently; fine for the current seed. MIN(track_energy_index) assumes one value per race (constant). cst median is over all laps of the circuit-season, including laps outside qualifying stints, unlike the other features; a small inconsistency of population, not a formula error. Verdict: SOUND.
5. Fills: no COALESCE; ELSE 2 (161) discussed; the only silent drop is the FD6 WHERE (documented).
6. Tests: unique + not_null x11, accepted_values x1; singular assert_power_law_no_seed_columns (leakage allowlist), assert_power_law_fit_bounds (upstream). Mostly shape plus the allowlist guard.

## 11. mart_degradation_history_envelope  (marts/mart_degradation_history_envelope.sql)

1. Purpose: pre-aggregated historical stint envelope for the Degradation Simulator: per (circuit, era, compound, lap_in_stint) fuel-removed pace percentiles, deg-from-fresh bands, isotonic monotone columns and modulation coefficients. Consumer: app export and degradation-simulator queries, ml/src/powerlaw.py, smoke tests.
2. Flow: int_lap_residual_decomposed, race_to_track, dim_circuits, source(fits.degradation_isotonic). Nothing in-group reads it.
3. How: clean laps (weight 1, no SC/VSC/red-flag/major-outlier, lap_in_stint 1-50), UNION ALL a pooled '_all' compound; ref_green_pace_s = MEDIAN(weight_corrected_lap_time) over laps with age_in_stint <= 2 per (circuit, era, compound); envelope = QUANTILE_CONT p10/p50/p90 per lap_in_stint and the same minus ref; HAVING n_observations >= 3; LEFT JOIN isotonic fits.
4. Maths check:
   - QUESTIONABLE (lines 97-101 vs 108-122): the "fresh" anchor is defined by age_in_stint <= 2, but the envelope is indexed by lap_in_stint. On a used set (starting age > 0) lap_in_stint 1 has high age, so those laps sit in a lap_in_stint 1 bucket yet are not in the anchor. Deg-from-fresh = observed - anchor then mixes tyre-age and lap-in-stint effects. Use of age for the anchor and lap_in_stint for the index is not reconciled in the file.
   - QUESTIONABLE (line 162): n_observations >= 3 allows p10/p90 from 3 points, which are essentially min/median/max; not a stable band. The percentiles are over laps pooled across races/drivers; no per-stint independence handling.
   - QUESTIONABLE: ref_green_pace_s is a median across all fresh laps of the cell, including different years and fuel eras within the pre/post era; and the era split is `race_year < var(era_boundary)`, so everything from 2022 on (now 2022-2025, plus 2026) is one 'post2022' era, while the header says 2022-2024. A rule change inside that span is not separated.
   - '_all' pooled row mixes compounds; its anchor is the median of all fresh laps, so its deg-from-fresh differs in meaning from the per-compound rows (test assert_envelope_has_pooled_row only checks existence). The simulator knows to fall back to it.
   - weight_corrected_lap_time = lap_time - fuel; correct unit (s).
   - join CAST(REPLACE(race_id,'_','') AS INTEGER) = rt.race_id: '2018_1' -> 20181 and '2018_10' -> 201810 are distinct; 2019_1 -> 20191; no collision found by hand, but the construction is fragile (2018_1x vs 2018_1 + x not an issue because the year prefix is fixed length). Verdict: QUESTIONABLE.
5. Fills (lines 151-153): COALESCE(iso.dirty_air_deg_mult, 1.0), COALESCE(iso.temp_headroom_c, 8.0), COALESCE(iso.temp_penalty_s_per_deg, 0.010). Where the isotonic fit has no row (new circuit/era/compound/lap, including any lap beyond the fitted range) the row is published with these literals as though fitted; the mono columns stay NULL, so the simulator can detect the missing fit only from those NULLs. Values 8.0 and 0.010 are hard-coded, undocumented in the file as to origin. COALESCE(correction_weight, 0) = 1 (line 69) just drops NULL-weight laps.
6. Tests: unique_combination, row-count between, three column-pair A > B (p90 >= p50 >= p10 style), not_null x13, relationships x2, accepted_values, between x3; singular assert_envelope_has_pooled_row. Value-ordering tests present; no check on the fresh-anchor consistency or the default fills.

## 12. fct_ghost_car_pace  (marts/fct_ghost_car_pace.sql)

1. Purpose: counterfactual lap time if an ego driver had driven a host constructor's car, per (ego driver, host constructor, race, lap). Consumer: app export, ghost-car routes (standings, lap-chart), fct_ghost_race_finish.
2. Flow: int_lap_residual_decomposed, int_compound_cliff_predicted, stg_laps, int_constructor_structural_pace, int_circuit_x_constructor_interaction, int_constructor_deg_sensitivity. Read by fct_ghost_race_finish.
3. How: predicted = base_track_pace + fuel + ego driver_skill_residual + host constructor structural pace + dirty_air_tax + compound_component + (host deg slope - ego deg slope) x age + cliff interaction. Cartesian join of each ego lap with every constructor that ran a valid lap that race (about 10x the laps). Cliff interaction = plateau x (ramp(hinge host) - ramp(hinge ego)) clamped to +/-2 s. recombination_confidence = host_obs / (host_obs + 50) x correction_weight; rows with confidence <= 0 are dropped.
4. Maths check:
   - The recombination follows from the identity pace_delta = fuel + compound + constructor + dirty_air + residual: swapping the constructor term and adding two interaction terms that are zero when ego = host keeps the ego-in-own-car identity exact (tested to 0.0001 s by assert_ghost_car_self_consistency). Correct.
   - QUESTIONABLE (lines 210-211, 374-381): when the EGO's own constructor has no structural-pace row (the 0.0 fill in int_lap_residual_decomposed.sql:286, wet races and some mixed races), the ego's driver_skill_residual_s already carries that car's pace (the header there says so), and then the host term is added on top: ego car is counted in the residual AND the host car is added. The host-side fill is flagged (host_constructor_pace_is_prior) but no ego-side flag exists, so those laps look like normal counterfactuals. Affects the rows where ego constructor pace was filled, a minority by design but not counted here.
   - QUESTIONABLE (WHERE line 445): header (lines 70-71) says rows with confidence < 0.05 are excluded; the code keeps everything > 0.0. Documentation and code disagree. A host with panel_observations_n = 0 gives confidence 0 and is dropped, including the ego = host row, so the self-consistency test passes only for the rows that remain.
   - Terms COALESCEd to 0 (lines 374-381) cannot trigger for base_track_pace_s, compound_component_s, driver_skill_residual_s because the ego_laps CTE requires driver_skill_residual_s IS NOT NULL, which in turn is NULL if base, compound, fuel, constructor or dirty-air tax are NULL (int_lap_residual_decomposed.sql:367-391); dirty_air_tax_s is non-NULL on every included lap. So these COALESCEs are inert for ego terms; they are live only for deg_interaction_s / cliff_interaction_s, which are themselves never NULL.
   - deg_interaction uses age_in_stint COALESCE 0 and slope delta: unit s/lap x laps = s. Cliff: plateau in s, ramp is 0..1, so term bounded by plateau; the +/-2 s clip is inert, as stated.
   - Join fan-out: host_constructor_pace, host_interaction and deg cells are one row per (race, constructor) / (season, constructor, compound) (not unique-tested in the mart file itself; relies on the sources). Verdict: QUESTIONABLE.
5. Fills (all in lines 210-245 and 297-321): COALESCE(host pace, 0.0), COALESCE(circuit interaction, 0.0) (carried only, not in sum), COALESCE(deg slopes, 0.0), COALESCE(cliff shifts, 0.0), COALESCE(age_in_stint, 0), COALESCE(compound_cliff_severity, 0.0), COALESCE(onset, 999.0), COALESCE(panel_observations_n, 0), COALESCE(interaction_obs_n, 0). TX-18 flags *_is_prior mark host pace, host deg, ego deg and cliff-params fills; SEs are left NULL (not 0). Terms inside the predicted-lap SUM that become 0 when missing: host_constructor_pace_s, deg_interaction_s (both slopes), cliff_interaction_s; each of those is flagged except the ego-side constructor fill described above.
6. Tests: schema not_null x20, unique, accepted_range x3, between x2; singular assert_ghost_car_self_consistency (identity, strong), assert_ghost_recombination (|predicted - actual| bound 11 s, deliberately loose), assert_ghost_se_never_zero_filled, assert_cliff_seed_severity_bounded. Self-scenario only; cross-scenario (the actual counterfactual) is untested as the ghost_self_scenario_rank header admits.

## 13. fct_ghost_race_finish  (marts/fct_ghost_race_finish.sql)

1. Purpose: for each (host constructor, race) scenario, ranks every driver by predicted mean pace and gives order probabilities (p_beats_next, finish_pos_se). Consumer: app export (counterfactual-championship), assistant views, query-lab.
2. Flow: fct_ghost_car_pace (confidence >= 0.3), stg_laps, stg_results. Nothing in-group reads it.
3. How: per (race, ego, host) means of predicted_residual_pace_s (fuel-excluded); RANK ascending; pairwise Normal approximation P(i ahead of j) = Phi((mu_j - mu_i)/sd) with host structural term cancelling and only exposure differentials of shared host coefficients remaining; finish_pos_se = sqrt(sum p(1-p)); p_beats_next from the ranked-next driver.
4. Maths check:
   - Variance algebra is internally consistent: independent per-driver terms add, the shared host slope/cliff terms enter as a difference. The host pace SE correctly cancels. Poisson-binomial sd uses p(1-p), symmetric. The normal_cdf macro is the A&S 26.2.17 rational approximation (error about 7.5e-8). SE NULLs propagate (CASE guards the GREATEST floor), good.
   - QUESTIONABLE (line 234): finite-sample term lap_pace_sd^2 / laps uses STDDEV_SAMP of predicted_lap_time_s, which contains the fuel_component (about 3 to 4 s decline over a race) and tyre ageing trends. Those are deterministic structure, not sampling noise, so sd/sqrt(n) overstates the SE of the mean pace; also the ranking variable is predicted_residual_pace_s (fuel removed) while the SE uses the fuel-included series. The mismatch can only widen intervals.
   - QUESTIONABLE (lines 230-233): cliff-shift SE exposure = se_shift x mean_severity x fraction_active, but the cliff term is plateau x ramp(hinge), with a ramp that saturates after 2.5 laps, so d/d(shift) is plateau/2.5 inside the ramp and 0 beyond it. The product with the raw compound_cliff_severity (not the plateau macro) and an "active" fraction is a rough bound, not the derivative. It is labelled an approximation in the header only for independence, not for this.
   - QUESTIONABLE: ego coefficients are treated as independent across drivers (line 232-234) although two drivers of one constructor share the same ego slope and shift estimates; the pairwise difference for teammates therefore overstates variance.
   - QUESTIONABLE (line 102 vs fct_ghost_car_pace 445): filter confidence >= 0.3 means for correction_weight 1.0 laps a host needs about 22+ panel observations (0.3 = obs/(obs+50)), and for weight-0.6 laps about 50+, so the lap set per scenario depends on the host's data volume; drivers' laps_counted/coverage then differ by host. Coverage is exposed (lap_coverage, is_short_run).
   - Ranks: RANK ties possible for equal predicted pace (practically none); p_beats_next uses rank_j = rank_i + 1, which returns NULL if ties skip a rank. Ties to actual finish position are claimed in the header ("ties broken by actual finish position") but the code ranks by predicted pace alone with no tiebreak (lines 250-253). Documentation and code disagree; practical effect negligible.
   - actual_finish_position falls back to lap-derived position only when the driver has no stg_results row. Verdict: QUESTIONABLE (SE construction approximations).
5. Fills: no COALESCE on numbers; COALESCE(rf.is_dnf, FALSE) for actual_is_dnf (unknown shown as non-DNF). GREATEST(SQRT(...), 1e-6) floor (line 282) only on a non-NULL value. Intentionally NULL SEs.
6. Tests: unique + not_null x8, between x4, accepted_range, accepted_values; singular assert_p_beats_next_geq_half (consistency of rank and probability), assert_ghost_self_scenario_rank (Spearman vs official finish, self scenario only), assert_ghost_se_never_zero_filled. The SE magnitude itself (calibration) is not tested.

## 14. fct_driver_isolation_pair_lap  (marts/fct_driver_isolation_pair_lap.sql)

1. Purpose: tier-3 relative pace per pair of cars on the same lap, with an exact split into pace gap, car advantage and traffic advantage. Consumer: the three other isolation marts and scripts/validate_driver_isolation.py. Not exported.
2. Flow: self-join of int_driver_isolation_lap_values. Read by fct_driver_isolation_lap / _stint / _race.
3. How: pair (a, b) when same race_year, race_id, lap_number, same compound, different driver and |age_b - age_a| <= 2 (var). Both directions emitted. relative_pace_gain_s = b.lap_time - a.lap_time (positive = a faster); pace_gap = a.pace_isolated - b.pace_isolated; car = b.car_iso - a.car_iso; traffic = b.dirty_air_tax - a.dirty_air_tax.
4. Maths: the identity relative = pace_gap + car + traffic + (C_peer - C_driver) is derived in the header and the unpublished tyre term is zero at equal age; tested to 1e-6 on same-age rows. Antisymmetric by construction. Peer sets differ between a pair of cars for a lap (a pair row exists in both directions, so the counts are symmetric). No division. Caveat in header: peers share a lap and compound but not a situation (fighting, orders), so pair means are not controlled comparisons. Verdict: SOUND.
5. Fills: none.
6. Tests: unique_combination, not_null x16, relationships x4, accepted_values x4; singular assert_isolation_cumulative_identity, assert_isolation_sign_convention. Identity tested numerically.

## 15. fct_driver_isolation_lap  (marts/fct_driver_isolation_lap.sql)

1. Purpose: per-lap isolation ratings with a trailing 5-lap window rating, SE, shrinkage and trust label. Consumer: stint and race isolation marts, validation scripts; not exported.
2. Flow: int_driver_isolation_lap_values, fct_driver_isolation_pair_lap, int_lap_telemetry_aggregates, seed driver_isolation_method_scores. Read by _stint and _race.
3. How: window (RANGE on lap_number, within a stint, last 4 laps + current) of non-extrapolated pure_skill gain; relative window = SUM(relative_sum)/SUM(n_pair_laps). Each NULL below isolation_window_min_laps = 3. SE pure = sqrt(sigma_w^2 / (n f)); SE relative = sqrt(Var of pooled pair values) / sqrt(distinct laps with peers). tau^2 per (season, rating) = max(VAR_SAMP(raw) - AVG(SE^2), 0), NULL-safe. lambda = tau^2 / (tau^2 + SE^2); shrunk = lambda x raw; confidence = round(100 lambda x method_score).
4. Maths check:
   - Window mean pure and the pooled relative mean are properly weighted. SE guarded by window floor; the relative-SE branch NULLs on missing sums and uses GREATEST(var, 0) before sqrt.
   - lambda formula and the macro's SE = 0 -> 1.0 branch are correct for a normal-normal shrink to 0.
   - QUESTIONABLE (tau^2, lines 184-194): tau^2 is estimated by VAR_SAMP over rolling windows that overlap by 4 of 5 laps, so the sample is heavily autocorrelated and the variance estimate has far fewer effective observations than rows; method-of-moments is still unbiased in expectation but its noise is not reflected. Also VAR_SAMP over all drivers pools between-driver and car-driven variance, so tau^2 is the total variance of the raw rating, which is the intent ("signal variance"), not specifically driver skill.
   - QUESTIONABLE (relative SE): pair-lap values within a window share the focal driver's lap time and the same peers across consecutive laps, so treating them as independent (SD / sqrt(distinct laps)) understates the SE; the header states the formula, not the dependence.
   - GREATEST(NULL-safe) handled explicitly in tau (comment T29). Verdict: QUESTIONABLE (SE independence assumptions; the arithmetic is correct).
5. Fills: COALESCE(pa.n_pair_laps, 0) / n_teammate_peers (counts, line ~100). Ratings stay NULL (documented). None enter a sum.
6. Tests: unique + not_null x17, relationships x4, accepted_values x5; singular assert_isolation_window_no_forward_reach (causality), assert_isolation_small_sample_nulls, assert_isolation_reliability_bounds, assert_isolation_cumulative_identity, assert_isolation_phase_partition. Good structural/value checks; SE calibration untested.

## 16. fct_driver_isolation_stint  (marts/fct_driver_isolation_stint.sql)

1. Purpose: isolation ratings per stint and stint phase (early / mid / cliff / recovery plus an 'all' row). Consumer: app export (stint facts), validation scripts.
2. Flow: fct_driver_isolation_lap, fct_driver_isolation_pair_lap, int_driver_isolation_stint_tyre, int_stint_end_regime, int_pit_strategy_value, driver_isolation_method_scores.
3. How: UNION ALL a per-phase grouping with an 'all' grouping; mean pure over non-extrapolated laps; relative mean over pair-laps with SD / sqrt(distinct laps); tau^2 from the 'all' rows with n >= 6 (one row per stint). identity_* via the macro.
4. Maths check:
   - Aggregation and SE formulas are consistent with the lap model. tau^2 from 'all' rows is reused for the phase rows (smaller n): lambda correctly shrinks them harder because SE is larger.
   - Identity macro (macros/driver_isolation_identity_terms.sql:36-50): every term is a SUM over pair rows with non-NULL pace_gap divided by identity_n_pair_laps, so all four terms share one denominator and the three contributions close up to the tyre-age bias. QUESTIONABLE: the traffic and car terms use SUM(CASE WHEN pace_gap IS NOT NULL THEN term END), which skips a NULL term silently (a NULL dirty_air_tax_s on a closed row contributes nothing, not an error), so closure to the relative gain would be silently off by that row's value; the test (4) in assert_isolation_cumulative_identity guards non-NULL, so this is covered upstream.
   - LEFT JOINs to int_stint_end_regime and int_pit_strategy_value on stint_id assume one row per stint (no fan-out guard here; a duplicate would double the 'all' and phase rows, the unique tests on stint_phase_id would catch it).
   - The seed's grade is placeholder 'unvalidated' ("until WI-16b fills it"): trust labels then read 'unvalidated', confidence_pct NULL, so the SE/lambda machinery exists but is not published as confidence. Verdict: QUESTIONABLE (same SE-independence caveat).
5. Fills: COALESCE(pa.n_pair_laps, 0), n_relative_laps, n_teammate_pair_laps = 0 (counts). dirty_air_lap_share excludes NULL laps (documented). No NULL-to-0 in sums except the identity macro's COALESCE(SUM(pace_gap), 0.0) which is guarded by n > 0.
6. Tests: unique + unique_combination, not_null x13, accepted_values x3, relationships x4; singular assert_isolation_cumulative_identity, assert_isolation_phase_partition, assert_isolation_small_sample_nulls, assert_isolation_reliability_bounds.

## 17. fct_driver_isolation_race  (marts/fct_driver_isolation_race.sql)

1. Purpose: isolation ratings per driver-race with pure skill, relative pace, SE, lambda, confidence, identity split and context. Consumer: app export (facts), validation scripts.
2. Flow: fct_driver_isolation_lap, fct_driver_isolation_pair_lap, int_driver_isolation_stint_tyre (unreferenced CTE kept only to hold a DAG edge), seed method scores.
3. How: group laps by driver-race (grouping on car_iso_s etc. as constants); pure mean over non-extrapolated laps; pure SE = sqrt(sigma_w^2 / (n f)) using total race laps; relative as in the lap mart; tau^2 per season from rows with n >= 6.
4. Maths check:
   - QUESTIONABLE (lines 112-118, 145-150): at race grain SE_pure = sqrt(sigma_w^2/(n_pure_laps x f)) with the season neff factor f applied to the whole race's laps. The header says SEs "combine stints, which are independent", but the code does not combine per-stint variances; it treats the race as one stint-sized sample with a single f. If f is calibrated for one stint's autocorrelation this is a different number from the stint-combined SE. stint_parts and race_se_parts CTEs compute n_pure per stint and a count of stints but n_pure is never used. Dead code and a comment that does not match the code.
   - relative SE as in lap mart: pair-lap values across a race share peers and lap times; independence assumed.
   - GROUP BY on car_iso_s, car_term_source, sigma/f: relies on these being constant per driver-race; documented lesson F16 and PK-tested.
   - pure_skill_gain_s includes a declared per-season offset (var isolation_pure_season_offset_gain_s, currently {}), so currently no offset. Verdict: QUESTIONABLE (SE construction does not match its header).
5. Fills: COALESCE counts to 0 (n_pair_laps, n_relative_laps, n_teammate_pair_laps); none enter sums.
6. Tests: unique + not_null x12, relationships x3, accepted_values x3; singular assert_isolation_cumulative_identity, assert_isolation_small_sample_nulls, assert_isolation_reliability_bounds, assert_isolation_field_centring, assert_isolation_base_invariance. Value tests exist for identity and bounds, none recompute the SE.

## 18. fct_telemetry_deltas  (marts/fct_telemetry_deltas.sql)

1. Purpose: teammate corner-metric deltas (braking point, minimum speed, throttle point) per lap and corner. Consumer: app export (read specially, partitioned), assistant views.
2. Flow: int_corner_metrics, stg_laps. Nothing in-group reads it.
3. How: teammates = pairs of drivers with equal constructor in a race and driver_a < driver_b (from DISTINCT race, driver, constructor in stg_laps); corner metrics for each side; FULL OUTER JOIN on (race, pair, corner, lap_number); deltas = a - b, ROUND to 1/2/1 dp; NULL when either side or the metric is missing.
4. Maths: sign and unit correct (m, kph, m). NULL kept NULL (CO-22). Rounding is applied once at the end. Notes: pairs a driver with a teammate on the same lap number only; a lap on which one driver pitted or did not measure yields a NULL delta row, so row count is not equal to paired laps (by design). If three drivers share a constructor in one race (rare substitution), every pair is produced, which is consistent with "teammates". The entry DISTINCT would duplicate a pair only if a driver has two constructors in a race, which would need data corruption. Verdict: SOUND.
5. Fills: COALESCE(a.x, b.x) lines 82-98 are for key columns of the full outer join, not numeric fills. No fill on any delta.
6. Tests: unique_combination, not_null x6, relationships; singular assert_telemetry_deltas_teammates_only and assert_telemetry_deltas_null_when_side_missing (both value-level on the stated rules).

## 19. mart_corner_skill_driver  (marts/mart_corner_skill_driver.sql)

1. Purpose: season corner-phase skill (braking, mid-corner, exit) of each driver against a leave-one-driver-out car baseline, plus a z-scored index. Consumer: app export and corner-phase-skill page, assistant (queries.ts, seasonKinds.ts).
2. Flow: int_corner_skill_residuals, stg_laps, int_event_corrections, int_track_evolution. Nothing in-group reads it.
3. How: clean laps; car sums per (race, constructor, corner); LORO baseline = (car sum - driver sum)/(car n - driver n); per (driver, race, corner) deconf = driver mean - LORO baseline, winsorized to +/-1.0 s with IS NOT NULL guards; season mean over cells, SE = SD / sqrt(n cells), require >= 100 mapped cells; per-phase z-score only when the phase has >= 30 cells; index = sum of three z.
4. Maths check:
   - LORO and winsorization correct; NULL handling explicit (guards protect against LEAST/GREATEST skipping NULL).
   - QUESTIONABLE (lines 300-325): z = skill / STDDEV(skill) OVER season is not centred (no minus mean). The header and name say "z-scored". For two-driver cars the teammate pair sums to about 0 so the mean is near 0, but with 3-driver cars or unequal pairings the z is a scaled value, not a z. The SD is over drivers meeting the 100-cell floor only. Equal weights on the three phases, which are correlated, is a modelling choice.
   - QUESTIONABLE (lines 262-273): SE = STDDEV(cells) / sqrt(number of cells) assumes the cells (corner x race) are independent. All cells of a race share the same teammate baseline and track conditions, and a driver's cells within a race are correlated, so the SE is too small.
   - Cells are weighted equally regardless of the number of laps behind them (a 1-lap cell counts as much as a 30-lap cell); winsorization limits but does not solve it.
   - corner_skill_index sums the already-rounded z (line 343-344 rounds each z to 2 dp before summing); error at most 0.015. Rows with any phase below 30 cells have NULL index (not 0). Verdict: QUESTIONABLE.
5. Fills: COALESCE(dca.driver_sum_*, 0) inside the LORO numerator (lines ~125-143): used where the driver has no lap for that phase (the CASE requires car n > driver n), subtracting 0 for a driver who contributed nothing, which is correct arithmetic, not a default. No NULL-to-0 in the index.
6. Tests: unique_combination, not_null x18, relationships x2, between x4; singular assert_corner_skill_sign_convention, assert_corner_skill_phase_gate, assert_corner_skill_cell_winsorized (value-level on the stated rules).

## 20. fct_track_limits  (marts/new_data/fct_track_limits.sql)

1. Purpose: one row per deleted lap (race and qualifying) with raw reason and parsed turn. Consumer: only fct_track_limits_driver_session; not exported, no page.
2. Flow: stg_laps, stg_laps_qualifying (is_deleted). Read by fct_track_limits_driver_session.
3. How: UNION of is_deleted laps; is_track_limits = reason starts 'TRACK LIMITS'; turn_number via REGEXP_EXTRACT 'TURN (\d+)'; next-lap flag by '(NEXT LAP)'.
4. Maths: string parsing only; NULL turn when no turn in the text, raw text kept. Primary key deleted_lap_id = race_session_driver_lap (unique-tested). Verdict: SOUND.
5. Fills: none.
6. Tests: unique + not_null on deleted_lap_id; assert_track_limits_reconcile (counts reconcile with Bronze Deleted totals). 

## 21. fct_track_limits_driver_session  (marts/new_data/fct_track_limits_driver_session.sql)

1. Purpose: deleted-lap counts per driver, race and session with laps run as denominator; seasons with no deletion data (2018) are NULL with a reason. Consumer: none (scratch).
2. Flow: stg_laps, stg_laps_qualifying, fct_track_limits.
3. How: season_has_data = any deleted lap in the season; per-driver n_laps_run and n_deleted; LEFT JOIN track-limit counts; counts are NULL when the season has no deletion data, else COALESCEd to 0.
4. Maths: denominator and numerator share a grain. COALESCE(t.n_track_limits, 0) only fires inside a season that has deletion data (CASE guard), so a 0 there is a real zero. The "season has data" rule is per season, not per race, so a single race missing deletion ingest inside a season with deletions would read as zero deleted (the reconcile test compares to Bronze, which would not catch a Bronze gap). Verdict: SOUND.
5. Fills: lines 55-57 COALESCE(t.n_track_limits, 0), COALESCE(t.n_turns, 0) inside the guarded CASE; no sums.
6. Tests: unique + not_null on keys, accepted_values on the reason; assert_track_limits_reconcile (value-level reconciliation to Bronze).

## 22. fct_speed_traps  (marts/new_data/fct_speed_traps.sql)

1. Purpose: speed-trap/finish-line/intermediate max, median and n per driver-race-session over valid laps. Consumer: none (scratch).
2. Flow: stg_laps, stg_laps_qualifying.
3. How: GROUP BY (race, session, driver); MAX/MEDIAN FILTER(is_valid_lap); counts of readings and missing readings; ANY_VALUE(constructor_id ORDER BY constructor_id).
4. Maths: aggregates ignore NULL, counts show how many; missing is NULL not 0. Mixed units none (kph). ANY_VALUE ordered by constructor_id is deterministic but would pick one team for a driver who changed teams within a session (not possible within one session). Verdict: SOUND.
5. Fills: none.
6. Tests: unique + not_null; assert_speed_traps_missing_not_zero (checks a missing reading is NULL not 0).

## 23. fct_speed_traps_season  (marts/new_data/fct_speed_traps_season.sql)

1. Purpose: season roll-up of the speed trap per driver and per team. Consumer: none.
2. Flow: stg_laps, stg_laps_qualifying (valid laps).
3. How: UNION driver and team entity streams; MAX, MEDIAN, counts per (season, session, entity).
4. Maths: MEDIAN over laps pools all races (lap-weighted); the team stream includes every driver of that constructor, so a mid-season driver swap blends. n_valid_laps = COUNT(*) counts laps whether or not a reading exists, n_st_readings counts readings; consistent. entity_id for team uses the lap's constructor_id so a driver who changes teams is split correctly. Verdict: SOUND.
5. Fills: none.
6. Tests: unique + not_null on season_entity_id; assert_speed_traps_missing_not_zero.

## 24. fct_pit_stop_crosscheck  (marts/new_data/fct_pit_stop_crosscheck.sql)

1. Purpose: Jolpica pit stops beside FastF1 pit stops per driver-race with an agreement status. Consumer: none (scratch until AP-09 / AX-28).
2. Flow: stg_jolpica_pit_stops, stg_pits, stg_laps, source(bronze_f1.raw_results).
3. How: Jolpica ergast id mapped to the FastF1 abbreviation through Bronze results (DISTINCT race, driverid, abbreviation); FULL OUTER JOIN on (race, driver); status AGREE / COUNT_DIFFERS / LAPS_DIFFER / JOLPICA_RACE_MISSING / FASTF1_RACE_MISSING; lap lists compared as ordered strings.
4. Maths: comparing STRING_AGG of ordered in-lap numbers is a correct exact-set test. Risk: if raw_results holds two abbreviations for one ergast id in a race, the id_map DISTINCT would fan out Jolpica rows (not found, cannot check without data). Unmapped Jolpica rows keep '?<ergast id>' so they surface as COUNT_DIFFERS rather than being lost. Durations are kept in separate columns (two measures, not summed together). Verdict: SOUND.
5. Fills: COALESCE(m.driver_id, '?' || ergast_id) (a visible marker, not a number); COALESCE(fastf1_n_stops, 0) <> COALESCE(jolpica_n_stops, 0) in the comparison only.
6. Tests: unique + not_null on crosscheck_id, accepted_values on status. Shape only.

---------------------------------------------------------------------
## Cross-cutting notes

- ml_eligible (fct_lap_residuals.sql:106-111) is the shared lap filter for four marts but does not test driver_skill_residual_s non-NULL; counts and means in mart_race_driver_summary / mart_driver_season_summary therefore sit on slightly different lap sets (n_clean_laps vs the laps behind each mean).
- constructor_component_s = 0.0 fill (int_lap_residual_decomposed.sql:286) reaches constructor_rank in both summary marts and the ghost ego side; the flag constructor_pace_is_filled exists but no mart uses it.
- Uncertainty in this group is built by one of three methods: exact order-statistic CI (mart_race_driver_summary, sound), method-of-moments shrinkage with SE = sd/sqrt(n) (isolation marts, corner skill), delta-method-like variance propagation (ghost finish). The last two assume independence between laps or cells that are in fact autocorrelated, so their intervals are likely too narrow (isolation, corner) or loosely bounded (ghost). Not quantified here.
- Not checked (no warehouse reads allowed): how many rows each QUESTIONABLE/WRONG finding touches; uniqueness of upstream joins (int_stint_end_regime, int_pit_strategy_value, int_constructor_deg_sensitivity) beyond what tests/comments claim; int_era_normalized_driver_rating CI construction (out of group); cliff_plateau_s and cliff_ramp_frac macro bodies (not in macros/ by those names under compound_cliff_wear.sql; only the header was read).

---------------------------------------------------------------------
## Findings summary

### WRONG
1. fct_stint_features.sql:148-155 and 217-230 - end_of_stint_pace_falloff_s_per_lap slope: mean_x is over all 3 rows, mean_y and the numerator skip a NULL residual row, the denominator does not. A NULL residual among the last 3 laps gives a mis-scaled slope (x=1,2,3 with y3 NULL yields half the two-point slope); the n_laps < 3 gate counts rows, so it does not catch it. Extent not measured.

### QUESTIONABLE
1. fct_ghost_car_pace.sql:210-211 and 374-381 - ego's own constructor term 0.0-filled upstream (int_lap_residual_decomposed.sql:286) is left in the ego residual, then the host car is added; no ego-side prior flag (only host_constructor_pace_is_prior).
2. fct_ghost_car_pace.sql:445 vs header 70-71 - header says confidence < 0.05 is excluded, code keeps > 0.0; fct_ghost_race_finish.sql:102 then uses >= 0.3, so lap sets per scenario depend on host data volume.
3. fct_ghost_race_finish.sql:230-234 - SE inputs: lap_pace_sd uses predicted_lap_time_s including fuel and tyre trend (deterministic) as noise; cliff exposure se_shift x severity x active-fraction is not the derivative of the saturating ramp; ego coefficients treated independent across teammates. Header ties-by-finish-position (line 12) not in code (lines 250-253).
4. fct_cliff_prediction_features.sql:577-590 - surface_bulk_ratio COALESCEs each load to 0.0 inside the ratio; one NULL gives exactly 0.0 or 1.0, outside the stated range [0, 0.606].
5. fct_cliff_prediction_features.sql:552 - COALESCE(drift_s_per_lap, 0.0) silently makes detrended labels equal raw jumps for stints with no fitted drift (primary label next_5_lap_cumulative_jump_s uses it).
6. fct_cliff_prediction_features.sql:705-722 (legacy single-lap targets) - LEAD(...,1) without the no-hole guard; and 231-262 survival edge: NULL (not 0) n_reaching for a first-appearance cell gives weight 1.0 instead of the cap.
7. mart_driver_season_summary.sql:143-150 and mart_race_driver_summary.sql:156-163 - constructor_rank averages constructor_component_s including the 0.0 fill, biasing filled constructors to mid-field.
8. fct_driver_skill_features.sql:117-118 - AVG(proxy x w) / AVG(w) divides by weights of rows whose proxy is NULL; line 90 clean_lap_count counts laps with a NULL residual; line 213 COALESCE(strategic_divergence_share, 0.0) turns "no teammate row" into zero divergence.
9. mart_degradation_history_envelope.sql:97-101 vs 108-122 - fresh anchor by age_in_stint <= 2 but table indexed by lap_in_stint; n_observations >= 3 (line 162) lets p10/p90 stand on 3 points; lines 151-153 default coefficients 1.0 / 8.0 / 0.010 published as if fitted; era split puts 2022 onward in one era.
10. mart_corner_skill_driver.sql:300-325 - "z-score" is not centred (skill / SD only); lines 262-273 SE assumes independent cells though cells share the same teammate baseline.
11. fct_driver_isolation_race.sql:112-150 - header says per-stint SEs are combined, code uses total race laps with a single season f; stint_parts/race_se_parts unused. fct_driver_isolation_lap.sql:184-194, and _stint/_race tau^2 and relative SE assume independence across overlapping windows and shared peers.
12. mart_race_driver_summary.sql:69-75 - the order-statistic CI treats paired lap gaps as independent (formula and ranks verified correct); too-narrow interval in practice.
