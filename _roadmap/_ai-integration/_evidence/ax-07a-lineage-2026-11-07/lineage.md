# AX-07a: column-level lineage for v1 card sources (feeds HD13)

Date: 2026-11-07. Read-only analysis of `transform/` at the working tree (HEAD `ed57245` plus uncommitted roadmap edits only; no `transform/` edits). How it was run, and what was not checked: `PROVENANCE.txt` in this folder.

## 0. Classes used

| Class | Test (HD13, owner, 2026-11-07) |
| :-- | :-- |
| **T** (TRANSFORM-ONLY) | No path from `int_lap_air_state`, `int_dirty_air_tax_component`, `theta_air`, `int_driver_isolation_lap_panel`, WC or ML reaches the column's value or its row filter. |
| **T-F** (TRANSFORM-ONLY-WITH-FILTER-CAVEAT) | `int_lap_air_state` reaches the column only by choosing which laps count (for example, through the clean-air eligibility rule of the field-pace base). The card carries a caveat. |
| **DA** (DIRTY-AIR-DEPENDENT) | The value contains `dirty_air_tax_s` (θ_air 0.331 s/lap × lagged dirty-air share), or anything built from `driver_skill_residual_s`, `total_explained_s` or the isolation panel `y_s`. Held in v1. |
| **TRAFFIC** | The value is a traffic or exposure quantity: an air-state share, a gap, proximity, or a WC output. Held in v1. |
| **ML** | Anything from `mart_degradation_predictions`, `app/public/models/*`, or a column that is an ML training target. Held in v1. |

The SQL turned up three cases that HD13 does not name. Each needs its own owner call (section 6):

- **[S]**: the value includes fitted coefficients from `compound_cliff_params`. That seed is fitted *offline* on lap times with a separate dirty-air penalty removed (θ_time ≈ 0.0042 s per second spent within 1.5 s of the car ahead). This is **not θ_air**. Columns marked [S] are T or T-F under the literal text of HD13.
- **[R]**: rows are chosen by a flag computed from `driver_skill_residual_s`, which contains the tax. The value itself carries no tax. In the tables below I mark these **DA (filter)**, which is the conservative reading.
- **[A]**: an air-state *measurement* (gap or share) is used as a value. It is not the tax. Marked **TRAFFIC**.

## 1. Headline verdicts

