# Transform CI & Physics Testing

The Continuous Integration (CI) pipeline for the **Off The Pace** transform layer is unusually strict because it acts as a physics engine mapped onto a dbt (data build tool) database. 

While the architecture follows a standard Medallion setup (Staging $\to$ Reference $\to$ Intermediate $\to$ Marts), the **424 tests** enforced in CI guarantee that the physical models remain mathematically sealed, physically logical, and statistically sound against real-world chaos.

---

## 1. The "Identity-Closure" Tests
In this pipeline, lap time is treated with the same mathematical strictness as the conservation of mass. If a pull request changes how fuel weight is calculated, it doesn't just change fuel—it affects the entire Seven-Term Identity.

The CI runs specific SQL macros (such as `assert_lap_7term_identity.sql`) on every single lap in the test fixtures. If the sum of the physics components (fuel, compound, rubber, ambient, constructor, dirty air) plus the driver skill residual deviates from the true lap time by more than **0.0001 seconds**, the build outright fails. The identity is empirically sealed to $1.4 \times 10^{-14}\text{s}$ machine precision.

### Detailed Test Directory
* **`assert_residual_decomposition_identity.sql`**: Validates the 6-term lap residual closure on `int_lap_residual_decomposed`.
* **`assert_lap_7term_identity.sql`**: Validates the full 7-term lap residual (with dirty air extracted) on `int_lap_residual_decomposed`.
* **`assert_qualifying_7term_identity.sql`**: Validates the 7-term identity specifically for qualifying laps on `int_qualifying_decomposed`.
* **`assert_sector_residual_identity.sql`**: Ensures the residual identity holds at the sector grain on `int_sector_residual_decomposed`.
* **`assert_sector_aggregates_to_lap.sql`**: Validates that sector-level physics components perfectly aggregate back into the full lap components (Placeholder).
* **`assert_corner_closure.sql`**: Ensures corner-grain closure: the sum of braking, mid-corner, and exit residuals must equal the total corner residual within 0.001s.
* **`assert_ghost_car_self_consistency.sql`**: Ghost-car degenerate identity. Ensures that putting a driver's skill back into their own constructor's car yields a delta of exactly zero.
* **`assert_example_identity_closure.sql`**: Usage example for the closure macro.
* **`assert_deg_slope_centering.sql`**: Fix 1 validation: ensures constructor degradation-slope is perfectly centered (raw minus field mean).
* **`assert_cliff_hinge_centering.sql`**: Fix 2 validation: ensures constructor cliff-onset hinge is perfectly centered.
* **`assert_affinity_shrinkage_bounds.sql`**: Validates the mathematical bounds of the Bayesian shrinkage for driver circuit affinity.
* **`assert_era_rating_shrinkage_bounds.sql`**: Validates the mathematical bounds of the Bayesian shrinkage for era ratings.

---

## 2. Domain Constraint Tests (Physics Checks)
The CI runs custom SQL queries to ensure the physical state of the track and the cars behaves logically.

### Detailed Test Directory
* **`assert_track_evolution_monotone.sql`**: Track rubber only builds up over time during a dry race. If the model suggests the track randomly "lost" grip without rain, the test fails.
* **`assert_stint_boundary_integrity`**: Ensures that when a driver pits, their thermal load, air state, and tyre age are immediately reset.
* **`assert_no_future_leakage.sql`**: A strict guard preventing data leakage. Ensures trailing window functions (like moving averages for tyre temperature) don't accidentally look ahead at future laps.
* **`assert_synthetic_teammate_identity.sql`**: Ensures the `driver_skill_proxy` evaluates to roughly 0 when the ego driver and the synthetic teammate are the same person.
* **`assert_field_pace_honest_range.sql`**: The field pace curve must stay within ±5 seconds of the overall race median.
* **`assert_mad_floor.sql`**: The MAD (Median Absolute Deviation) scale estimator must be floored at 0.10s to prevent a severe tyre cliff from masking itself.
* **`assert_driver_skill_residual_reasonable.sql`**: The derived driver-skill residual per race must be centered near 0 (mean < ±1s).
* **`assert_raw_laps_has_both_sessions.sql`**: Validates that data for both the race session and the qualifying session are present in the bronze models.
* **`assert_p_beats_next_geq_half.sql`**: Fix 3 pairwise consistency: ensures the probability of a driver beating the next ranked driver is mathematically $\ge 0.5$.
* **`assert_constructor_coefficient_signs.sql`**: Every season must have at least one constructor genuinely faster than the field, preventing relative calculations from drifting infinitely.
* **`assert_constructor_confidence_monotone.sql`**: Ensures constructor-index confidence strictly increases with lap count (Placeholder/YAML).
* **`assert_cliff_stints_have_falloff.sql`**: Informational flag for stints with a detected cliff but minimal end-of-stint pace falloff (Placeholder).

