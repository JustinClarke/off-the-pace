# Lineage and robustness: what feeds what, and where it can break

Written 2026-11-21. Read-only review of the working tree (uncommitted state). No dbt run, no data queried, no tests executed. Every claim comes from reading a model file, a schema file, a test file, the app or ML code, or the [transform status board](transform.md).

Updated 2026-11-22 for the track-evolution closure work. Section F lists what changed. Those updates come from scratch builds (a CI fixture and a 2018–2025 bronze copy), not from the production warehouse.

**Top findings**

1. Almost every number the app and the ML model show passes through [int_stint_geometry](../../../transform/models/intermediate/int_stint_geometry.sql), [int_lap_fuel_state](../../../transform/models/intermediate/int_lap_fuel_state.sql) and [int_lap_residual_decomposed](../../../transform/models/intermediate/int_lap_residual_decomposed.sql). A mistake in any of these spreads to 30 to 60 other models.
2. The most robust chains are the short ones close to raw data (staging, stint geometry, the power-law chain, the lap residual identity). The least robust are the long ones that stack several assumptions (qualifying features, ghost car, corner skill, cliff defaults).
3. The worst habit in the code is a default that looks like data: 0.0 constructor pace, `LEAST(slope, 0)` in track evolution, 0.5 thermal ratio, default tyre-cliff cells, 0.0 qualifying race-average. Some now carry a flag column (`constructor_pace_is_filled`, `*_is_prior`), but the downstream averages mostly ignore the flag.
4. The ML contract (39 features) comes from one mart, [fct_cliff_prediction_features](../../../transform/models/marts/fct_cliff_prediction_features.sql). Its leakage guards are strong and tested. Its weakest inputs are the seven qualifying features and the compound and cliff-prior features, which sit on seed-fitted defaults.
5. The status file is out of date in several places (car-FE models, qualifying fuel, a "no reader" model that has a reader, ghost-car flags). Section E lists them. Do not rely on its status column without checking the file.

---

## A. How the pipeline works

**Sources.** Raw race data is read from "bronze" parquet files (FastF1 laps, telemetry, weather, results, track status, race control, circuit info, qualifying versions of these) plus Jolpica pit stops. They are declared in [src_formula1.yml](../../../transform/models/staging/src_formula1.yml) and [src_jolpica.yml](../../../transform/models/staging/src_jolpica.yml). One more source, `fits`, is a parquet file written by a Python fit script outside dbt ([src_fits.yml](../../../transform/models/intermediate/src_fits.yml)). Hand-kept lookup tables ("seeds") sit in [transform/seeds](../../../transform/seeds): `race_to_track`, `circuit_reference`, `compound_cliff_params`, `compound_hardness_scale`, `race_scheduled_laps`, `tyre_allocations`, `seed_manual_lap_exceptions`, `raw_dim_events`, `driver_isolation_method_scores`.

**Staging (`stg_*`).** One cleaning step per raw table: rename columns, fix types, map tyre names, flag valid laps. Almost no logic. Output is in [transform/models/staging](../../../transform/models/staging).

**Intermediate (`int_*`).** Where the logic lives. 53 models. They build, in order: the stint (one continuous run on one set of tyres) per lap; fuel mass per lap; the field pace curve (what a normal lap time is on that lap); track evolution (the track getting faster as rubber builds); the dirty-air state (time spent close behind another car); expected tyre wear and "cliff" (the lap where a tyre suddenly drops off); and then the lap residual. The residual is lap time minus all those terms, and it is used as the driver skill signal. Driver ratings, qualifying, corner skill and pit strategy build on top. Files are in [transform/models/intermediate](../../../transform/models/intermediate).

**Reference (`dim_*`).** Small lookup tables built from seeds (circuits, compounds per season, constructors, drivers, corners). In [transform/models/reference](../../../transform/models/reference).

**Marts (`fct_*`, `mart_*`).** The tables other things read. `fct_cliff_prediction_features` is the ML training table. `fct_lap_residuals`, `fct_stint_features`, `fct_ghost_*`, `fct_driver_skill_features` and the `mart_*` summaries feed the app. In [transform/models/marts](../../../transform/models/marts). Five scratch marts under `new_data/` have no reader yet.

**Readers.**
- **Export.** [scripts/export_app_data.py](../../../scripts/export_app_data.py) copies a fixed list of tables to parquet in `app/public/data`. The app can only read tables on that list (plus one derived table, `race_caution_timeline`, built from `int_stint_geometry`).
- **App.** Pages in [app/src/features](../../../app/src/features) run SQL against those parquet files in the browser.
- **Assistant.** [app/src/assistant](../../../app/src/assistant) builds answer "cards" from the same exported tables. Some cards are held stubs that name a table that does not exist (`fct_constructor_structural_pace`, in [heldStubs.ts](../../../app/src/assistant/cards/sql/heldStubs.ts)).
- **ML.** [ml/src/features.py](../../../ml/src/features.py) and [ml/src/schema.py](../../../ml/src/schema.py) read `fct_cliff_prediction_features` and `fct_stint_features` straight from the DuckDB warehouse. [ml/src/powerlaw.py](../../../ml/src/powerlaw.py) reads `fct_power_law_training`. [ml/src/predict.py](../../../ml/src/predict.py) writes `mart_degradation_predictions.parquet`, which the app reads for the model pages. This table is not a dbt model.

---

## B. Lineage by feature

Notation: `->` means "is read by". Seeds are in brackets. Paths are given once at first use; every model lives under `transform/models/<layer>/<name>.sql` (layer: staging, intermediate, marts, reference).

### B1. Shared spine (almost everything below passes through these)