| Question | Verdict | Proof (file:line, under `transform/models/` unless noted) |
| :-- | :-- | :-- |
| `mart_race_driver_summary.rating_s` | **T-F** | `rating_s = int_driver_race_skill_loro.driver_skill_loro_s` (`marts/mart_race_driver_summary.sql:55`). That column is `MEDIAN(own.lap_time_s - mate.lap_time_s)` over paired clean laps (`intermediate/int_driver_race_skill_loro.sql:185,202,273`). It reads `int_lap_fuel_state.lap_time_s` only and never reads a residual, the field curve or the tax (header :12-15, :128-130). Air state enters only through the rain filter `COALESCE(e.rainfall_flag,FALSE)=FALSE` (:156), which joins `int_track_evolution`. That model has rows only for field-pace cells that are not thin (`intermediate/int_track_evolution.sql:22`), and those cells count only free-air and tow laps (`intermediate/int_field_pace_curve.sql:234,277`). |
| rating_s inputs | **T** / **T-F** | `int_lap_fuel_state.lap_time_s` is T (valid laps only, `intermediate/int_lap_fuel_state.sql:48`). `int_event_corrections.correction_weight` is T. `int_track_evolution.rainfall_flag` is T-F (row coverage, above). `stg_laps.constructor_id` is T. |
| rating_s interval `ci_low` / `ci_high` | **DA** | `lap_se_s = STDDEV(driver_skill_residual_s)/SQRT(n)` (`marts/mart_race_driver_summary.sql:29-30,105-106`). The residual subtracts `dirty_air_tax_s` (`intermediate/int_lap_residual_decomposed.sql:363-367`). The point estimate can be quoted under T-F, but this interval cannot. It is also the SE of a different statistic (the residual mean, not the paired median). |
| teammate gap (`teammate_gap_s`, race mart) | **T-F** | `CASE WHEN t.teammate_id IS NOT NULL THEN k.rating_s END` (`marts/mart_race_driver_summary.sql:109`). The teammate is picked by join on `ratings`, with `n_clean_laps` (a T count of `ml_eligible` laps) as tie-break (:67-84). |
| teammate gap (season mart) | **T-F** | `marts/mart_driver_season_summary.sql`: `rating_s = era_adjusted_rating` and `teammate_gap_s = rating_s` (ratings CTE, final SELECT). Primary team and teammate come from `ml_eligible` lap counts (T). `teammate_gap_rank` and `_percentile` are also T-F, but CO-01/T4 dropped the race-level rank as misleading; that is a presentation question. |
| field pace (`int_field_pace_curve`, all four app columns) | **T-F [S]** | Clean-air eligibility `a.air_state_dominant IN ('free_air','tow_zone')` (`intermediate/int_field_pace_curve.sql:234`). There is no tax term. The base subtracts `expected_compound_pace_s` (:205), which is seed-fitted, hence [S]. `low_sample_flag` (:277) and `eligible_lap_count` (:258) are counts of the filtered set. |
| corner skill (`mart_corner_skill_driver`, all app columns incl. `*_se_s`) | **T-F** | Inputs are `int_corner_skill_residuals`, which come from telemetry corner metrics and have no air-state or tax upstream (model-level, section 2). Air state enters only through the rain filter on `int_track_evolution` (`marts/mart_corner_skill_driver.sql:61-62,96-97`). The "residual" in the name is a corner-level telemetry residual, not `driver_skill_residual_s`. |
| pit-stop stint values (observed) | **T** | `actual_pit_lap` comes from `stg_pits` (`intermediate/int_pit_strategy_value.sql:144,454`). `pit_lane_loss_s`, `pit_loss_source` and `pit_loss_imputed_flag` come from `int_pit_loss_circuit`, which has no flagged upstream (:121,132,479-481). `stint_length_laps`, `compound`, `starting_tyre_age_laps`, `stint_end_cause`, `is_censored_stint` and `reached_flag` are T (`marts/fct_stint_features.sql:34-36,57`). |
| pit optimum and opportunity cost | **T [S], HELD (D9)** | The cost curve uses only the compound seed, pit loss, the hazard and weather (`intermediate/int_pit_strategy_cost_curve.sql:149,207,238,280`). There is no air state and no tax. It stays held for `PIT_CALL_REPRODUCTION_RATE` and is not reclassified. |
| pit verdict `strategy_verdict` / `pit_decision_class` | **TRAFFIC [A] + HELD** | The `undercut_forced` branch (`intermediate/int_pit_strategy_value.sql:517-522`) uses `first_undercut_threat_lap`. That is the minimum of `int_lap_air_state.min_gap_s` (:150-166, :477), a gap value rather than a filter. |
| era ratings (`era_adjusted_rating`, `_ci_low_s` / `_ci_high_s`) | **T-F** | `era_adjusted_rating = shrunk_residual_s` (`intermediate/int_era_normalized_driver_rating.sql:154`). That comes from `int_driver_season_ratings` (:32-35), whose only input is `driver_skill_loro_s`. The word "residual" in these column names is a historical name; the value is the paired teammate gap. The CI is computed inside the same chain (:178-179). |
| `fct_lap_residuals` fuel / compound / constructor components | **T / T [S] / T-F** | These are *not* residualised against the tax in SQL. `fuel_component_s = weight_penalty_s` (`intermediate/int_lap_residual_decomposed.sql:226`). `compound_component_s = expected_compound_pace_s` (:229). `constructor_component_s = int_constructor_structural_pace` (:269-270), whose panel is `lap_time_s - field_pace_smoothed_s` with no tax (`intermediate/int_constructor_structural_pace.sql`, clean_panel). The tax is added only in `total_explained_s` (:357) and subtracted only in `driver_skill_residual_s` (:367). **This conflicts with HD13's listing; see section 6, Q1.** |

## 2. Model level (from the manifest)

`dbt parse` on a scratch copy produced the manifest. Walking `depends_on.nodes` gives the transitive upstream of each model (script and JSON: `PROVENANCE.txt`). Columns: **air** means `int_lap_air_state` is upstream; **tax** means `int_dirty_air_tax_component` is upstream; **iso** means `int_driver_isolation_lap_panel` is upstream.

