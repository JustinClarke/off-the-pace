# Phase C — leakage sweep (2026-09-24)

Contract width used: ml/src/schema.py FEATURE_COLUMNS = 39 (32 + 7 `qualifying`); PER_TARGET_FEATURE_MASK
removes the 7 for degradation_regressor (p10/p50/p90) and stint_life_regressor -> 32; cliff_classifier 39.

## C1. Window sweep (phaseC_window_sweep.py -> phaseC_windows.csv; 125 windows in 45 lineage models)
Forward-reaching windows (LEAD / FOLLOWING / whole-partition):
- fct_cliff_prediction_features: the target LEADs (expected -- label).
- int_field_pace_curve.field_pace_smoothed_s: ROWS 2 PRECEDING AND 2 FOLLOWING (line ~100). Feeds base_track_pace_s
  (label spine), int_track_evolution (label spine AND quali feature via weather_proxy), int_lap_normalized_pace
  (seed fitter input), int_dirty_air_tax_component, int_constructor_structural_pace (label spine). Reaches NO
  contract feature directly. Covered by the 08 "race-scoped spine" acceptance (label side only).
- int_event_corrections.next_lap_is_controlled (LEAD): correction_weight -> event_flag_any (not a feature).
- int_dirty_air_tax_component.dirtiest_air_lap_in_race_flag (whole race): not consumed by mart.
- int_lap_proximity LEAD(driver_id/crossing) -- car behind at the same track bin, same lap: seconds, not laps. OK.
- int_lap_telemetry_aggregates stint-whole partition: no contract feature reads telemetry aggregates since Phase 9.
- int_stint_geometry stint_length_actual/valid (whole stint): label spine (field-pace in-lap exclusion), not features.
- int_qualifying_segments / stg_track_status LEADs: within-session, not features.
Verdict: no forward-reaching WINDOW on any contract feature's chain. Clean for windows.

## C2. Offline fits
- data/fits/constructor_car_fe.parquet -> int_constructor_car_fe -> int_driver_race_skill_loro.driver_skill_field_s
  -> int_driver_circuit_era_affinity (app Ghost Car Standings). NOT on ML lineage. data_window 2018_to_2024, fit 07-07.
  2025: 0 rows -> driver_skill_field_s NULL for all 459 2025 driver-races -> affinity WHERE ... IS NOT NULL silently
  drops 2025 (post2022 era max seasons_observed_n = 3). App surface finding, see Phase F.
- data/fits/degradation_isotonic.parquet -> mart_degradation_history_envelope (app simulator). NOT on ML lineage.
  data_window 2018_to_2024, fit 06-15. Stale vs 2025.
- seeds/compound_cliff_params.csv (fit_compound_cliff.py + survival.py) -> dim_compounds_season -> mart 6 compound_*
  columns directly, and int_compound_cliff_predicted -> expected_compound_pace_s, expected_degradation_rate_s_per_lap,
  cliff_onset_passed, laps_past_cliff (features) AND compound_component_s (label spine) AND anomaly_class
  (clean_cliff vs mistake -> is_training_eligible).
  * Fit unit = (track_id, compound, season). VERIFIED every one of 171 (track_id, season) cells in the mart is ONE race.
    So a cox_km_survival cell is fitted on exactly the race it is joined back onto, including the scored stint's
    own future laps (KM median of the age at which a >0.5 s spike vs trailing median persists 2 laps; severity from
    [onset, onset+5] vs [onset-5, onset-1]; wear slope on ages 3..onset-2).
  * Training-eligible rows by fit_source: 2018-2024 cox_km_survival 116,385 (97.1%), cross_season_fallback 2,827
    (pooled 2018-2024 -> crosses season split for every fold but the last), class default 570;
    2025 carried_forward_2024 18,248, class default 508, NO CELL 1,409.
  * Only wear_gradient, onset, severity vary. grip_peak / optimal_temp_low/high are ONE value per compound
    (constants; carry no temporal info beyond `compound`, except their NULL pattern on 2025 missing cells).
  * 08l ruled "seed_bias(t) is not a leak: a real model has ... season (hence every compound-curve parameter) ...
    at prediction time" (work/08:2244). That sentence assumes the parameters are available pre-race; the fit
    population was not examined. NEW EVIDENCE: they are fitted on the scored race. 00c's standard
    (contemporaneous-with-target = leakage for a feature) applies; the 08 "race-scoped spine" acceptance covers
    the label decomposition, not features.
  * Train/eval asymmetry: v14's 2025 eval fold is scored with LAGGED (carried-forward) params while every
    training row carries IN-RACE params. v13's published 2024 fold was scored with in-race params.
    => v14's cv_final_fold is the more honest number; v13 and earlier folds are plausibly optimistic. UNMEASURED.