```
bronze raw_laps [+ seed_manual_lap_exceptions] -> stg_laps
bronze raw_laps -> stg_pits -> (with stg_laps) stg_lap_tyre_qa
bronze raw_results -> stg_results -> stg_race_control
[tyre_allocations] -> stg_tyre_allocations
stg_laps + stg_lap_tyre_qa + stg_tyre_allocations + stg_race_control + stg_results + [race_to_track]
   -> int_stint_geometry        (one row per lap with its stint, tyre age, compound, flag laps)
int_stint_geometry + dim_circuits ([circuit_reference]) + [race_scheduled_laps] + [race_to_track] + stg_laps
   -> int_lap_fuel_state        (fuel mass per lap)
int_stint_geometry + dim_compounds_season ([compound_cliff_params]) + stg_weather + [race_to_track]
   -> int_compound_cliff_predicted   (expected tyre pace, wear and cliff per lap)
int_compound_cliff_predicted + int_lap_fuel_state + int_lap_air_state + int_stint_geometry
   -> int_field_pace_curve -> int_track_evolution (rain state from int_lap_rain_state)
stg_laps + stg_weather + [race_to_track]
   -> int_lap_rain_state   (one row per lap: DRY, WET or NO_WEATHER; does not read the pace curve)
stg_laps + [seed_manual_lap_exceptions] -> int_event_corrections   (weights for restart, outlier laps)
... + int_constructor_structural_pace + int_dirty_air_tax_component
   -> int_lap_residual_decomposed   (the lap residual, "driver skill" signal; 8 int inputs; also reads int_track_evolution and int_lap_rain_state, and publishes base_pace_status = MEASURED / THIN_CELL / NO_CELL)
```
Notes: `int_lap_air_state` reads bronze `raw_telemetry` directly, not `stg_telemetry`. `dim_compounds_season` is built from the seed [compound_cliff_params.csv](../../../transform/seeds/compound_cliff_params.csv), which is written by [fit_compound_cliff.py](../../../transform/tasks/coefficients/fit_compound_cliff.py).

### B2. ML features (the contract in [ml/src/schema.py](../../../ml/src/schema.py))

All 39 feature columns come from the one mart [fct_cliff_prediction_features](../../../transform/models/marts/fct_cliff_prediction_features.sql). The degradation and stint-life models use 32 (qualifying group masked); the cliff classifier uses all 39. The chain per group:

| Group (features) | Chain to the mart |
|---|---|
| **stint_position**: `lap_number`, `lap_in_stint`, `age_in_stint`, `fuel_mass_kg` | B1 spine -> `int_lap_residual_decomposed` (carries stint fields and fuel) -> mart. Fuel: `int_lap_fuel_state`. |
| **compound** (7): `compound`, `compound_grip_peak`, `compound_wear_gradient`, `compound_optimal_temp_low/high`, `compound_cliff_onset_laps`, `compound_cliff_severity` | [compound_cliff_params] -> `dim_compounds_season` -> mart |
| **cliff_prior** (4): `expected_compound_pace_s`, `expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff` | `dim_compounds_season` + `int_stint_geometry` + `stg_weather` -> `int_compound_cliff_predicted` -> mart |
| **thermal** (4): `push_residual`, `cumulative_push_load_surface/bulk`, `surface_bulk_ratio` | `int_lap_fuel_state` + `int_stint_geometry` + `stg_laps` -> `int_lap_thermal_proxy` -> mart (the ratio is finished in the mart using the two weight-sum vars in [dbt_project.yml](../../../transform/dbt_project.yml)) |
| **dirty_air** (4): `dirty_air_share_lap`, `dirty_air_thermal_load_surface/bulk`, `air_state_dominant` | bronze `raw_telemetry` + `stg_laps` + `int_stint_geometry` -> `int_lap_air_state` -> mart |
| **proximity** (9): `share_lap_within_1s/2s`, `share_lap_in_train`, `share_lap_behind_within_1s`, `time_within_1s`, `gap_ahead_min_s`, `gap_ahead_median_s`, `ahead_identity_stability`, `n_distinct_cars_ahead_3s` | `stg_telemetry_position` + `stg_pits` + `stg_results` + `int_stint_geometry` -> `int_lap_proximity` -> mart |
| **qualifying** (7): `quali_push_laps_n`, `quali_constructor_pace_mean_s`, `quali_constructor_pace_se_mean_s`, `quali_pace_delta_best_s`, `quali_ratio_to_segment_best_min`, `quali_skill_session_avg_s`, `quali_segments_contested_n` | bronze qualifying files -> `stg_laps_qualifying`, `stg_results_qualifying`, `stg_session_status_qualifying`, `stg_red_flags_qualifying` -> `int_qualifying_segments` -> `int_qualifying_push_laps` -> (`int_constructor_structural_pace_qualifying`, `int_lap_residual_decomposed_qualifying`) -> `int_qualifying_decomposed` (also reads `int_lap_residual_decomposed`) -> `int_qualifying_driver_summary` -> mart |

Targets and gates (not features, but they decide which rows train):
- **5-lap degradation target** `next_5_lap_cumulative_jump_s` and **cliff class** `laps_until_cliff_class`: built in the mart from `int_lap_residual_decomposed` residuals and the per-stint drift from [int_lap_residual_stint_detrend](../../../transform/models/intermediate/int_lap_residual_stint_detrend.sql).
- **Stint-life target** `remaining_stint_life_laps` and its censoring flag: [fct_stint_features](../../../transform/models/marts/fct_stint_features.sql) <- `int_stint_end_regime` (<- `int_stint_geometry`, `stg_results`). Joined in [features.py](../../../ml/src/features.py).
- **Training eligibility** (`is_training_eligible`, on the cliff mart): `int_lap_anomaly_flags` (anomaly class), `int_event_corrections` (restart, weight), `int_lap_residual_decomposed`, and since 2026-11-22 `base_pace_status = 'MEASURED'` (THIN_CELL and NO_CELL laps are excluded). WET laps are excluded through the anomaly class; NO_WEATHER laps stay trainable. On the 2018–2025 scratch build the training population went from 124,370 to 120,441 laps (3,575 of the drop in 2018–2024). `fct_lap_residuals.ml_eligible` is analytical and was not changed (see F).
- **Survival weight** and exposure counts: `int_sc_hazard_history` (<- `stg_laps`, `stg_track_status`).