| Source model (card or app) | air | tax | iso | Model-level reading | Column-level result (section 3) |
| :-- | :-: | :-: | :-: | :-- | :-- |
| `race_caution_timeline` (export view over `int_stint_geometry`, `scripts/export_app_data.py:122-161`) | – | – | – | clean | T |
| `int_sc_hazard_history` | – | – | – | clean | T |
| `int_compound_cliff_predicted`, `dim_compounds_season` | – | – | – | clean | T [S] |
| `int_synthetic_teammate` | – | – | – | clean | T [S] (design 2.4 said T*) |
| `int_lap_fuel_state`, `int_stint_geometry`, `int_lap_thermal_proxy`, `int_stint_end_regime`, `int_pit_loss_circuit`, `int_pit_strategy_cost_curve`, `int_corner_skill_residuals`, `int_qualifying_*` (quali chain) | – | – | – | clean | T (cost curve [S]) |
| `int_field_pace_curve` | ✓ | – | – | air | T-F [S] |
| `int_track_evolution` | ✓ | – | – | air | T-F [S] |
| `int_constructor_structural_pace`, `int_circuit_x_constructor_interaction` | ✓ | – | – | air | T-F [S] |
| `int_driver_race_skill_loro`, `int_driver_season_ratings`, `int_era_normalized_driver_rating`, `int_driver_circuit_affinity`, `int_driver_circuit_era_affinity` | ✓ | – | – | air | T-F (see the Q4 note on `driver_skill_field_s`) |
| `mart_corner_skill_driver` | ✓ | – | – | air | T-F |
| `int_pit_strategy_value` | ✓ | – | – | air | mixed: T / TRAFFIC / HELD |
| `int_lap_residual_decomposed`, `fct_lap_residuals` | ✓ | ✓ | – | tax | mixed, per column |
| `int_lap_anomaly_flags` | ✓ | ✓ | – | tax | mixed, per column |
| `int_qualifying_decomposed` | ✓ | ✓ | – | tax | mixed (race side DA) |
| `int_tyre_surface_vs_bulk_decoupling` | ✓ | ✓ | – | tax | mixed |
| `fct_stint_features` | ✓ | ✓ | – | tax | mixed, per column |
| `fct_cliff_prediction_features` | ✓ | ✓ | – | tax | mixed, per column |
| `int_lap_telemetry_aggregates` | ✓ | ✓ | – | tax (false positive) | T. It reads `int_lap_anomaly_flags` only for the lap spine and the in/out-lap flags (`intermediate/int_lap_telemetry_aggregates.sql:185-197`). |
| `mart_race_driver_summary`, `mart_driver_season_summary`, `mart_metric_benchmark` | ✓ | ✓ | – | tax | mixed, per column |
| `fct_ghost_car_pace`, `fct_ghost_race_finish`, `fct_driver_skill_features`, `int_constructor_deg_sensitivity`, `int_sector_residual_decomposed`, `int_power_law_lap`, `mart_degradation_history_envelope` | ✓ | ✓ | – | tax | DA on modelled columns (ghost pace adds `driver_skill_residual_s` and `dirty_air_tax_s`, `marts/fct_ghost_car_pace.sql:357-359`) |
| `fct_driver_isolation_*`, `int_driver_isolation_*`, `int_constructor_car_fe_isolation` (offline fit on `y_s`) | ✓ | ✓ | ✓ | tax+iso | DA. `x_s = lap_time_s - compound - dirty_air_tax_s` (`intermediate/int_driver_isolation_lap_panel.sql:238,399`). The FE fit reads `y_s` (`transform/tasks/coefficients/fit_constructor_car_fe.py:310-319`). |
| `int_constructor_car_fe` (offline fit, `fits.constructor_car_fe`) | (✓) | – | – | not in manifest, offline fit | T-F. The fit panel is fuel state, field pace, corrections and rainfall, with no tax (`transform/tasks/coefficients/fit_constructor_car_fe.py:130-160`). |

θ_air enters the graph at exactly two places: `intermediate/int_dirty_air_tax_component.sql:326-373` (`var('theta_air_label_value')`, applied as `theta_air × dirty_air_share_lag1` clamped to [0, 5]) and `intermediate/int_driver_isolation_lap_panel.sql:119,151-153`. `int_lap_normalized_pace` (θ_time) is a dbt leaf. It reaches the warehouse only through the offline compound-cliff fit ([S]).