---

## 3. Statistical "Regression" Gates
This acts as the ultimate mathematical gatekeeper for the project. Certain tests ensure that code changes actually *improve* the statistical model. 

When a developer submits a PR to improve how the "car pace" is calculated, the CI checks the variance of the resulting *driver skill residual*. If the new car pace calculation is worse, it will introduce noise, meaning the variance of the driver skill goes up. **The CI will block the merge** if a code change makes the driver skill estimate statistically noisier than the `main` branch baseline.

### Detailed Test Directory
* **`assert_constructor_pace_propagates.sql`**: Ensures that the `constructor_component_s` successfully reduces the variance in `driver_skill_residual_s` versus the pre-release baseline.
* **`assert_residual_variance_shrinks.sql`**: Ensures the variance of `driver_skill_residual_s` does not regress mathematically compared to the hardcoded baseline snapshot.

---

## 4. The Generic Schema Tests (The Remaining ~396 Tests)
While the custom singular SQL tests handle the complex physics and statistical boundaries, the vast majority of the **424 total tests** are strictly enforced generic assertions defined in the `schema.yml` files across the 60 models. 

These include:
* **Primary Key & Foreign Key Integrity**: `unique` and `not_null` constraints on all surrogate keys (like `stint_id` or `lap_id`).
* **Domain Boundaries**: Strict `dbt_expectations.expect_column_values_to_be_between` enforcement ensuring that probabilities (like `recombination_confidence` or `p_beats_next`) stay strictly within `[0, 1]`.
* **Physical Guardrails**: Ensuring physical properties don't violate reality (e.g., dirty air tax cannot be negative, lift and coast shares must remain between `0` and `1`).
* **Categorical Integrity**: `accepted_values` ensuring tyre compounds and session flags do not drift from their expected taxonomy.

These generic tests run continuously alongside the singular tests, ensuring that the feature columns sent downstream to the ML layer never break their strict schema contracts.

---

## 5. Real-World Edge Cases (Fixtures)
Instead of mocking fake, perfectly clean data, the CI runs these strict tests against three committed "fixture" races (`fixtures/bronze/laps`) to guarantee the logic handles the chaos of real Formula 1:

* **Bahrain 2023**: A perfectly clean, dry race with multiple tyre compounds (baseline sanity).
* **Italy 2020**: A chaotic sprint-style race with red flags and severe interruptions.
* **São Paulo 2024**: A deeply wet and mixed-condition race pushing the anomaly detection to its limits.


<details>
<summary>Click to expand the Complete Directory of Generic Schema Tests (~400 tests)</summary>