In the mart but not in the shipped contract (dropped by ablation, per the long comment in schema.py): `int_lap_telemetry_aggregates` (powertrain and telemetry-cliff groups), `int_lap_corner_inputs`, `int_lap_corner_drift` (<- `int_corner_drift_from_early_stint` <- `int_corner_skill_residuals`). They still build and still cost build time.

Other ML code:
- **Power-law model** ([powerlaw.py](../../../ml/src/powerlaw.py), [powerlaw_fit.py](../../../ml/src/powerlaw_fit.py)): `int_power_law_lap` (<- `int_lap_residual_decomposed`, `int_stint_geometry`, `dim_circuits`, [compound_hardness_scale]) -> `int_cell_power_law_fit` -> `fct_power_law_training` (also reads `fct_cliff_prediction_features` and `int_lap_fuel_state`). `powerlaw_fit.py` also reads `int_power_law_lap` directly and treats `int_stint_power_law_fit` as a parity reference.
- **Flag chance** ([flag_chance.py](../../../ml/src/flag_chance.py)): `int_stint_geometry`, `fct_stint_features`, the ML mart.
- **Predictions parquet** -> app model pages (not a dbt model).

### B3. App pages

"Mart" in the chain below means the table the app SQL actually reads. Where I name a feature folder, the code is in `app/src/features/<folder>`. Core chain is always B1 first.

| App feature (folder) | Table read | Chain behind it (beyond B1) |
|---|---|---|
| lap-waterfall, race-lost, constructor-team-averages, pit-strategy (laps), race-control (lap table), ghost-race-standings | `fct_lap_residuals` | `int_lap_residual_decomposed` + `dim_constructors` + `dim_drivers` |
| race-control | `int_sc_hazard_history`, `race_caution_timeline` (derived from `int_stint_geometry`) | `stg_laps` + `stg_track_status` |
| field-pace-curve | `int_field_pace_curve` | B1 |
| track-evolution | `int_track_evolution` | `int_field_pace_curve` + `int_lap_rain_state` (rain state from `stg_weather`) |
| dirty-air-cost | `int_dirty_air_tax_component`, `fct_cliff_prediction_features` | `int_lap_air_state`, `int_compound_cliff_predicted`, `int_field_pace_curve`, `int_track_evolution`, `int_event_corrections`, `int_lap_fuel_state` |
| dirty-air-lap-map | `int_lap_air_state`, `fct_cliff_prediction_features` | `int_lap_air_state`; proximity group via `int_lap_proximity` |
| driver-workload | `fct_cliff_prediction_features` | `push_residual` via `int_lap_thermal_proxy` |
| tyre-cliff-survival, stint-degradation-timeline | `fct_cliff_prediction_features`, `dim_compounds_season`, `dim_circuits` | cliff and compound columns; default cells now shown as "estimate, no data for this track" via [cliffEstimate.ts](../../../app/src/features/shared/cliffEstimate.ts) |
| degradation-simulator | `mart_degradation_history_envelope`, `fct_power_law_training`, `fct_cliff_prediction_features`, `int_constructor_structural_pace`, `dim_compounds_season` | envelope <- `int_lap_residual_decomposed`, `dim_circuits`, external `fits.degradation_isotonic` parquet |
| blind-test-scoreboard, model-metrics, ml routes | `mart_degradation_predictions` (ML output), `fct_cliff_prediction_features`, `fct_stint_features` | ML chain in B2 |
| pit-strategy | `int_pit_strategy_value`, `fct_stint_features`, `fct_lap_residuals`, `int_stint_end_regime` (name appears in a code comment only), `int_lap_air_state` | `int_pit_strategy_value` <- `int_pit_strategy_cost_curve`, `int_pit_loss_circuit`, `int_stint_end_regime`, `int_compound_cliff_predicted`, `int_lap_air_state`, `stg_pits`, `stg_lap_tyre_qa`, [circuit_reference] |
| tyre-recovery-forecast | `int_tyre_surface_vs_bulk_decoupling` | `int_lap_residual_decomposed` + `int_lap_thermal_proxy` |
| constructor-structural-pace, party-mode | `int_constructor_structural_pace`, `int_constructor_structural_pace_qualifying` | `int_event_corrections`, `int_field_pace_curve`, `int_lap_fuel_state`, `int_track_evolution`; quali side <- `int_qualifying_push_laps` |
| constructor-circuit-interaction | `int_circuit_x_constructor_interaction` | `int_constructor_structural_pace`, [circuit_reference] |
| era-ratings-timeline, era-translator, hidden-performance (rating part) | `int_era_normalized_driver_rating`, `int_driver_season_ratings` | `int_driver_race_skill_loro` <- `int_driver_race_paired_laps` + `int_constructor_car_fe` + B1 corrections/fuel/pace/evolution |
| driver-circuit-affinity | `int_driver_circuit_affinity` | `int_driver_race_skill_loro`, [circuit_reference] |
| ghost-race-standings, hidden-performance | `int_driver_circuit_era_affinity`, `int_driver_race_skill_loro`, `fct_ghost_race_finish` | as above |
| counterfactual-championship, hidden-performance | `fct_ghost_race_finish` | `fct_ghost_car_pace` <- `int_lap_residual_decomposed`, `int_constructor_structural_pace`, `int_circuit_x_constructor_interaction`, `int_constructor_deg_sensitivity` (<- `int_compound_cliff_predicted`), `int_compound_cliff_predicted`, `stg_laps`, `stg_results` |
| driver-consistency, wet-race-specialist | `fct_driver_skill_features` | `int_lap_residual_decomposed`, `int_constructor_structural_pace`, `int_lap_anomaly_flags`, `int_synthetic_teammate`, `dim_*` |
| synthetic-teammate | `int_synthetic_teammate` | `int_compound_cliff_predicted`, `int_lap_fuel_state`, B1 |
| quali-vs-race-skill | `int_qualifying_decomposed` | B2 qualifying chain + `int_lap_residual_decomposed` |
| corner-phase-skill | `mart_corner_skill_driver` | `int_corner_skill_residuals` <- `int_corner_metrics`, `int_corner_lap_measured`, `int_corner_length_measured` (<- `dim_corners`, `stg_telemetry`, `stg_laps`), `stg_sector_times`, `int_stint_geometry` |
| sector-decomposition | `int_sector_residual_decomposed` | `int_lap_residual_decomposed`, `int_lap_air_state`, `stg_sector_times`, `stg_lap_tyre_qa` |
| data-quality-audit | `int_lap_anomaly_flags`, `mart_race_coverage` | `int_lap_residual_decomposed` -> flags; coverage <- `int_driver_race_skill_loro`, `stg_lap_tyre_qa`, `int_lap_air_state` |
| query-lab | `fct_driver_skill_features`, `fct_ghost_race_finish`, `fct_stint_features`, `mart_corner_skill_driver`, `dim_circuits` | as above |
| assistant cards | `mart_race_driver_summary`, `mart_driver_season_summary`, `mart_race_coverage`, `mart_metric_benchmark`, `mart_build_provenance`, `fct_driver_isolation_race/stint`, `int_driver_isolation_lap_panel` (held), `stg_results`, `stg_pits`, plus most of the tables above | summary marts <- `fct_lap_residuals`, `int_dirty_air_tax_component`, `int_driver_race_paired_laps`, `int_driver_race_skill_loro`, `int_era_normalized_driver_rating`, `stg_results` |