No dbt model carries WC (wake-calibration) output: `tasks/wake_calibration/` is Python only. No dbt model reads an ML artefact. In dbt, TRAFFIC is therefore only the air-state and proximity exposure columns, and ML is only the training-target columns of `fct_cliff_prediction_features`.

## 3. Column level, per card source

### 3.1 `mart_race_driver_summary` (results kind plus rating marts; grain driver × race)

| Column | Class | Path |
| :-- | :-- | :-- |
| `driver_id`, `race_id`, `race_year`, `circuit_id`, `constructor_id` | T | keys (:99-110, :128) |
| **row set** | T-F | Rows are drivers with a non-null `driver_skill_loro_s` (:57, :120). In the scratch build that is 3,138 of 3,275 driver-races. Results columns are T, but a driver with no paired teammate lap is missing from this mart. |
| `rating_s` | **T-F** | section 1 |
| `ci_low`, `ci_high` | **DA** | :29-30, :105-106 |
| `n_clean_laps` | T | count of `ml_eligible` laps (:23). `ml_eligible` uses correction weight, compound and constructor bounds, and a lap-time check only (`marts/fct_lap_residuals.sql`, final expression). It is not the rating's sample: `paired_lap_count` in `int_driver_race_skill_loro` is, and the mart does not carry it. |
| `n_drivers` | T-F | count of rated drivers (:63) |
| `teammate_id`, `teammate_gap_s` | T-F | :67-84, :109 |
| `constructor_rank` | T-F [S] | rank of `AVG(constructor_component_s)` (:86-95) |
| `mean_fuel_component_s` | T | :25 |
| `mean_compound_component_s` | T [S] | :26 |
| `mean_constructor_component_s` | T-F [S] | :27 |
| `mean_dirty_air_tax_s` | **DA (price)** | :28 |
| `avg_lap_time_s` | T | :24 |
| `laps_completed` | T | `COUNT(*)` of `fct_lap_residuals` rows (:37). Those are *valid timed laps* (`int_lap_fuel_state.sql:48`), not the classified laps completed. Fix the label or the source before a results card uses it. |
| `positions_gained`, `has_dnf` | T | `stg_results` (:42-50) |

### 3.2 `mart_driver_season_summary` and `mart_metric_benchmark`

- Season: `rating_s`, `ci_low`, `ci_high`, `n_races`, `teammate_gap_s`, `teammate_gap_rank`, `teammate_gap_percentile` and `n_drivers` are **T-F** (era chain). `constructor_rank` and `mean_constructor_component_s` are T-F [S]. `mean_fuel_component_s` is T. `mean_compound_component_s` is T [S]. `mean_dirty_air_tax_s` is **DA (price)**.
- Benchmark (long format, one row per metric): the `lap_time_s` and `fuel_component_s` rows are T. The `compound_component_s` rows are T [S] and the `constructor_component_s` rows T-F [S]. The `driver_skill_residual_s` and `dirty_air_tax_s` rows are **DA**. A card has to filter on `metric_name`.

### 3.3 `fct_lap_residuals` (wide)

| Columns | Class | Path (`intermediate/int_lap_residual_decomposed.sql` unless noted) |
| :-- | :-- | :-- |
| `lap_id`, `stint_id`, `race_year`, `race_id`, `driver_id`, `constructor_id`, `lap_number`, `position`, `compound`, `age_in_stint`, `lap_in_stint`, `stint_length_actual`, `fuel_mass_kg`, `driver_debut_year`, `pu_family` | T | stint geometry, stg_laps, dims |
| `lap_time_s`, `weight_corrected_lap_time` | T | `int_lap_fuel_state` (:90-91) |
| `fuel_component_s` | T | :226 |
| `compound_component_s`, `expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff`, `ambient_temp_delta` | T [S] | :229-233 (`int_compound_cliff_predicted`) |
| `base_track_pace_s`, `pace_delta_s` | T-F [S] | :241, :343 (field pace) |
| `rubber_component_s`, `ambient_component_s`, `track_unexplained_s` | T-F [S] | :245-247 (`int_track_evolution`, built on field pace) |
| `track_temp_c`, `rainfall_flag` | T-F | :248-249. These are weather values, but NULL where `int_track_evolution` has no row. |
| `constructor_component_s`, `constructor_component_se_s`, `_ci_low_s`, `_ci_high_s` | T-F [S] | :269-276 |
| `correction_class`, `correction_weight`, `is_safety_car_lap`, `is_vsc_lap`, `is_red_flag_lap`, `is_restart_lap`, `is_pre_controlled_lap`, `is_local_yellow_lap`, `is_major_outlier_lap` | T | `int_event_corrections` (:302-314) |
| `ml_eligible` | T | `marts/fct_lap_residuals.sql` (final expression) |
| `total_explained_s` | **DA** | :354-357 |
| `driver_skill_residual_s` | **DA** | :363-367 |
| `dirty_air_tax_s`, `dirty_air_tax_se_s`, `cumulative_dirty_air_tax_race_s` | **DA (price)** | :285-297 |