### Staging Layer
#### **stg_laps** (7 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
- `not_null` on `driver_id`
- `not_null` on `race_year`
- `not_null` on `race_id`
- `not_null` on `lap_number`
- `accepted_values` on `compound`
#### **stg_sector_times** (4 tests)
- `not_null` on `sector_id`
- `unique` on `sector_id`
- `not_null` on `lap_id`
- `accepted_values` on `sector`
#### **stg_pits** (1 tests)
- `not_null` on `lap_id`
#### **stg_events** (2 tests)
- `not_null` on `stg_event_id`
- `unique` on `stg_event_id`
#### **stg_results** (8 tests)
- `not_null` on `result_id`
- `unique` on `result_id`
- `not_null` on `race_id`
- `not_null` on `race_year`
- `not_null` on `driver_id`
- `not_null` on `is_classified`
- `not_null` on `is_dnf`
- `accepted_values` on `dnf_cause`
#### **stg_track_status** (4 tests)
- `not_null` on `track_status_id`
- `not_null` on `race_id`
- `accepted_values` on `status_label`
- `not_null` on `session_time_s`
#### **stg_session_status** (3 tests)
- `not_null` on `session_status_id`
- `not_null` on `race_id`
- `not_null` on `session_time_s`
#### **stg_circuit_info** (5 tests)
- `not_null` on `corner_id`
- `unique` on `corner_id`
- `not_null` on `race_id`
- `not_null` on `race_year`
- `not_null` on `corner_distance_m`

### Marts Layer
#### **fct_driver_skill_features** (1 tests)
- `dbt_expectations.expect_column_values_to_be_between` on model level
#### **fct_cliff_prediction_features** (2 tests)
- `dbt_expectations.expect_column_values_to_be_between` on model level
- `dbt_expectations.expect_column_values_to_be_between` on model level
#### **fct_stint_features** (8 tests)
- `not_null` on `stint_id`
- `unique` on `stint_id`
- `not_null` on `driver_id`
- `not_null` on `race_id`
- `not_null` on `race_year`
- `not_null` on `stint_length_laps`
- `dbt_expectations.expect_column_values_to_be_between` on `stint_length_laps`
- `not_null` on `short_stint_flag`
#### **fct_ghost_car_pace** (21 tests)
- `not_null` on `ghost_id`
- `unique` on `ghost_id`
- `not_null` on `predicted_lap_time_s`
- `not_null` on `actual_lap_time_s`
- `not_null` on `delta_vs_actual_lap_s`
- `not_null` on `deg_interaction_s`
- `not_null` on `host_deg_slope_s_per_lap`
- `not_null` on `ego_deg_slope_s_per_lap`
- `not_null` on `cliff_interaction_s`
- `dbt_expectations.expect_column_values_to_be_between` on `cliff_interaction_s`
- `not_null` on `host_cliff_shift_laps`
- `not_null` on `ego_cliff_shift_laps`
- `not_null` on `recombination_confidence`
- `dbt_expectations.expect_column_values_to_be_between` on `recombination_confidence`
- `not_null` on `host_constructor_pace_se_s`
- `not_null` on `host_deg_slope_sd_s_per_lap`
- `not_null` on `ego_deg_slope_sd_s_per_lap`
- `not_null` on `host_cliff_shift_se_laps`
- `not_null` on `ego_cliff_shift_se_laps`
- `not_null` on `host_cliff_active`
- `not_null` on `ego_cliff_active`
#### **fct_ghost_race_finish** (12 tests)
- `not_null` on `ghost_race_id`
- `unique` on `ghost_race_id`
- `not_null` on `is_self_scenario`
- `not_null` on `predicted_finish_position`
- `dbt_expectations.expect_column_values_to_be_between` on `predicted_finish_position`
- `not_null` on `predicted_mean_lap_s`
- `not_null` on `is_short_run`
- `not_null` on `predicted_mean_lap_se_s`
- `dbt_expectations.expect_column_values_to_be_between` on `predicted_mean_lap_se_s`
- `dbt_expectations.expect_column_values_to_be_between` on `p_beats_next`
- `not_null` on `finish_pos_se`
- `dbt_expectations.expect_column_values_to_be_between` on `finish_pos_se`
#### **mart_corner_skill_driver** (13 tests)
- `not_null` on `race_year`
- `not_null` on `driver_id`
- `not_null` on `constructor_id`
- `not_null` on `braking_skill_s`
- `not_null` on `mid_corner_skill_s`
- `not_null` on `exit_skill_s`
- `not_null` on `braking_skill_z`
- `not_null` on `mid_corner_skill_z`
- `not_null` on `exit_skill_z`
- `not_null` on `corner_skill_index`
- `dbt_expectations.expect_column_values_to_be_between` on `corner_skill_index`
- `not_null` on `mapped_corners`
- `dbt_utils.unique_combination_of_columns` on model level
#### **mart_degradation_history_envelope** (22 tests)
- `not_null` on `circuit_id`
- `not_null` on `circuit_name`
- `not_null` on `era`
- `accepted_values` on `era`
- `not_null` on `compound`
- `not_null` on `lap_in_stint`
- `dbt_expectations.expect_column_values_to_be_between` on `lap_in_stint`
- `not_null` on `n_observations`
- `dbt_expectations.expect_column_values_to_be_between` on `n_observations`
- `not_null` on `ref_green_pace_s`
- `dbt_expectations.expect_column_values_to_be_between` on `ref_green_pace_s`
- `not_null` on `obs_fuel_removed_pace_p10_s`
- `not_null` on `obs_fuel_removed_pace_p50_s`
- `not_null` on `obs_fuel_removed_pace_p90_s`
- `not_null` on `obs_deg_from_fresh_p10_s`
- `not_null` on `obs_deg_from_fresh_p50_s`
- `not_null` on `obs_deg_from_fresh_p90_s`
- `dbt_utils.unique_combination_of_columns` on model level
- `dbt_expectations.expect_table_row_count_to_be_between` on model level
- `dbt_expectations.expect_column_pair_values_A_to_be_greater_than_B` on model level
- `dbt_expectations.expect_column_pair_values_A_to_be_greater_than_B` on model level
- `dbt_expectations.expect_column_pair_values_A_to_be_greater_than_B` on model level
#### **dim_events** (3 tests)
- `not_null` on `event_id`
- `unique` on `event_id`
- `not_null` on `race_id`
#### **fct_lap_residuals** (18 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
- `not_null` on `race_year`
- `not_null` on `race_id`
- `not_null` on `driver_id`
- `not_null` on `constructor_id`
- `not_null` on `lap_number`
- `not_null` on `lap_time_s`
- `accepted_values` on `compound`
- `not_null` on `fuel_component_s`
- `not_null` on `compound_component_s`
- `not_null` on `rubber_component_s`
- `not_null` on `ambient_component_s`
- `not_null` on `constructor_component_s`
- `not_null` on `dirty_air_tax_s`
- `not_null` on `driver_skill_residual_s`
- `not_null` on `ml_eligible`
- `not_null` on `correction_weight`
#### **fct_telemetry_deltas** (9 tests)
- `not_null` on `race_id`
- `not_null` on `driver_a`
- `not_null` on `driver_b`
- `not_null` on `corner_name`
- `not_null` on `track_id`
- `not_null` on `lap_number`
- `not_null` on `braking_point_delta_m`
- `not_null` on `v_min_delta_kph`
- `not_null` on `throttle_point_delta_m`