Not exported or comment-only in the app (checked by grep): `int_lap_proximity` and `int_lap_residual_decomposed` appear only in comments or docs text, not in a live query. Routes such as `drivers/dna-clusters`, `deep-dives/telemetry-fingerprint`, `ghost-car/standings`, `ghost-car/lap-chart` are stubs that name `stg_telemetry` or `fct_ghost_car_pace` in a header comment.

### B4. Built but with no reader (checked by grep over app, ml, scripts and the dbt graph)

`stg_events`, `stg_red_flags` (new), `dim_driver_seasons`, `int_lap_normalized_pace` (a deliberate leaf), `int_track_geometry`, `int_microsector_crossings` -> `int_microsector_proximity`, `int_microsector_corner_class`, the physical-ahead chain (`stg_physical_ahead_laps/telemetry` -> `int_lap_physical_ahead` -> `int_physical_ahead_pairs`, `_pairs_lapped`, `_pair_race`, `int_traffic_exposure_driver_race` -> `int_traffic_exposure_race`), and the five `new_data` marts. `fct_telemetry_deltas`, `fct_driver_isolation_lap/pair_lap` and `fct_power_law_training` have no app reader but have an ML or assistant reader or feed other models. `fct_telemetry_deltas` is handled outside the main export list (the export script says it is derived inline); I did not trace it.

---

## C. Ranking, most robust to least robust

This is judgement, not a measurement. The order uses these signals: layers between the raw data and the output, zero or constant fills that look like data, logic tests (not just column tests), open issues, documented sign and unit, and whether anything reads it. Test counts are the number of singular tests under [transform/tests](../../../transform/tests) that call `ref()` on the model; they do not include schema-file tests or tests that reach the model another way, so treat them as a rough guide.