Design 2.5's `qv_laps` ("observed columns only") should be limited to the T rows above. Note that `rainfall_flag` there is T-F.

### 3.4 `fct_stint_features` (wide)

| Columns | Class | Path (`marts/fct_stint_features.sql`) |
| :-- | :-- | :-- |
| `stint_id`, `driver_id`, `race_id`, `race_year`, `constructor_id`, `stint_length_laps`, `compound`, `starting_tyre_age_laps`, `short_stint_flag` | T | :34-36, constructor_per_stint |
| `cumulative_thermal_load_end` | T | :74 (`int_lap_thermal_proxy`) |
| `is_censored_stint`, `end_regime`, `stint_end_cause`, `end_cause_confidence`, `is_stint_life_censored`, `reached_flag` | T | :57 (`int_stint_end_regime`: stint geometry plus `stg_results`) |
| `is_fresh_tyre_raw`, `clean_laps_to_cut`, `slope_to_cut_s_per_lap`, `mean_clean_pace_s`, `cut_reason`, `slope_reliable` | T | run_fit, :182-185 (`weight_corrected_lap_time`, valid laps) |
| `cumulative_dirty_air_tax_s` | **DA (price)** | :92, :226 |
| `cliff_lap_in_stint` | **DA** | :105, the first `cliff_candidate_flag`. That flag is MAD on `driver_skill_residual_s` (`intermediate/int_lap_anomaly_flags.sql:247-252`). The pit-strategy Gantt shows this column. |
| `tyre_management_score` | **DA** | :247 (`end_residual_s`) |
| `end_of_stint_pace_falloff_s_per_lap` | **DA** | :207 |
| `pit_decision_class` | **TRAFFIC [A] + HELD** | :156 (`strategy_verdict`) |

Design 2.5's `qv_stints` lists `pit_decision_class` as a dimension. It should not be one: it is held and TRAFFIC. The list also excludes `cliff_lap_in_stint`, which is correct.

### 3.5 `fct_cliff_prediction_features` (wide)

