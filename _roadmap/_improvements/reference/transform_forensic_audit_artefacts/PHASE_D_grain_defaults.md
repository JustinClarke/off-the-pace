# Phase D — grain, duplication, defaults (2026-09-24)

## D1. Grain (phaseD_grain.py -> phaseD_grain.csv)
Every declared key checked is unique with zero NULL keys: stg_laps, stg_laps_qualifying, stg_results,
stg_results_qualifying, stg_weather, stg_sector_times, stg_pits, int_stint_geometry, int_lap_residual_decomposed,
int_lap_anomaly_flags, int_compound_cliff_predicted, int_lap_thermal_proxy, int_lap_air_state, int_lap_proximity,
int_lap_corner_inputs, int_lap_corner_drift, int_event_corrections, int_lap_telemetry_aggregates, int_lap_fuel_state,
int_field_pace_curve, int_track_evolution, int_qualifying_driver_summary (driver-weekend), int_sc_hazard_history
(circuit x season), int_lap_residual_stint_detrend, int_constructor_structural_pace, race_to_track, dim_circuits,
dim_compounds_season, dim_constructors, dim_drivers, dim_events(event_id), fct_cliff_prediction_features,
fct_stint_features, fct_lap_residuals, fct_driver_skill_features, fct_ghost_car_pace(ghost_id; also
host x race x ego x lap), fct_ghost_race_finish(ghost_race_id; also race x ego x host).
Mart rows 160,207 = int_lap_residual_decomposed rows 160,207 -> no join fan-out. lap_id uniqueness test is not the
only barrier: every joined source is itself unique on its join key.
Race conservation: stg 21/21/17/22/22/22/24/24 -> mart 20/21/17/21/22/22/24/24.
- 2018: 2018_14 (Italian GP) dropped. Cause: race_to_track seed has no 2018_14 row; int_lap_fuel_state.sql INNER JOIN
  race_map (line ~52) and int_compound_cliff_predicted.sql:90 INNER JOIN race_map drop all 927 laps (833 valid).
  fit_compound_cliff.py:111 calls it "a known, unrelated seed gap". The ONLY valid laps lost before the spine.
- 2021: 2021_12 (Belgian GP) -- 60 laps, all neutralised, is_valid_lap FALSE everywhere. Legitimate (charter §3).

## D2. Defaults (phaseD_coalesce_classify.py -> phaseD_coalesce_classified.csv: all 428 sites classified)
Totals: numeric_zero 226, nullif_guard 79, numeric_sentinel 43, column/expr fallback 32, bool 30, string 13,
nullif_other 5. In ML lineage: 202.
Material ones, with fire rates:
1. LABEL: int_lap_residual_decomposed.sql:294 (and 309) pace_delta_s = lap_time_s - COALESCE(base_track_pace_s,
   lap_time_s) -> 0 when int_field_pace_curve has no row. Fires on 14,892 / 160,207 spine laps (9.3%), 171/171 races.
   14,065 have no curve row at all (lap number had no eligible field lap); 827 have a row with NULL value.
   Position: 7,933 mid-race, 4,601 in a race's last 3 laps, 2,358 in laps 1-3. Structural cause: curve eligibility
   (int_field_pace_curve.sql eligible CTE) drops valid_lap_in_stint 1 and the last two valid laps of EVERY stint
   (incl. the final stint, which has no in-lap), and every lap > 107% of the race fastest (whole mixed-condition
   races: 2025_1 100%, 2024_9 76%, 2019_11 75%, 2025_12 80%, 2022_17 68%; rainfall_flag FALSE on most).
   Injected error = -(lap_time - true base): vs nearest non-null base, median 4.22 s, mean 6.35 s, p90 14.9 s.
   9.48% of labelled training rows (9,052 / 95,513; exact count) have such a lap in t..t+5. Those rows: mean label +1.88 vs
   -0.70 s, sd 7.58 vs 3.52, cliff-within-5 share 35.1% vs 18.6%. Not documented anywhere in the tree.
2. FEATURES via int_compound_cliff_predicted.sql:120,124,146,147,152,156,194,196,210 (999 onset / 0 severity /
   0 wear / 0 grip): fire on 1,409 2025 training rows (2025_21 all slicks, 2025_4 MEDIUM, 2025_13 INTERMEDIATE) ->
   cliff_onset_passed FALSE, laps_past_cliff 0, expected_degradation_rate 0 exactly, expected_compound_pace_s =
   temperature term only; AND the same default enters the LABEL via compound_component_s. mart's six compound_*
   columns are NULL there (not defaulted) -- inconsistent handling of one missing cell.
3. track_temp_c COALESCE 30.0 (int_compound_cliff_predicted:110): stg_weather track_temp NULL on 0 training rows.
   Dormant.
4. dirty-air block (int_lap_air_state.sql:182-195, mart 381-386): min_gap_s NULL on 5.5% of training rows/season
   (~1 in 20 = race leader, legitimately free air) but 14.9% in 2018 -> ~9.4% of 2018 rows have no car telemetry
   and receive dirty_air_share 0 / 'free_air'. Season-shaped (2018) fabricated free air.
5. proximity share_* (int_lap_proximity.sql:406-426 COALESCE 0 at source; mart 396-401 never fires): 2018 ~9.7% of
   rows have no position data -> share_* = 0 (fabricated) while gap_ahead_* stay NULL (distinguishable only jointly).
6. quali_push_laps_n COALESCE 0 (mart 459): documented intentional coverage indicator. Accepted.
7. survival_weight COALESCE 1.0 (mart 539): 2018 NULL prior -> 1.0. Documented; not a feature; unused by quantile
   heads (08o). Accepted.
8. event_flag_any, drift_s_per_lap COALESCE: not features (drift barred).
9. theta_air COALESCE(…, 0.1310) (int_dirty_air_tax_component:201): dormant (VAR>0). But see Phase C (global slope).
10. dim_constructors pu_family -> 'unknown_pu' (§4.4): see Phase E.

MISSING_ORDINAL = -1.0 (schema.py:262); _build_encoders assigns 0..k-1 (features.py:61-69) -> no collision;
unseen/NULL -> map() NaN -> fillna(-1.0) (features.py:79). Clean.