1. **Staging reads** (`stg_laps` 16 tests, `stg_weather` 9, `stg_telemetry*`, `stg_circuit_info`, `stg_tyre_allocations`, `stg_race_control`, `stg_track_status`). One step from raw, little logic. Open items: `stg_results` misses about 69 classified retirements (DNF flag), `stg_lap_tyre_qa` has stint 0 on 3 driver-races (accepted as DQ-01), and several relationships tests fail on 2026 rows missing from `race_to_track`.
2. **`int_stint_geometry`** (20 tests, status SOUND). The most tested model. Five staging inputs, so a bad stint here spreads to about 63 models. Open: `assert_stint_geometry_2018_compound_code_null` fails (1 row on the scratch build).
3. **Power-law chain** (`int_power_law_lap` -> `int_cell_power_law_fit` -> `fct_power_law_training`). Status says SOUND and "really done". It is built to avoid the seed-derived cliff chain, and tests pin that (`assert_power_law_no_seed_columns`, `assert_power_law_fit_bounds`). It restricts fits to 2018 to 2024 through a var. It still sits on `int_lap_residual_decomposed`.
4. **`int_sc_hazard_history`** (race-control page and ML survival weight). Reads only `stg_laps` and `stg_track_status`. Two tests including a no-future-leakage test and a probability-bounds test. Season-lagged, so 2018 rates are NULL by design (documented in the export script). Many `COALESCE(... 0)` calls that I did not review one by one.
5. **Lap residual identity** (`int_lap_residual_decomposed` -> `fct_lap_residuals`, used by waterfall, race-lost, team averages). 18 tests including the exact-sum identity (`assert_lap_7term_identity`, `assert_residual_decomposition_identity`). Weak points: eight inputs, constructor term filled with 0.0 where no constructor row exists (now flagged by `constructor_pace_is_filled`), dirty-air tax filled with 0.0 where no row exists. The flagged fill is not excluded in `mart_race_driver_summary` / `mart_driver_season_summary` constructor ranks (they average `constructor_component_s` directly). Since 2026-11-22 the residual also publishes `base_pace_status` (MEASURED, THIN_CELL, NO_CELL) and `base_eligible_lap_count`. `total_explained_s` stays numeric on non-MEASURED laps and is documented as not fully measured there.
6. **Stint-life labels** (`int_stint_end_regime` -> `fct_stint_features`). 4 and 3 tests, including censoring partition and the falloff-slope test that pins the old unit bug fix. Dirty-air fields are now NULL when unmeasured (TX-17). Open: relationships test fails on `race_to_track` (1,107 rows, baseline). Used for the ML stint-life target.
7. **ML `proximity` group** (`int_lap_proximity`). Built from the position sensor, not from speed, so it avoids the follower-speed assumption in `int_lap_air_state`. 5 tests; pit-lane exclusion and crossing order are tested. Open: `assert_proximity_agrees_with_blue_flags` fails on baseline. The admission to the ML contract was measured with permutation controls (see schema.py).
8. **`fuel_mass_kg`** (`int_lap_fuel_state`, 7 tests). Burns fuel evenly over scheduled distance, per race, not per driver. Owner kept this on purpose, with an error bound of about 0.05 s per driver (from older archive data, not the current build). Open: `assert_fuel_load_matches_scheduled_distance` fails on baseline (38 rows). Everything depends on it, so a bad value is costly, but its logic is simple.
   **Update 2026-11-21 (uncommitted, dbt not run):** the `GREATEST` clamp no longer turns a NULL load into 0 kg (the raw value goes through a CASE first). New not_null and range tests cover `fuel_mass_kg`, `weight_penalty_s` and `weight_corrected_lap_time`, plus a singular test (`assert_fuel_mass_null_and_range`) that checks NULL inputs, NULL output, negative or over-limit fuel, and a zero where fuel should remain. The `weight_corrected_lap_time` not_null holds because `is_valid_lap` (`stg_laps.sql`) excludes untimed laps before this model reads them. The fitter's 0.005 floor is removed, so a flat or rising first-stint slope is reported as `NON_IDENTIFIED` and keeps the prior. The seed row for Spain still holds the old floor value (0.005) until a re-fit is promoted.