| Columns | Class | Path (`marts/fct_cliff_prediction_features.sql`) |
| :-- | :-- | :-- |
| keys, `lap_number`, `lap_in_stint`, `age_in_stint`, `compound`, `fuel_mass_kg` | T | residuals spine (:20-35), geometry columns only |
| `compound_grip_peak`, `compound_wear_gradient`, `compound_optimal_temp_low` / `_high`, `compound_cliff_onset_laps`, `compound_cliff_severity` | T [S] | compound_params (:332) |
| `expected_compound_pace_s`, `expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff`, `ambient_temp_delta` | T [S] | cliff (:46-54) |
| `push_residual`, `cumulative_push_load_surface` / `_bulk`, `baseline_observations_n`, `surface_bulk_ratio` | T | `int_lap_thermal_proxy.sql:127` (stint baseline minus weight-corrected lap time, not the skill residual) and :572-590 |
| `corner_*` (input and drift, 20 columns, plus coverage) | T | `int_lap_corner_inputs` / `int_lap_corner_drift`, from corner metrics |
| `quali_push_laps_n`, `quali_constructor_pace_mean_s`, `quali_constructor_pace_se_mean_s`, `quali_pace_delta_best_s`, `quali_ratio_to_segment_best_min`, `quali_skill_session_avg_s`, `quali_segments_contested_n` | T [S] | `int_qualifying_driver_summary.sql:101-107`. Quali-side only; quali tax is `0.0 AS dirty_air_tax_s` (`int_lap_residual_decomposed_qualifying.sql:134`). |
| `circuit_*_hazard_per_lap`, `circuit_hazard_prior_*` | T | `int_sc_hazard_history` (:214) |
| `track_energy_index`, `circuit_abrasiveness_index` | T | dim_circuits (:351) |
| telemetry block (`n_gear_changes` … `lift_coast_share`) | T | `int_lap_telemetry_aggregates` (false-positive flag, section 2) |
| `event_flag_any` | T | :523 (`correction_weight < 1.0`) |
| `survival_weight` | T | :247-298, :564-568. Counts of stints reaching each lap; no residual. |
| `is_rain_lap` | T-F | from `int_lap_anomaly_flags`, which takes `rainfall_flag` from the residual chain, which takes it from `int_track_evolution` |
| `dirty_air_share_lap`, `dirty_air_thermal_load_surface` / `_bulk`, `air_state_dominant` | **TRAFFIC [A]** | :67-74, :397-400, :856-858 |
| `share_lap_within_1s` / `_2s`, `share_lap_in_train`, `share_lap_behind_within_1s`, `time_within_1s`, `gap_ahead_min_s` / `_median_s`, `ahead_identity_stability`, `n_distinct_cars_ahead_3s` | **TRAFFIC [A]** | `int_lap_proximity` (:83-95). This is the position channel; no tax. |
| `anomaly_class` | **DA [R]** for `mistake` / `clean_cliff`; T for `event_driven` / `conditions` / `normal`-vs-event | `int_lap_anomaly_flags.sql:221-245` (MAD branch :234-243) |
| `cliff_candidate_flag` | **DA** | `int_lap_anomaly_flags.sql:247-252` |
| `next_lap_degradation_jump_s`, `_detrended_s`, `next_3_lap_*`, `next_5_lap_cumulative_jump_s`, `laps_until_cliff_class` | **DA + ML (training targets)** | :650-665, :699-813 (LEAD of `driver_skill_residual_s`) |
| `is_training_eligible` | **DA [R]** | :1012-1021 (`anomaly_class NOT IN ('mistake',…)`) |

### 3.6 T-feature app columns (registered queries)