## C3. Cross-season pooled statistics
- theta_air (int_dirty_air_tax_component.sql:195-206): ONE global OLS slope over all seasons, no season key.
  Label-side (dirty_air_tax_s -> driver_skill_residual_s). VERIFIED by re-running the compiled production SQL:
  theta(all incl 2025) = 0.152123 (implied by built table, 0.152123), theta(<=2024) = 0.131000 (= the v13 value
  quoted in schema.py/08q), theta(<=2023) = 0.162842. So the 2025 ingest re-labelled 2018-2024: mean |shift| in
  next_5_lap_cumulative_jump_s ~0.019-0.023 s, 16-19% of eligible rows move >50 ms (label sd 3.3-5.0 s).
  schema.py MODEL_VERSION_DEFAULT note "v14 IS comparable to v13 head-to-head at fixed target ... nothing about
  the label definition moves here" is FALSE. Also: the eval fold's labels are defined with a slope fitted on
  the eval fold.
- int_driver_circuit_era_affinity / int_era_normalized_driver_rating / int_driver_circuit_affinity: pool every
  season (survey) -- off ML lineage, app-descriptive. int_sc_hazard_history: season-lagged, in lineage but not in
  the 39. Survival weights: season-lagged (08f-1), not a feature and not used for quantile heads (08o).

## C4. Label lineage
- drift_s_per_lap consumed only by the mart label + cliff_scan; barred; nothing else reads it (grep). Clean.
- is_training_eligible = age>3 AND anomaly_class NOT IN (mistake, conditions). mistake vs clean_cliff differ ONLY
  by cliff_onset_passed (int_lap_anomaly_flags.sql:235-243) -> the in-race seed decides whether a residual spike
  row is trained on. Eligibility also conditions on residual(t) (mad_score>3 AND residual>trailing median), a
  label term (label subtracts 5*residual(t)). Label means (age>3): normal -0.43, mistake -5.03 (excluded, 4,262
  labelled), clean_cliff -7.87 (kept, 866 labelled), event_driven +0.44 (kept), conditions -0.66 (excluded).

## C5. Split / encoders
- _build_encoders on train rows only (features.py:62-69, called 167 on train_df). With holdout empty, "train"
  = all 2018-2025 -> for v14 the encoders see 2025 (Phase A: no 2025-only compound level; harmless).
- Season folds: whole seasons (train.py:179-196); stints never cross races -> 5-lap overlap cannot cross a fold.
  Within-season row-split would leak 4/5 of the label window; not used in production. Clean.

## C6. Information-timestamp table -> see AUDIT_REPORT.md §5 (39 rows)
Forward/contemporaneous members: fuel_mass_kg (end of race, 12/172 races differ), compound_wear_gradient,
compound_cliff_onset_laps, compound_cliff_severity, expected_compound_pace_s, expected_degradation_rate_s_per_lap,
cliff_onset_passed, laps_past_cliff (end of race via seed, 2018-2024), quali_skill_session_avg_s (race-day
track evolution + in-race seed). All others: end of lap t or earlier.

## C7. Fuel
int_lap_fuel_state.sql race_lap_counts = MAX(lap_number) over laps WHERE is_valid_lap (lines ~26-33, 39).
fuel_mass_kg = rate*(race_lap_count - lap_number + 1). 12 of 172 races have MAX(valid) < MAX(all)
(fuel_race_lap_count_gap.csv): 2019_2 (3), 2020_15 (3), 2022_16 (6), 2023_3 (5), 2025_10 (4), + seven 1-lap.
The declared exemption (intermediate schema.yml) says the proxy diverges "only where a race is stopped early"
and "has NOT been measured": wrong premise (valid-lap filter also diverges when the finish is neutralised) and
now measured. Also 2022_18 (29 laps run, rain-shortened) prices fuel for 28 laps. Correct value computable
from dim_circuits.lap_length_km (scheduled distance).