9. **ML `thermal` group** (`int_lap_thermal_proxy`). Status SOUND, 3 tests, but `assert_push_residual_fuel_neutral` fails on baseline (18,585 rows) and is untriaged. The model has many constant-style fills and clamps (counts from my grep: 11 zero-fills, 14 `LEAST/GREATEST`; I did not read each). The ratio constants must be kept in step with literal weights in the SQL (comment in dbt_project.yml).
10. **Driver rating chain** (`int_driver_race_paired_laps` -> `int_driver_race_skill_loro` -> `int_driver_season_ratings` -> `int_era_normalized_driver_rating` -> `mart_race_driver_summary` / `mart_driver_season_summary`). Has real logic tests and a [unit-test file](../../../transform/models/intermediate/unit_tests_rating_chain.yml) with worked numbers, plus tests for antisymmetry and shrinkage bounds. Weak points: a fixed prior weight of 5, zero-fill for variance when a driver has one race (NULL SE becoming a zero-width interval, HD27), and an input (`int_constructor_car_fe`) whose fit lives in Python and was never checked. `mart_race_coverage` has an open logic case (2021_12 labelled OK with no rating).
11. **ML `compound` and `cliff_prior` groups** (`dim_compounds_season`, `int_compound_cliff_predicted`, 9 tests on the latter). Many cells are not measured: the seed rows are tagged `cross_season_fallback`, and the owner backtest says default cells are about 2x worse than measured ones and biased 12 to 16 laps late. `int_compound_cliff_predicted` prices a lap with no seed cell as a free tyre. The seed has source columns (`fit_source`, `onset_source`) that say which cells are fallbacks, but the ML contract carries only the numeric columns, so the model cannot tell a default from a fit (based on the feature list in schema.py).
12. **Field pace curve and track evolution** (`int_field_pace_curve` 8 tests, `int_track_evolution` 2 existing tests plus 5 added on 2026-11-22). Field pace is "SOUND, really done". Track evolution's slope clamp is now an explicit CASE, so a NULL raw slope stays NULL. The unclamped `rubber_slope_raw_s_per_lap`, `rubber_fit_lap_count` and `rubber_status` (MEASURED, CLAMPED_POSITIVE, INSUFFICIENT_LAPS, NO_FIELD_BASE) are now published. The clamp policy itself is unchanged, so the flat-line effect remains on races with a positive raw slope (62% on an older build; not re-measured). A lap with no pace cell has no row. That is documented, not padded.
13. **Dirty-air chain** (`int_lap_air_state` 7 tests -> `int_dirty_air_tax_component` 10 tests -> dirty-air-cost page, ML `dirty_air` group). Good test coverage including NULL-when-unmeasured. Weak: the gap is estimated using the follower's speed, `dt_s` is not clamped, the uncertainty is declared as a flat 15%, and the model reads bronze telemetry directly. The baseline test `assert_prior_season_labels_frozen` fails on this chain.
14. **Pit strategy chain** (`int_pit_loss_circuit` -> `int_pit_strategy_cost_curve` -> `int_pit_strategy_value` -> pit-strategy page, `fct_stint_features`). Very long (21 CTEs in the last model, six int inputs), fixed constants (stop-loss truncated to 8 to 60 s), new tyre priced from age 1, a free tyre when no curve exists, and `GREATEST(..., 0.0)` that hides a missing opportunity cost. A test pins the baseline units (`assert_pit_cost_curve_baseline_units`).
15. **Tyre-cliff survival and stint-degradation pages.** Display chain is fine, but the numbers come from the defaults in item 11. The app now labels default cells as an estimate with a range, which is the right fix. Still open: promotion of the pooled tier, and the simulator averaging over defaults (queries.ts lines 191 and 192 per the status file; I did not open that file).
16. **Constructor pace, circuit interaction, party mode** (`int_constructor_structural_pace` 2 tests, `int_circuit_x_constructor_interaction` 0 tests, `int_constructor_structural_pace_qualifying` 0 tests). Not neutral to fuel or compound, standard error falls back to 0 when there is one observation (HD27). The interaction model includes car development, not just circuit fit.
17. **Ghost car chain** (`fct_ghost_car_pace` -> `fct_ghost_race_finish`, counterfactual championship, hidden performance). Eight upstream int models and 46 `COALESCE(...)` hits in one file. Now partly defended: the code adds `*_is_prior` flags and a `lap_has_prior_fill` flag, drops low-confidence laps, and has self-consistency tests. It still contains the WRONG `int_constructor_deg_sensitivity` (cliff-onset shift divides a value by itself, per status; I did not re-derive this) and an ego-side constructor term that comes from the 0.0-filled residual column.
18. **Corner skill** (`mart_corner_skill_driver` <- `int_corner_skill_residuals`). The mid-corner unit bug was fixed by measuring corner length (two new models, 8 and 9 passing tests, not audited). No value test pins the units. The mart z-score is not centred, and `int_corner_metrics` uses an exact throttle = 100 test and truncated windows. The sign convention is pinned by a test. Throttle threshold under investigation.
19. **ML `qualifying` group and quali-vs-race page** (`int_qualifying_decomposed` -> `int_qualifying_driver_summary`). Deepest feature chain (about eight models), status WRONG and only partly fixed. Race average is filled with 0.0 in `quali_vs_race_skill_delta_s` (line 145 of the model), `quali_traffic_flag` is always NULL, `dnq_flag` is always FALSE, no test pins the sign. The ML only reads qualifying columns that do not use that 0.0 fill, and 1.9% of rows are missing (7.98% in 2018). `int_qualifying_driver_summary` and `int_qualifying_decomposed` have 0 and 1 tests that touch their own logic. `int_qualifying_driver_summary` grew from 109 to 176 lines today; the status board still describes the older version.
20. **Tyre recovery forecast** (`int_tyre_surface_vs_bulk_decoupling`, 1 test). Missing thermal load imputed as 0.5, and the output "probability" is not fitted.
21. **Degradation envelope and simulator** (`mart_degradation_history_envelope`). Reads an external parquet fit; default coefficients (`temp_headroom_c` 8.0, `temp_penalty_s_per_deg` 0.010, `dirty_air_deg_mult` 1.0) are filled in and shown as if fitted; age and lap index mismatch (status). The `data/fits/.gitkeep` file is deleted in the working tree, so the source parquet's location is worth checking.
22. **Driver skill features, synthetic teammate, data-quality audit, sector decomposition.** `fct_driver_skill_features` has 0 tests that call it; `strategic_divergence_share` is filled with 0.0; NULL proxies sit in a weight divisor (status). `int_synthetic_teammate` has a constant TRUE flag and weights from its own outcome spread. `int_lap_anomaly_flags` uses an unscaled MAD (about 2 sigma) and calls NULL-residual laps normal, and it gates ML training rows. `int_sector_residual_decomposed` uses a different baseline from the lap model.
23. **Models with no reader** (B4). Not ranked for robustness. They cannot hurt a user today. The microsector and physical-ahead chains have many tests; `int_track_geometry` has none and was changed by dividing positions by 10.

---

## D. Where logic is most likely to break (top 10)

1. **`int_lap_residual_decomposed` constructor term filled with 0.0.** Wet races and constructors with no dry clean lap get "average car". The flag exists, but rank and average columns in the two summary marts ignore it, so the 0.0 reads as a real car term.
2. **`int_compound_cliff_predicted` and `dim_compounds_season` default cells.** A lap with no fitted cell is priced as a free tyre or as a default cliff. This feeds the ML cliff and compound features, the field pace curve, the pit-strategy chain, and the ghost car.
3. **`int_lap_fuel_state` even burn.** One assumption sits under 48 downstream models. Bounded at about 0.05 s per driver, but measured on old data, and a baseline test on it still fails. The per-circuit penalty factor is a hand-set prior: the fitter cannot identify it from the data, and none of the current calibrated values is trusted (see item 8 of section B, and the Spain note there). Calibration-policy question still open: whether a factor around 0.001 s/kg is acceptable at all.
4. **`int_track_evolution` slope clamp.** The published rubber slope is still clamped at 0 by policy. Since 2026-11-22 the clamp is an explicit CASE, so a NULL raw slope stays NULL, and the raw slope and a status are published. The earlier figure of 44 downstream models is transitive. Only `int_lap_residual_decomposed` reads the rubber and ambient columns, and it carries them as informational columns outside the residual identity.
5. **`int_stint_geometry` and `stg_lap_tyre_qa`.** Everything is keyed on the stint. A fault in tyre run joining, compound mapping (2018 compound code NULL test fails) or stint 0 affects the ML labels and every tyre page.
6. **`race_to_track` seed gap.** All 19 2026 races are missing, and 26 relationships tests fail on it. The per-model caps to 2025 hide the problem. The ML holdout is pinned to 2026 ([holdout_config.py](../../../ml/src/holdout_config.py)), so ML evaluation depends on 2026 rows that this seed does not cover. I did not check whether 2026 rows exist in the warehouse.
7. **`int_qualifying_decomposed` fills and dead flags.** 0.0 race average, constant flags, no sign test, and it is the parent of seven ML features (only the columns that avoid the 0.0 fill reach the ML).
8. **`int_constructor_deg_sensitivity` (WRONG, open) into `fct_ghost_car_pace`.** The cliff-onset shift has a units fault per the audit, and it drives the ghost-car finishing positions shown in the app.
9. **Zero-width uncertainty (HD27).** Constructor pace, era rating, circuit interaction and the shrinkage models turn a missing standard error into 0, so the app can show a confidence band of no width. `assert_ghost_se_never_zero_filled` covers the ghost car only.
10. **Training gate `int_lap_anomaly_flags` + `int_event_corrections`.** They decide which laps train the ML models. MAD is unscaled (about 2 sigma, so it flags more laps than intended), outlier thresholds come from one fastest lap, and two weights (0.3, 0.6) are unused. A silent change here moves every ML metric. Since 2026-11-22 ML training also requires `base_pace_status = 'MEASURED'` (see B2).