| Feature · query · column | Class | Path |
| :-- | :-- | :-- |
| race-control · timeline / pooled-rates · all | T | `race_caution_timeline` comes from `int_stint_geometry` (`scripts/export_app_data.py:122-161`) |
| race-control · circuit-hazard · `prior_races_n`, `prior_racing_laps`, `*_hazard_per_lap_shrunk` | T | `int_sc_hazard_history` comes from `stg_track_status` and `stg_laps` only. NULL for 2018 (AX-07 finding 3). |
| field-pace · race · `field_pace_smoothed_s`, `field_pace_trimmed_mean_s`, `eligible_lap_count`, `low_sample_flag` | T-F [S] | section 1 |
| quali-vs-race · season · `quali_skill_s` | T [S] | `int_qualifying_decomposed.sql:68-91,142` |
| quali-vs-race · season · `delta_s`, `race_skill_s` | **DA** | `race_skill_race_avg_s = AVG(driver_skill_residual_s)` (:96-107). Delta is at :145-147. Note `COALESCE(race_avg, 0.0)` (:146): a missing race side gives delta = quali skill, not NULL. |
| quali-vs-race · season · `n_races` | T | count. The `quali_traffic_flag IS NOT TRUE` filter is a no-op because the flag is a NULL constant (:154). |
| corner-phase-skill · season · all (incl. `*_se_s` used as `se_1`) | T-F | section 1 |
| driver-workload · season · `avg_stint_age_laps`, `avg_push_residual` | value T, **filter DA [R]** | `WHERE is_training_eligible` drops `mistake` laps (`fct_cliff_prediction_features.sql:1012-1021`) |
| driver-workload · `avg_dirty_air_share` | **TRAFFIC [A]** | `dirty_air_share_lap` |
| driver-workload · `cliff_flag_pct` | **DA** | `cliff_candidate_flag` |
| driver-workload · `total_laps` | **DA [R]** | filter |
| tyre-cliff-survival · profiles · all `compound_*` | T [S] | `dim_compounds_season`, from the seed |
| tyre-cliff-survival · race-compounds / stints · `stint_count`, `stint_length`, `cliffed`, `degradation_s` | values T [S], **filter DA [R]** | `anomaly_class IN ('normal','clean_cliff')` drops `mistake` laps |
| tyre-recovery · all · `avg_surface_bulk_ratio` | T | `int_tyre_surface_vs_bulk_decoupling.sql` with_ratio |
| tyre-recovery · `avg_recovery_prob_pct`, `avg_thermal_s`, `post_cliff_laps` | T [S] | :155-156, :160-169, row filter `cliff_onset_passed` (:171) |
| tyre-recovery · `recovery_rate_pct` | **DA** | `recovery_flag` compares the next laps' `driver_skill_residual_s` (:105-106, :140-150) |
| data-quality · season · `total_laps`, `neutralised_laps`, `out_in_laps`, `major_outlier_laps` | T | `int_lap_anomaly_flags` pass-through of `int_event_corrections` and geometry |
| data-quality · `rain_laps` | T-F | `is_rain_lap = COALESCE(rainfall_flag,FALSE)` (`int_lap_anomaly_flags.sql:216`). It undercounts where `int_track_evolution` has no row (section 5). |
| data-quality · `usable_laps`, `pct_usable` | **DA [R]** | `WHEN mad_score > 3.0 THEN FALSE` (`int_lap_anomaly_flags.sql:262`); MAD is computed on `driver_skill_residual_s` (:77-144) |
| data-quality · `anomaly_laps` | **DA [R]** | mixes T branches with the MAD branches (:221-245) |
| pit-strategy · gantt · `start_lap`, `end_lap`, `stint_length_laps`, `pit_lane_loss_s` | T | section 1 |
| pit-strategy · gantt · `cliff_lap_in_stint` | **DA** | `fct_stint_features` :105 |
| pit-strategy · gantt · `optimal_pit_lap_in_stint`, `overrun_laps`, `opportunity_cost_s`, `optimal_pit_lap_confidence` | T [S], HELD | section 1 |
| pit-strategy · gantt · `verdict` | TRAFFIC [A], HELD | section 1 |
| pit-strategy · race-summary · `total_laps` | T | `MAX(lap_number)` from `fct_lap_residuals` |
| results (no page) · `fct_ghost_race_finish.actual_finish_position`, `actual_dnf_cause` | value T; **row set DA** | Values come from `stg_results` (`marts/fct_ghost_race_finish.sql:125-150`). Rows are left-joined onto ghost-scenario rows built from the taxed residual chain (:295-345). Source results from `stg_results` or the race mart instead. |

### 3.7 Rows marked T* in design 2.4 that the lineage moves

| Source | Design 2.4 | Lineage |
| :-- | :-- | :-- |
| rating marts: `rating_s`, `teammate_gap_s` (race and season), era ratings and their CIs, `int_driver_circuit_affinity` | T* | **T-F**. The race-mart `ci_*` stay **DA**. |
| `int_synthetic_teammate` (`driver_skill_proxy_s`) | T* | **T [S]**. Weight-corrected lap time versus the teammate plus the compound offset (`intermediate/int_synthetic_teammate.sql:132-133`). Nothing flagged upstream. |
| `int_constructor_structural_pace(_qualifying)`, `int_circuit_x_constructor_interaction` | T* | **T-F [S]**. The CO-30 dirty-air pricing is in the *isolation* panel, not here. |
| `int_track_evolution` | T* (check) | **T-F [S]** |
| `constructor_component_s` in `fct_lap_residuals` (team averages) | T* | **T-F [S]**. The `avg_driver_skill_residual_s` and `avg_dirty_air_tax_s` on that page stay DA. |
| `int_driver_circuit_era_affinity` (`driver_skill_field_s`, ghost standings) | T* | **T-F [S]**, given the car-FE fit panel in section 2. See Q4. |
| driver-workload | T | **mostly DA [R] / TRAFFIC**, as shipped |
| tyre-recovery-forecast | T (check) | mixed: `recovery_rate_pct` is **DA** |
| data-quality-audit | T | mixed: usable and anomaly counts are **DA [R]** |
| quali-vs-race-skill | T (check) | `quali_skill_s` is T [S]; `delta_s` and `race_skill_s` are **DA** |