### Intermediate Layer
#### **int_stint_geometry** (3 tests)
- `not_null` on `stint_id`
- `not_null` on `lap_id`
- `unique` on `lap_id`
#### **int_lap_fuel_state** (2 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
#### **int_lap_air_state** (2 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
#### **int_lap_thermal_proxy** (2 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
#### **int_corner_metrics** (4 tests)
- `not_null` on `driver_id`
- `not_null` on `lap_number`
- `not_null` on `race_id`
- `not_null` on `corner_name`
#### **int_lap_telemetry_aggregates** (7 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
- `not_null` on `stint_id`
- `dbt_utils.accepted_range` on `pct_full_throttle`
- `dbt_utils.accepted_range` on `pct_drs_active`
- `dbt_utils.accepted_range` on `traction_wheelspin_proxy`
- `dbt_utils.accepted_range` on `lift_coast_share`
#### **int_compound_cliff_predicted** (2 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
#### **int_field_pace_curve** (3 tests)
- `not_null` on `race_year`
- `not_null` on `race_id`
- `not_null` on `lap_number`
#### **int_track_evolution** (3 tests)
- `not_null` on `race_year`
- `not_null` on `race_id`
- `not_null` on `lap_number`
#### **int_synthetic_teammate** (4 tests)
- `not_null` on `race_year`
- `not_null` on `race_id`
- `not_null` on `ego_driver_id`
- `not_null` on `lap_number`
#### **int_event_corrections** (2 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
#### **int_lap_residual_decomposed** (7 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
- `not_null` on `constructor_component_s`
- `not_null` on `dirty_air_tax_s`
- `dbt_expectations.expect_column_values_to_be_between` on `dirty_air_tax_s`
- `not_null` on `driver_skill_residual_s`
- `not_null` on `total_explained_s`
#### **int_lap_anomaly_flags** (2 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
#### **int_constructor_car_fe** (6 tests)
- `not_null` on `constructor_car_fe_id`
- `unique` on `constructor_car_fe_id`
- `not_null` on `race_year`
- `not_null` on `race_id`
- `not_null` on `constructor_id`
- `not_null` on `car_fe_s`
#### **int_constructor_structural_pace** (15 tests)
- `not_null` on `constructor_race_id`
- `unique` on `constructor_race_id`
- `not_null` on `race_year`
- `not_null` on `race_id`
- `not_null` on `constructor_id`
- `not_null` on `constructor_structural_pace_s`
- `not_null` on `constructor_structural_pace_se_s`
- `dbt_expectations.expect_column_values_to_be_between` on `constructor_structural_pace_se_s`
- `not_null` on `constructor_structural_pace_ci_low_s`
- `not_null` on `constructor_structural_pace_ci_high_s`
- `not_null` on `panel_observations_n`
- `not_null` on `clean_teammate_pair_laps_n`
- `dbt_expectations.expect_column_values_to_be_between` on `r_squared_within`
- `not_null` on `fit_timestamp`
- `dbt_expectations.expect_column_pair_values_A_to_be_greater_than_B` on model level
#### **int_constructor_deg_sensitivity** (25 tests)
- `not_null` on `deg_sensitivity_id`
- `unique` on `deg_sensitivity_id`
- `not_null` on `race_year`
- `not_null` on `constructor_id`
- `not_null` on `compound`
- `accepted_values` on `compound`
- `not_null` on `deg_slope_s_per_lap`
- `dbt_expectations.expect_column_values_to_be_between` on `deg_slope_s_per_lap`
- `dbt_expectations.expect_column_values_to_be_between` on `deg_slope_raw_s_per_lap`
- `dbt_expectations.expect_column_values_to_be_between` on `deg_slope_se_s_per_lap`
- `not_null` on `deg_slope_posterior_sd_s_per_lap`
- `not_null` on `shrink_factor`
- `dbt_expectations.expect_column_values_to_be_between` on `shrink_factor`
- `not_null` on `tau_s_per_lap`
- `not_null` on `n_laps`
- `not_null` on `n_stints`
- `not_null` on `is_low_sample`
- `not_null` on `cliff_onset_shift_laps`
- `dbt_expectations.expect_column_values_to_be_between` on `cliff_onset_shift_laps`
- `dbt_expectations.expect_column_values_to_be_between` on `cliff_onset_shift_se_laps`
- `not_null` on `n_post_cliff_laps`
- `not_null` on `n_deep_cliff_laps`
- `not_null` on `n_stints_cliff`
- `not_null` on `is_low_sample_cliff`
- `not_null` on `fit_timestamp`
#### **int_dirty_air_tax_component** (10 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
- `not_null` on `dirty_air_intensity_lag1`
- `not_null` on `dirty_air_tax_s`
- `dbt_expectations.expect_column_values_to_be_between` on `dirty_air_tax_s`
- `not_null` on `dirty_air_tax_se_s`
- `not_null` on `tax_calibration_confidence`
- `dbt_expectations.expect_column_values_to_be_between` on `tax_calibration_confidence`
- `not_null` on `cumulative_dirty_air_tax_race_s`
- `not_null` on `dirtiest_air_lap_in_race_flag`
#### **int_sector_residual_decomposed** (10 tests)
- `not_null` on `sector_id`
- `unique` on `sector_id`
- `not_null` on `lap_id`
- `not_null` on `sector`
- `accepted_values` on `sector`
- `not_null` on `sector_time_s`
- `not_null` on `sector_pace_delta_s`
- `not_null` on `sector_driver_skill_residual_s`
- `not_null` on `sector_total_explained_s`
- `accepted_values` on `dominant_component_class`
#### **int_corner_skill_residuals** (6 tests)
- `not_null` on `corner_id`
- `unique` on `corner_id`
- `not_null` on `lap_id`
- `not_null` on `corner_name`
- `not_null` on `field_corner_sample_n`
- `not_null` on `corner_unmapped_flag`
#### **int_lap_fuel_state_qualifying** (2 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
#### **int_constructor_structural_pace_qualifying** (3 tests)
- `not_null` on `constructor_race_id`
- `unique` on `constructor_race_id`
- `not_null` on `constructor_structural_pace_s`
#### **int_lap_residual_decomposed_qualifying** (3 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
- `not_null` on `quali_driver_skill_residual_s`
#### **int_qualifying_decomposed** (3 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
- `not_null` on `quali_skill_residual_s`
#### **int_pit_strategy_value** (5 tests)
- `not_null` on `stint_id`
- `unique` on `stint_id`
- `dbt_expectations.expect_column_values_to_be_between` on `opportunity_cost_s`
- `accepted_values` on `strategy_verdict`
- `dbt_expectations.expect_column_values_to_be_between` on `optimal_pit_lap_confidence`
#### **int_circuit_x_constructor_interaction** (3 tests)
- `not_null` on `constructor_race_id`
- `unique` on `constructor_race_id`
- `not_null` on `circuit_constructor_interaction_s`
#### **int_tyre_surface_vs_bulk_decoupling** (9 tests)
- `not_null` on `lap_id`
- `unique` on `lap_id`
- `not_null` on `surface_bulk_ratio`
- `dbt_expectations.expect_column_values_to_be_between` on `surface_bulk_ratio`
- `not_null` on `degradation_source`
- `accepted_values` on `degradation_source`
- `not_null` on `recovery_probability`
- `dbt_expectations.expect_column_values_to_be_between` on `recovery_probability`
- `not_null` on `thermal_attribution_s`
#### **int_driver_circuit_affinity** (14 tests)
- `not_null` on `driver_circuit_id`
- `unique` on `driver_circuit_id`
- `not_null` on `driver_id`
- `not_null` on `circuit_key`
- `not_null` on `n_obs`
- `not_null` on `seasons_observed_n`
- `not_null` on `raw_affinity_s`
- `not_null` on `shrunk_affinity_s`
- `not_null` on `shrunk_affinity_se_s`
- `dbt_expectations.expect_column_values_to_be_between` on `shrunk_affinity_se_s`
- `not_null` on `shrunk_affinity_ci_low_s`
- `not_null` on `shrunk_affinity_ci_high_s`
- `not_null` on `affinity_confidence`
- `dbt_expectations.expect_column_values_to_be_between` on `affinity_confidence`
#### **int_driver_circuit_era_affinity** (18 tests)
- `not_null` on `driver_circuit_era_id`
- `unique` on `driver_circuit_era_id`
- `not_null` on `driver_id`
- `not_null` on `circuit_id`
- `not_null` on `circuit_name`
- `not_null` on `era_key`
- `accepted_values` on `era_key`
- `not_null` on `era_label`
- `not_null` on `n_obs`
- `not_null` on `seasons_observed_n`
- `not_null` on `raw_affinity_s`
- `not_null` on `shrunk_affinity_s`
- `not_null` on `shrunk_affinity_se_s`
- `dbt_expectations.expect_column_values_to_be_between` on `shrunk_affinity_se_s`
- `not_null` on `shrunk_affinity_ci_low_s`
- `not_null` on `shrunk_affinity_ci_high_s`
- `not_null` on `affinity_confidence`
- `dbt_expectations.expect_column_values_to_be_between` on `affinity_confidence`
#### **int_driver_race_skill_loro** (6 tests)
- `not_null` on `driver_race_skill_id`
- `unique` on `driver_race_skill_id`
- `not_null` on `driver_id`
- `not_null` on `race_year`
- `not_null` on `race_id`
- `not_null` on `clean_lap_count`
#### **int_driver_season_ratings** (11 tests)
- `not_null` on `driver_season_id`
- `unique` on `driver_season_id`
- `not_null` on `driver_id`
- `not_null` on `season`
- `not_null` on `n_races`
- `not_null` on `raw_residual_mean_s`
- `not_null` on `shrunk_residual_s`
- `not_null` on `shrunk_residual_se_s`
- `dbt_expectations.expect_column_values_to_be_between` on `shrunk_residual_se_s`
- `not_null` on `rating_confidence`
- `dbt_expectations.expect_column_values_to_be_between` on `rating_confidence`
#### **int_era_normalized_driver_rating** (15 tests)
- `not_null` on `driver_season_id`
- `unique` on `driver_season_id`
- `not_null` on `driver_id`
- `not_null` on `season`
- `not_null` on `raw_residual_mean_s`
- `not_null` on `shrunk_residual_s`
- `not_null` on `era_adjusted_rating`
- `not_null` on `era_adjusted_rating_se_s`
- `dbt_expectations.expect_column_values_to_be_between` on `era_adjusted_rating_se_s`
- `not_null` on `era_adjusted_rating_ci_low_s`
- `not_null` on `era_adjusted_rating_ci_high_s`
- `not_null` on `rating_confidence`
- `dbt_expectations.expect_column_values_to_be_between` on `rating_confidence`
- `not_null` on `bridge_driver_anchor_flag`
- `not_null` on `low_anchor_sample_flag`
#### **int_sc_hazard_history** (17 tests)
- `not_null` on `circuit_slug`
- `unique` on `circuit_slug`
- `not_null` on `n_races`
- `not_null` on `racing_laps`
- `dbt_expectations.expect_column_values_to_be_between` on `racing_laps`
- `not_null` on `sc_hazard_per_lap`
- `dbt_expectations.expect_column_values_to_be_between` on `sc_hazard_per_lap`
- `not_null` on `vsc_hazard_per_lap`
- `dbt_expectations.expect_column_values_to_be_between` on `vsc_hazard_per_lap`
- `not_null` on `any_hazard_per_lap`
- `dbt_expectations.expect_column_values_to_be_between` on `any_hazard_per_lap`
- `not_null` on `sc_hazard_per_lap_shrunk`
- `dbt_expectations.expect_column_values_to_be_between` on `sc_hazard_per_lap_shrunk`
- `not_null` on `vsc_hazard_per_lap_shrunk`
- `dbt_expectations.expect_column_values_to_be_between` on `vsc_hazard_per_lap_shrunk`
- `not_null` on `any_hazard_per_lap_shrunk`
- `dbt_expectations.expect_column_values_to_be_between` on `any_hazard_per_lap_shrunk`
#### **int_pit_loss_circuit** (7 tests)
- `not_null` on `circuit_slug`
- `unique` on `circuit_slug`
- `not_null` on `n_stops`
- `not_null` on `pit_loss_s_empirical`
- `dbt_expectations.expect_column_values_to_be_between` on `pit_loss_s_empirical`
- `not_null` on `pit_loss_s_shrunk`
- `dbt_expectations.expect_column_values_to_be_between` on `pit_loss_s_shrunk`

### Reference Layer
#### **dim_circuits** (6 tests)
- `not_null` on `circuit_key`
- `unique` on `circuit_key`
- `not_null` on `circuit_id`
- `not_null` on `fuel_consumption_rate_kg_per_lap`
- `not_null` on `weight_penalty_factor`
- `dbt_expectations.expect_column_values_to_be_between` on `lap_length_km`
#### **dim_compounds_season** (4 tests)
- `not_null` on `circuit_key`
- `not_null` on `compound_code`
- `not_null` on `season`
- `not_null` on `fit_date`
#### **dim_drivers** (2 tests)
- `not_null` on `driver_id`
- `unique` on `driver_id`
#### **dim_constructors** (3 tests)
- `not_null` on `constructor_id`
- `unique` on `constructor_id`
- `not_null` on `pu_family`
</details>