---

## E. Caveats and disagreements

**What I did not verify**
- I did not run dbt, the tests, the ML code or the app. Test pass and fail statements come from the status file's scratch-build record (2026-11-18 and 2026-11-19) and may not match the current working tree.
- I did not query the warehouse, so I have not confirmed row counts, the presence of 2026 data, or whether the `data/fits` parquet files exist.
- Zero-fill and `LEAST/GREATEST` counts in section C come from a text search of the SQL. I read the key ones (residual decomposition, qualifying, track evolution, ghost car, the ML mart) but not every hit.
- Test counts are for singular tests that use `ref('<model>')`. Schema tests (column tests, `dbt_utils` tests, unit tests) were not counted per model.
- I did not read the fit scripts under `transform/tasks/coefficients`, the macros, or the seeds' values. The status file says these were never audited either.
- I did not open the degradation simulator `queries.ts`, so the "averages over defaults" claim is the status file's.
- Which app routes are live and which are stubs: some `routes/*.tsx` files say "STATUS: stub" while a feature folder with the same name has real code (for example `drivers/consistency`, `ml/metrics`). I treated the feature folder as the live code.
- I did not trace `fct_telemetry_deltas`, `driver_network_rating.parquet`, or the assistant's `int_driver_isolation_lap_panel` use beyond a grep.
- The ranking in section C is my judgement. Items near each other could swap.

**Where the code and the status file disagree**
- **Car fixed-effect models.** The status file calls `int_constructor_car_fe` and `_isolation` "SQL pass-throughs of an external fit". In the working tree the SQL files are deleted and replaced by Python models. The docstring of [int_constructor_car_fe.py](../../../transform/models/intermediate/int_constructor_car_fe.py) says the fit now runs inside the warehouse build; `_isolation` still reads its own parquet. "NOT CHECKED" is still true, but the description is out of date, and so is the "109 SQL + 1 Python" count.
- **`int_lap_fuel_state_qualifying`.** Listed as OPEN (hard-coded 12 kg, 0.035 s/kg). The file is deleted, and the header of [int_lap_residual_decomposed_qualifying.sql](../../../transform/models/intermediate/int_lap_residual_decomposed_qualifying.sql) now says there is no fuel term for qualifying. The "fuel 0.42 s constant" note for that model is probably stale. Its status row has not caught up.
- **`stg_session_status`.** Listed as built with no reader. The file is deleted in the working tree, replaced by `stg_red_flags` (new, no reader).
- **`int_stint_power_law_fit`.** Status says no reader. [ml/src/powerlaw_fit.py](../../../ml/src/powerlaw_fit.py) names it as a parity reference, and two transform tests read it. It has no dbt or app consumer, so "orphan" is true only in the narrow sense.
- **Ghost car.** Status says "no ego flag". The code has `host_constructor_pace_is_prior`, `*_deg_slope_is_prior`, `cliff_params_is_prior` and `lap_has_prior_fill`. The ego-side constructor term is still not separately flagged (not fully checked).
- **`fct_stint_features` dirty air.** The code comment says the 0.0 fill was replaced by NULL (TX-17); the status table row for this mart does not mention it.
- **`int_qualifying_driver_summary`** changed from 109 to 176 lines (status note), and its status row is the older "baseline relationships test fails" entry. Whether the new version passes was not checked.
- **`mart_race_driver_summary` / `mart_driver_season_summary`.** Status says "constructor_rank 0.0 fill". The marts do not fill; they average the upstream column that contains the fill. Same effect, different place to fix it (filter on `constructor_pace_is_filled`).
  - **TX-30 closure record 2026-11-21 (uncommitted).** Temporary CI deferral rule recorded in [.github/CONTRIBUTING.md](../../../.github/CONTRIBUTING.md).
    - **Implementation:**
      - Measured-only constructor pace estimates implemented. `constructor_pace_is_filled` added to `fct_lap_residuals` and carried into the summary marts.
      - `mart_race_driver_summary` and `mart_driver_season_summary` use measured-only constructor averages and rankings, and expose `constructor_measured_laps_n` and `constructor_filled_share`.
      - Constructors without measured laps get NULL rankings and `NO_MEASURED_LAPS` in `constructor_rank_status`.
      - `mart_metric_benchmark` excludes prior-filled constructor observations.
      - Constructor-team-averages handles missing measured estimates (blanks, no rank).
      - Sparse-era guard added to `fit_constructor_car_fe.py`: a not-estimable era skips the fit, returns NULL with `not_estimated`, and logs a warning.
      - Miami 2025 partial fixtures and the missing Jolpica and qualifying circuit-info fixtures added (additive, byte-identical to bronze).
      - SQL regression tests and the associated fixture and sign-convention tests updated.
    - **Verified CI result** (the final TX-30 CI-target build, run earlier in this session, not rerun): PASS=1754 WARN=2 ERROR=0 SKIP=0 TOTAL=1759. Both summary marts built. All seven new constructor SQL tests passed. `assert_ai_mart_counts_consistent` passed. Isolation sign-convention and Miami coverage tests passed. Focused Vitest 11/11, Python 21/21, typecheck passed (re-confirmed 2026-11-21 after the citation fix: same results). Two warnings remain: `assert_physical_ahead_reference_lap_sane` and `assert_traffic_exposure_low_measured_share`.
    - **Remaining handoff items:**
      - Three stale app citations corrected in `app/src/assistant/honesty/policy.json` (the citations that `sources.node.test.ts` checks): `DIRTY_AIR_MODELLED_NOT_MEASURED` transform/models/intermediate/schema.yml line 1579 to 1650 (stale before TX-30); `RATING_TRUST_LABEL` transform/models/marts/schema.yml line 2952 to 3077; `RANK_WITHIN_CI` transform/models/marts/schema.yml line 2633 to 2731. Quotes unchanged. `sources.node.test.ts` rerun: 38/38 passed.
      - CI model-hash baseline regenerated and checks clean: 88 hashes changed, 18 models added, 2 removed. Provisionally kept. The changes include historical drift and fixture growth, not only TX-30.
      - Dev warehouse is a 274 KB stub. The dev data-profile baseline, dev hash baseline and app parquet export remain blocked.
      - Reference documentation blocked: missing `meta.family` on `int_physical_ahead_pairs_lapped`. Not changed (needs approval). One partially generated reference page (`docs/reference/models/int/int_constructor_car_fe.mdx`) needs review.
      - Documentation drift deferred: stale counts, seven missing navigation entries, six pages needing review.
      - São Paulo 2021 findings unverified pending updated data and a query against race 2021_19.
      - Constructor fit table reduction from 1,697 to 37 rows requires validation. Not assumed correct or incorrect.
    - **Closure classification:**
      - IMPLEMENTATION COMPLETE: the TX-30 constructor measured-only implementation and associated regression coverage are complete.
      - TARGETED VALIDATION PASSED: `sources.node.test.ts` 38/38, constructor-team-averages Vitest 11/11, Python 21/21, typecheck exit 0, and the earlier CI-target build (PASS=1754, ERROR=0).
      - FULL PROJECT CI: deferred under the temporary project rule. The TX-30 CI-target build passed earlier and must not be rerun unnecessarily.
      - OUTSTANDING: historical validation, constructor fit row-count validation, dev-dependent baselines and exports, reference documentation, and the two outstanding warnings. Not all project-level validation is complete.