## 4. What stays held, whatever HD13 adds

- Every `dirty_air_tax*` column, `mean_dirty_air_tax_s`, `cumulative_dirty_air_tax*`, `total_explained_s`, `driver_skill_residual_s` and everything built from them: race-lost and waterfall skill bars, sector decomposition, ghost car and ghost finish predictions, driver-consistency, wet-race, `fct_driver_skill_features`, the isolation marts, `int_constructor_car_fe_isolation`, `mart_degradation_history_envelope`, and the power-law marts.
- `fct_cliff_prediction_features` targets: ML label and DA.

## 5. Size of the T-F caveat (measured on the scratch build)

The rain filter in `int_driver_race_skill_loro:156`, `int_constructor_structural_pace` (clean_panel), `mart_corner_skill_driver:97` and the offline car-FE panel all LEFT JOIN `int_track_evolution`. That table has rows only where the field-pace cell is not thin, and thin depends on the clean-air count. Of 161,040 valid timed laps, **11,588 have no `int_track_evolution` row**. **1,018 of those are laps that `stg_weather` marks as raining**. Those laps therefore pass the "dry laps only" filter in every panel above. Not all missing rows come from the air-state rule; SC and thin cells also cause them, and the two causes were not separated. The card caveat should say: "Laps are chosen with a clean-air rule from the gap-to-car-ahead classification; on about 0.6 % of laps a rain filter that depends on it does not apply." This also looks like a latent defect, independent of HD13: it is worth a fix item that joins `stg_weather` directly.

The same build has 9,151 `mistake` laps (5.7 %), 2,990 `clean_cliff` laps, 21,901 laps with `mad_score > 3`, and 46,483 laps with a positive tax, out of 161,040. Not measured: how many [R] classifications would flip if the residual were computed without the tax.

## 6. Owner questions (HD13 follow-ups)

1. **Components "residualised against" the tax.** In SQL, `fuel_component_s`, `compound_component_s` and `constructor_component_s` (race-lost bars, team averages, the `mean_*_component_s` mart columns) contain no tax. They sit beside it in an identity whose remainder (skill) does contain it. Under HD13's literal test they are T, T [S] and T-F [S]. Should they be held anyway as members of the decomposition (recommended for the race-lost and waterfall pages, where they are shown stacked against the skill bar), or quoted as standalone numbers?
2. **[S] θ_time in the compound seed.** `compound_cliff_params` is fitted on `int_lap_normalized_pace` (lap time − θ_time × seconds in dirty air; `intermediate/int_lap_normalized_pace.sql:7,191`; `transform/tasks/coefficients/fit_compound_cliff.py:218-242,277,377-387`). That is a second dirty-air correction, unvalidated, and different from θ_air. It reaches every compound term, field pace (:205), the pit optimum and the synthetic teammate. Is it T with a caveat (recommended: its effect is second-order and enters through fitted coefficients, not a per-lap price), or held? If it is held, the live T set shrinks to race-control, hazard, the observed pit values, the rating chain (`rating_s`, teammate gap and era ratings, none of which reads the compound term), corner skill and results. Field pace, compound profiles, quali skill, recovery probability, structural pace and the synthetic teammate would then join the held set.
3. **[R] filters on the taxed residual.** `anomaly_class` (`mistake` / `clean_cliff`), `cliff_candidate_flag`, `usable_for_modelling` and `is_training_eligible` choose laps using MAD on `driver_skill_residual_s`. HD13 exempts air-state filters but says nothing about filters built on the tax. This item treats them as DA (filter). The alternative is T-F with a second caveat. A cheaper fix is to re-express the workload and tyre-cliff queries with `event_driven` / `conditions` exclusions only, which makes them T.
4. **`driver_skill_field_s`** (ghost standings affinity) depends on the offline `fits.constructor_car_fe`. The fit code reads no tax (`transform/tasks/coefficients/fit_constructor_car_fe.py:130-160`), but the parquet it wrote was not re-derived here.
5. **[A] exposure values** (`dirty_air_share_lap`, proximity shares, `min_gap_s` → `undercut_threat_lap`). These are measured, not priced. This item puts them in TRAFFIC because WC redefines exposure (design 2.5 already keeps `int_lap_air_state` out of the catalogue). Confirm.