- **"DONE" counts.** The status summary counts 31 DONE; the table lists 30 in B1. The header says the graph has 110 models; a count of `.sql` and `.py` files under models is different in the working tree (new physical-ahead and staging models, deleted ones). I did not reconcile this.
- **Assistant stubs.** [heldStubs.ts](../../../app/src/assistant/cards/sql/heldStubs.ts) and [export_app_data.py](../../../scripts/export_app_data.py) name tables that are not models (`fct_constructor_structural_pace`, `int_coast_tax_component`). [verifyParity.ts](../../../app/src/ml/verifyParity.ts) names `int_air_density` and `int_lap_powertrain_signature`, which its own comment says were folded away.

---

## F. Changes since 2026-11-21 (track evolution, rain state, coverage, ML training)

Working tree only, nothing committed. The board entry is TX-33 in [build-log.json](build-log.json), at stage MEASURED (not closed). Open decisions are HD35 to HD39 there. HD40 is resolved.

- **Rain state.** The new model `int_lap_rain_state` gives one row per lap, DRY, WET or NO_WEATHER. It is built from `stg_laps` and `stg_weather` and does not depend on the pace curve. The ten dry-only consumers now test `rainfall_flag = FALSE` on it. Before, `COALESCE(rainfall_flag, FALSE) = FALSE` was applied to the track-evolution signal, and a lap with no pace cell had no evolution row, so it was treated as dry. On the 2018–2025 bronze scratch build this restores 11,896 DRY driver-laps, and 1,001 WET driver-laps stay WET. NO_WEATHER does not occur on real data.
- **Slope observability.** `int_track_evolution` publishes `rubber_slope_raw_s_per_lap`, `rubber_slope_s_per_lap`, `rubber_fit_lap_count` and `rubber_status`. The published value is unchanged apart from NULL-safety. The ambient zero-fill is unchanged.
- **Coverage, without padding.** `int_track_evolution` stays sparse. `int_lap_residual_decomposed` publishes `base_pace_status` (on the bronze scratch build: MEASURED 148,509, THIN_CELL 6,495, NO_CELL 6,402 valid driver-laps) and `base_eligible_lap_count`. The missing coverage comes mostly from first-stint and out-laps, neutralised laps, the dirty-air filter, and two 2018 races with no race telemetry. Field size is rarely the cause.
- **Total explained.** `total_explained_s` stays numeric on THIN_CELL and NO_CELL laps (10,078 laps). It sums the fuel, compound, constructor and dirty-air terms and does not read the pace base, so it is not a fully measured decomposition on those rows. This is documented in schema.yml and pinned by a test.
- **ML training.** `is_training_eligible` now also requires `base_pace_status = 'MEASURED'`. The 39-feature contract is unchanged. `fct_lap_residuals.ml_eligible` is analytical and still includes non-measured laps (HD35).
- **Documentation.** The track-evolution page is rewritten as a pace trend (a linear fit with a capped slope), and ambient is described as driven by track temperature only. Four unsupported claims were removed or made precise, and the reviewer's verdict for that page is recorded.
- **Still open.** HD35 (analytical `ml_eligible`); HD36 (four pre-existing ML test failures, two of them an aggregation-scope audit); HD37 (dev and data-profile baselines); HD38 (driver-workload and model-card wording); HD39 (two hashes from an earlier pass). Full downstream mart validation on real data has not been run.
