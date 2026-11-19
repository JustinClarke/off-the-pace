# Transform status board

Updated 2026-11-19. Graph: 110 models (109 SQL + 1 Python). Nothing here is committed; all changes are working-tree state.

## A. Summary

Session note (2026-11-19): stg_laps, stg_laps_qualifying, stg_pits edited (working tree only). Verified by a scratch build from data/_archive-2026-11-14/dev.duckdb (stale copy): the three models build; their own tests pass except relationships tests and missing-table errors that match the baseline. Full pipeline not rebuilt; downstream effect unmeasured. Throttle threshold in int_corner_metrics: under investigation (not changed).

Fuel note (2026-11-19): `int_lap_fuel_state` burns fuel evenly over the scheduled race distance, not per driver or per lap; kept on purpose. Error bound about 0.05 s per driver in plausible cases, from three checks on an older archive copy (not the current build):
- Field-wide fuel policies shift race skill by at most about 0.14 s; ranks move in 2% to 5% of driver-races.
- A 2 kg teammate saver shifts the within-team gap about 0.025 s (sign flips in about 2% of team-races); 4 kg, about 0.05 s (about 4%).
- Dropping lift-and-coast laps costs about 0.015 s on average and reshuffles close drivers; no sign of team-ordered lifts.
A telemetry-based per-driver fuel proxy did not help (fuel mass moved 1 to 2 kg at the median; teammate test slightly worse) and was not pursued.

| Measure | Count |
|---|---|
| Models in the graph | 110 |
| Audited (fresh audit, read-only) | 108 |
| Not in the audit (added after it) | 2 (`int_corner_lap_measured`, `int_corner_length_measured`) |
| Audit verdicts | SOUND 55, QUESTIONABLE 47, WRONG 6 |
| WRONG fixed (change confirmed in the file, model built; no value test except fct_stint_features) | 3 (`int_corner_skill_residuals`, `fct_stint_features`, `int_track_geometry`) |
| WRONG partly fixed | 1 (`int_qualifying_decomposed`: sign flipped, 0.0 fill and dead flags open) |
| WRONG still open | 2 (`int_constructor_deg_sensitivity`; `stg_lap_tyre_qa`, accepted as DQ-01) |
| Status DONE | 31 (19 really done, 12 with caveat) |
| Status OPEN | 79 (see B2; includes UNVERIFIED and NOT CHECKED) |
| Status FIXED-NOT-VERIFIED | 0 |
| Status NOT CHECKED | 4 (2 new corner models, 2 car-FE pass-throughs) |

Status key. DONE: a fix verified by the scratch build and tests, or audit SOUND with nothing open (no fix needed). OPEN: audit finding still in the file, or a test fails. NOT CHECKED: not in the audit, or its values come from outside the audit.

Evidence for DONE: scratch build `scratchpad/implementation-build/` (13:11 to 13:32 on 2026-11-18, built after the last model edit at 13:10:59): `dbt run` PASS=92 of 92 built, `dbt test` PASS 1086, WARN 3, ERROR 41. 18 fits-dependent models were excluded from the run (`--exclude source:fits+`), none of them downstream of a changed model. The 41 failures match the clean baseline by name and row count (build-log entry 2026-11-18T23:59:30); the cause of `assert_prior_season_labels_frozen` and `assert_rain_flag_matches_tyres` is undetermined.

Graph method: the scratch `target/manifest.json` of that build (110 models, includes the two new corner models, newest of the manifests found). Not `transform/target/manifest.json`, which is stale. The 18 models not rebuilt: fct_driver_isolation_lap/pair_lap/race/stint, int_constructor_car_fe, int_constructor_car_fe_isolation, int_driver_circuit_affinity, int_driver_circuit_era_affinity, int_driver_isolation_lap_pace, int_driver_isolation_lap_values, int_driver_isolation_stint_tyre, int_driver_race_skill_loro, int_driver_season_ratings, int_era_normalized_driver_rating, mart_degradation_history_envelope, mart_driver_season_summary, mart_race_coverage, mart_race_driver_summary. Their tests ran against the copied tables, so treat those rows as read-audit only.

## B. Model table (110 rows, split by status)

### B1. Done (31)

| model | layer | audit verdict | status | what is open | feeds (direct dbt) | downstream (all) | reaches |
|---|---|---|---|---|---|---|---|
| stg_events | staging | SOUND | ✅ REALLY DONE | none | - | 0 | none |
| stg_laps | staging | QUESTIONABLE | ✅ DONE WITH CAVEAT | fixed: is_valid_lap wrapped in COALESCE(...,FALSE); no NULLs in scratch build; full pipeline not rebuilt | dim_corners, dim_drivers, fct_ghost_car_pace, fct_ghost_race_finish, fct_pit_stop_crosscheck (+28) | 82 | app; via ML/assistant/export |
| stg_laps_qualifying | staging | QUESTIONABLE | ✅ DONE WITH CAVEAT | fixed: is_valid_lap wrapped in COALESCE(...,FALSE); no NULLs in scratch build; full pipeline not rebuilt | fct_speed_traps, fct_speed_traps_season, fct_track_limits, fct_track_limits_driver_session, int_lap_fuel_state_qualifying (+3) | 13 | via ML/app/assistant/export |
| stg_pits | staging | QUESTIONABLE | ✅ DONE WITH CAVEAT | fixed: compound CASE maps NONE/NAN/UNKNOWN/NULL/'' to NULL, same as stg_laps; full pipeline not rebuilt | fct_pit_stop_crosscheck, int_lap_proximity, int_microsector_proximity, int_pit_loss_circuit, int_pit_strategy_value (+1) | 67 | assistant (comment only), export; via ML/app |
| stg_tyre_allocations | staging | SOUND | ✅ REALLY DONE | none | int_stint_geometry | 64 | via ML/app/assistant/export |
| int_cell_power_law_fit | intermediate | SOUND | ✅ DONE WITH CAVEAT | none | fct_power_law_training | 1 | via ML/app |
| int_corner_skill_residuals | intermediate | WRONG | ✅ DONE WITH CAVEAT | fixed: mid-corner term uses measured length; units not pinned by a test | int_corner_drift_from_early_stint, int_lap_corner_inputs, mart_corner_skill_driver | 6 | export; via ML/app/assistant |
| int_driver_isolation_lap_panel | intermediate | SOUND | ✅ REALLY DONE | none | int_driver_isolation_lap_pace | 7 | assistant; via export |
| int_field_pace_curve | intermediate | SOUND | ✅ REALLY DONE | none | int_constructor_structural_pace, int_dirty_air_tax_component, int_driver_race_skill_loro, int_lap_normalized_pace, int_lap_residual_decomposed (+1) | 45 | app, export; via ML/assistant |
| int_lap_corner_drift | intermediate | SOUND | ✅ DONE WITH CAVEAT | none | fct_cliff_prediction_features | 2 | via ML/app/assistant/export |
| int_lap_corner_inputs | intermediate | SOUND | ✅ DONE WITH CAVEAT | none | fct_cliff_prediction_features | 2 | via ML/app/assistant/export |
| int_power_law_lap | intermediate | SOUND | ✅ REALLY DONE | none | fct_power_law_training, int_cell_power_law_fit, int_stint_power_law_fit | 3 | ML; via app |
| int_sc_hazard_history | intermediate | SOUND | ✅ REALLY DONE | none | fct_cliff_prediction_features, int_pit_strategy_cost_curve | 6 | app, assistant, export; via ML |
| int_stint_power_law_fit | intermediate | SOUND | ✅ DONE WITH CAVEAT | none | - | 0 | none |
| int_traffic_exposure_driver_race | intermediate | SOUND | ✅ REALLY DONE | none | int_traffic_exposure_race | 1 | none |
| int_traffic_exposure_race | intermediate | SOUND | ✅ REALLY DONE | none | - | 0 | none |
| fct_lap_residuals | marts | SOUND | ✅ REALLY DONE | none | mart_build_provenance, mart_driver_season_summary, mart_metric_benchmark, mart_race_coverage, mart_race_driver_summary | 5 | ML (comment only), app, assistant, export |
| fct_power_law_training | marts | SOUND | ✅ REALLY DONE | none | - | 0 | ML, app (comment only) |
| fct_stint_features | marts | WRONG | ✅ DONE WITH CAVEAT | fixed: slope uses residual laps only; new test passes; own relationships test to race_to_track fails (1107 rows, baseline) | - | 0 | ML, app, assistant, export |
| mart_build_provenance | marts | SOUND | ✅ REALLY DONE | none | - | 0 | assistant (comment only), export |
| mart_metric_benchmark | marts | SOUND | ✅ REALLY DONE | none | - | 0 | assistant, export |
| dim_circuits | reference | SOUND | ✅ DONE WITH CAVEAT | none | dim_corners, fct_cliff_prediction_features, fct_driver_skill_features, int_lap_fuel_state, int_pit_loss_circuit (+4) | 62 | app, assistant, export; via ML |
| dim_compounds_season | reference | SOUND | ✅ REALLY DONE | none | fct_cliff_prediction_features, int_compound_cliff_predicted, int_constructor_deg_sensitivity, int_lap_residual_decomposed_qualifying, int_pit_strategy_cost_curve | 51 | app, assistant, export; via ML |
| dim_corners | reference | SOUND | ✅ REALLY DONE | none | int_corner_lap_measured, int_corner_length_measured, int_corner_metrics, int_microsector_corner_class | 12 | via ML/app/assistant/export |
| dim_driver_seasons | reference | SOUND | ✅ REALLY DONE | none | - | 0 | none |
| fct_pit_stop_crosscheck | new_data | SOUND | ✅ DONE WITH CAVEAT | none | - | 0 | none |
| fct_speed_traps | new_data | SOUND | ✅ REALLY DONE | none | - | 0 | none |
| fct_speed_traps_season | new_data | SOUND | ✅ REALLY DONE | none | - | 0 | none |
| fct_track_limits | new_data | SOUND | ✅ REALLY DONE | none | fct_track_limits_driver_session | 1 | none |
| fct_track_limits_driver_session | new_data | SOUND | ✅ REALLY DONE | none | - | 0 | none |
| int_track_geometry | intermediate | WRONG | ✅ DONE WITH CAVEAT | curvature guards G3 present in source; the 8.7e12 figure may predate them; re-check values | - | 0 | none |

#### Temporary list: staging items handed off (2026-11-19, 2018 to 2025 only)

Track these here until the build log takes them over. Each item is open unless marked.

- [x] **stg_lap_tyre_qa:** lap-1 pit gives stint 0 on 3 driver-races (`first_stint_number - 1`). Three laps with no stint are marked OK. Fix the stint logic and quarantine NULL-stint laps. Reaches `int_stint_geometry` and about 64 downstream models. Fixed 2026-11-19: lap-1-pit driver-races shift stint ordinals up by one (no stint 0); driver-races with no assigned lap are `quarantined_driver` (pit ordinal); new test `assert_lap_tyre_qa_stint_valid`. Verified on the archived 2026-11-08 warehouse only; downstream 64 models not rebuilt.
- [x] **stg_tyre_allocations:** 2025 Miami (`2025_6`) has no row, so 1,005 laps have no compound. Needs a Pirelli source, or a labelled carry-forward. Reaches `int_stint_geometry`. Fixed 2026-11-19: labelled carry-forward row `2025 miami_grand_prix C2/C3/C4 carried_from_2024` (152 seed rows, 24 for 2025); 2025 rows remain unverified carry-forwards pending a Pirelli source. Miami lap-level compounds stay NULL because the race is quarantined at source (stale FastF1 stints); new tests pin this. Verified on the bronze-backed scratch build only; downstream models not rebuilt.
- [x] **stg_weather wet vote:** 870 laps wet with under 10% on wets, 430 dry with at least half on wets. Tyres alone should not decide wet. A NULL tyre share counts as no evidence, not zero votes. Stale samples (over 120 s) should be flagged. Reaches `int_compound_cliff_predicted`, `int_pit_strategy_cost_curve`, `int_track_evolution`.
  - Done: wet needs tyres plus rain or humidity; NULL tyre share abstains; `weather_sample_stale` flags samples over 120 s. The 870 are now dry (0 left). The 430 laps (most of the field on wets, no rain, humidity under 70%) stay dry by design: owner ruled the rules work as they should. Verified on the bronze scratch build only; downstream not rebuilt.
- [x] **stg_circuit_info:** file pattern skipped qualifying-session files, so 2018 Australia, Bahrain and Italy and 2026 Monaco had no corners. Fixed: race file preferred, qualifying file used as fallback only where no race file exists (`stg_circuit_info.sql`, new source `raw_circuit_info_quali`, new test `assert_circuit_info_every_race_has_corners`). Verified 2018-25 against bronze. Not yet rebuilt through `dim_corners` in a full run. Reaches `dim_corners`.
- [x] **stg_telemetry:** scope decided race-only; header corrected (it claimed qualifying sessions, the glob reads race files only). Qualifying telemetry deferred to TX-23 (`stg_telemetry_qualifying`). Runaway distances stay bounded by the existing per-circuit bound. Reaches `int_corner_lap_measured`, `int_corner_metrics`, `int_lap_telemetry_aggregates`.
- [x] **stg_results_qualifying:** 2025 Miami has no segment times for any driver, so each gets "none". Fixed by flag, not derivation: new `segment_source` column is `missing_from_feed` for that race (derived from null times; position-based derivation disagreed with official times in about 150 rows). Reaches `int_qualifying_segments`, which should skip `missing_from_feed` races. App message tracked as AP-11 in BUILD-ORDER.
- [x] **stg_sector_times:** sectors with no time were dropped silently (5,553 of 631,980 sector rows, 0.9%). Now kept with `sector_time_missing = TRUE`, so the 3-rows-per-lap grain holds. `int_corner_skill_residuals` filters the flag, so its output is unchanged. 2025 Miami trap speeds are present in bronze race and qualifying laps (1,002 of 1,005 race laps), so the "trap speed missing" note did not reproduce. Reaches `int_corner_skill_residuals`, `int_sector_residual_decomposed`.
- [x] **stg_telemetry_position:** 16,708 samples had no RelativeDistance and were dropped; they are now kept, with the fraction derived from distance_m over the lap's max distance (`relative_distance_source = 'derived_from_distance_m'`). Derived values are approximate (mean error 0.002 where both exist). Clamps are no longer silent: 25,526 low and 158,831 high are flagged in `relative_clamp` (the old comment said "a handful"). Scratch build: 75,243,066 rows, none null. Reaches `int_lap_proximity`, `int_microsector_corner_class`, `int_microsector_crossings`. Downstream output has NOT been re-measured; 16,708 extra samples may shift proximity results.
- [ ] **stg_session_status:** 2025 Belgium red flag not recorded as aborted. Source red flags from track status. No direct readers.
- [ ] **stg_jolpica_pit_stops:** no tests; add them. Only the scratch cross-check reads it.
- [ ] **Owner rulings needed:** 2021 Belgian GP has no tyre data in bronze (rain-flag test fails); Miami compound source; wet-flag rule; whether qualifying telemetry is in scope.
- [ ] **Reverted?** The NULL changes in `int_lap_residual_decomposed` (constructor term) and `int_compound_cliff_predicted` (compound term) are still in the working tree and drop about 6,400 laps. Decide before anything else lands.

### B2. Pending (79)

| model | layer | audit verdict | status | what is open | feeds (direct dbt) | downstream (all) | reaches |
|---|---|---|---|---|---|---|---|
| int_driver_isolation_lap_pace | intermediate | SOUND | UNVERIFIED | none | int_driver_isolation_lap_values, int_driver_isolation_stint_tyre | 6 | via assistant/export |
| int_driver_isolation_lap_values | intermediate | SOUND | UNVERIFIED | none | fct_driver_isolation_lap, fct_driver_isolation_pair_lap | 4 | via assistant/export |
| int_driver_isolation_stint_tyre | intermediate | SOUND | UNVERIFIED | none | fct_driver_isolation_race, fct_driver_isolation_stint, int_driver_isolation_lap_values | 5 | via assistant/export |
| int_driver_race_paired_laps | intermediate | SOUND | OPEN | none | int_driver_race_skill_loro, mart_race_driver_summary | 8 | via app/assistant/export |
| int_driver_race_skill_loro | intermediate | SOUND | UNVERIFIED | none | int_driver_circuit_affinity, int_driver_circuit_era_affinity, int_driver_season_ratings, mart_race_coverage, mart_race_driver_summary | 7 | app, export; via assistant |
| fct_driver_isolation_pair_lap | marts | SOUND | UNVERIFIED | none | fct_driver_isolation_lap, fct_driver_isolation_race, fct_driver_isolation_stint | 3 | via assistant/export |
| mart_race_coverage | marts | SOUND | OPEN | 2021_12 labelled OK with no rating and no racing laps (logic review) | mart_race_driver_summary | 2 | app, assistant, export |
| stg_circuit_info | staging | SOUND | OPEN | baseline relationships test fails (274 rows, race_to_track seed gap), untriaged | dim_corners | 13 | via ML/app/assistant/export |
| stg_jolpica_pit_stops | staging | SOUND | OPEN | no tests | fct_pit_stop_crosscheck | 1 | none |
| stg_lap_tyre_qa | staging | WRONG | OPEN | stint 0 on 3 driver-races; accepted as DQ-01, no code change | int_pit_strategy_value, int_sector_residual_decomposed, int_stint_geometry, mart_race_coverage | 64 | via ML/app/assistant/export |
| stg_race_control | staging | SOUND | OPEN | baseline relationships test fails (3346 rows, race_to_track seed gap), untriaged | int_stint_geometry | 64 | via ML/app/assistant/export |
| stg_results | staging | QUESTIONABLE | OPEN | DNF misses ~69 classified retirements; default cause mechanical | fct_ghost_race_finish, int_lap_proximity, int_pit_loss_circuit, int_stint_end_regime, int_stint_geometry (+2) | 66 | assistant, export; via ML/app |
| stg_results_qualifying | staging | SOUND | OPEN | baseline relationships test fails (440 and 80 (dim_constructors) rows, race_to_track seed gap), untriaged | int_qualifying_segments | 8 | via ML/app/assistant/export |
| stg_sector_times | staging | SOUND | OPEN | baseline relationships test fails (65889 rows, race_to_track seed gap), untriaged | int_corner_skill_residuals, int_sector_residual_decomposed | 8 | via ML/app/assistant/export |
| stg_session_status | staging | SOUND | OPEN | baseline relationships test fails (101 rows, race_to_track seed gap), untriaged | - | 0 | none |
| stg_session_status_qualifying | staging | SOUND | OPEN | baseline relationships test fails (242 rows, race_to_track seed gap), untriaged | int_qualifying_segments | 8 | via ML/app/assistant/export |
| stg_telemetry | staging | SOUND | OPEN | baseline relationships test fails (14625196 rows, race_to_track seed gap), untriaged | int_corner_lap_measured, int_corner_metrics, int_lap_telemetry_aggregates | 15 | app (comment only); via ML/assistant/export |
| stg_telemetry_position | staging | SOUND | OPEN | baseline relationships test fails (7374946 rows, race_to_track seed gap), untriaged | int_lap_proximity, int_microsector_corner_class, int_microsector_crossings | 6 | via ML/app/assistant/export |
| stg_track_status | staging | SOUND | OPEN | baseline relationships test fails (350 rows, race_to_track seed gap), untriaged | int_microsector_proximity, int_pit_loss_circuit, int_sc_hazard_history | 9 | app; via ML/assistant/export |
| stg_weather | staging | SOUND | OPEN | baseline test assert_rain_flag_matches_tyres fails (1 row), untriaged | int_compound_cliff_predicted, int_pit_strategy_cost_curve, int_track_evolution | 50 | via ML/app/assistant/export |
| int_circuit_x_constructor_interaction | intermediate | QUESTIONABLE | OPEN | deviation includes car development; SE 0 for n=1 (HD27) | fct_ghost_car_pace | 2 | app, export; via assistant |
| int_compound_cliff_predicted | intermediate | QUESTIONABLE | OPEN | no-seed-cell laps priced as a free tyre (HD25) | fct_cliff_prediction_features, fct_ghost_car_pace, int_constructor_deg_sensitivity, int_dirty_air_tax_component, int_field_pace_curve (+3) | 48 | export; via ML/app/assistant |
| int_constructor_car_fe | intermediate | SOUND | NOT CHECKED | values come from external fit, never checked | int_driver_race_skill_loro | 8 | via app/assistant/export |
| int_constructor_car_fe_isolation | intermediate | SOUND | NOT CHECKED | values come from external fit, never checked | int_driver_isolation_lap_pace | 7 | via assistant/export |
| int_constructor_deg_sensitivity | intermediate | WRONG | OPEN | cliff-onset shift divides s by s (plan TX-32, HD29-HD34 open) | fct_ghost_car_pace | 2 | via app/assistant/export |
| int_constructor_structural_pace | intermediate | QUESTIONABLE | OPEN | not fuel/compound-neutral; SE 0 fallback (HD27) | fct_driver_skill_features, fct_ghost_car_pace, int_circuit_x_constructor_interaction, int_lap_residual_decomposed | 34 | app, export; via ML/assistant |
| int_constructor_structural_pace_qualifying | intermediate | QUESTIONABLE | OPEN | SE 0, zero-width CI for n=1 (HD27) | int_lap_residual_decomposed_qualifying | 5 | app, export; via ML/assistant |
| int_corner_drift_from_early_stint | intermediate | QUESTIONABLE | OPEN | baseline includes lap 1; mid-corner term now measured upstream | int_lap_corner_drift | 3 | via ML/app/assistant/export |
| int_corner_lap_measured | intermediate | not audited (new) | NOT CHECKED | new model, not in audit; 8 tests pass | int_corner_length_measured, int_corner_skill_residuals | 8 | via ML/app/assistant/export |
| int_corner_length_measured | intermediate | not audited (new) | NOT CHECKED | new model, not in audit; 9 tests pass | int_corner_skill_residuals | 7 | via ML/app/assistant/export |
| int_corner_metrics | intermediate | QUESTIONABLE | OPEN | exact throttle_pct = 100, truncated windows (audit item still in file) | fct_telemetry_deltas, int_corner_skill_residuals | 8 | export; via ML/app/assistant |
| int_dirty_air_tax_component | intermediate | QUESTIONABLE | OPEN | SE declared 15%; baseline test prior_season_labels_frozen fails | fct_stint_features, int_driver_isolation_lap_panel, int_lap_residual_decomposed, mart_driver_season_summary, mart_metric_benchmark (+1) | 33 | app, assistant (held stub only), export; via ML |
| int_driver_circuit_affinity | intermediate | QUESTIONABLE | OPEN | fixed prior weight 5; sigma2 zero-fill for n=1 (HD27) | - | 0 | app, export |
| int_driver_circuit_era_affinity | intermediate | QUESTIONABLE | OPEN | as affinity, plus era_label 2022-2024 covers 2025 | - | 0 | app, export |
| int_driver_season_ratings | intermediate | QUESTIONABLE | OPEN | fixed prior weight 5; sigma2 zero-fill (HD27) | int_era_normalized_driver_rating | 2 | app (comment only); via assistant/export |
| int_era_normalized_driver_rating | intermediate | QUESTIONABLE | OPEN | NULL SE becomes zero-width CI (HD27) | mart_driver_season_summary | 1 | app, assistant, export |
| int_event_corrections | intermediate | QUESTIONABLE | OPEN | outlier thresholds off one fastest lap; weights 0.3/0.6 unused | fct_cliff_prediction_features, int_constructor_structural_pace, int_dirty_air_tax_component, int_driver_race_paired_laps, int_driver_race_skill_loro (+3) | 44 | via ML/app/assistant/export |
| int_lap_air_state | intermediate | QUESTIONABLE | OPEN | gap uses follower speed; dt_s unclamped | fct_cliff_prediction_features, fct_stint_features, int_dirty_air_tax_component, int_driver_isolation_lap_panel, int_field_pace_curve (+4) | 47 | app, assistant (comment only), export; via ML |
| int_lap_anomaly_flags | intermediate | QUESTIONABLE | OPEN | unscaled MAD (~2 sigma); NULL-residual laps called normal | fct_cliff_prediction_features, fct_driver_skill_features, fct_stint_features, int_driver_isolation_lap_panel, int_lap_telemetry_aggregates | 13 | app, export; via ML/assistant |
| int_lap_fuel_state | intermediate | QUESTIONABLE | OPEN | even burn assumed by design; bounded at about 0.05 s per driver (2026-11-19); telemetry proxy tested, not used; fuel_delta_vs_expected removed. Caveat handled, status left OPEN (baseline test assert_fuel_load_matches_scheduled_distance still fails (38)) | fct_power_law_training, fct_stint_features, int_constructor_structural_pace, int_dirty_air_tax_component, int_driver_race_paired_laps (+6) | 48 | via ML/app/assistant/export |
| int_lap_fuel_state_qualifying | intermediate | QUESTIONABLE | OPEN | hard-coded 12 kg, 0.035 s/kg (HD26) | int_lap_residual_decomposed_qualifying | 5 | via ML/app/assistant/export |
| int_lap_normalized_pace | intermediate | QUESTIONABLE | OPEN | pooled slope confounded; fallback 0.004 (HD26) | - | 0 | none |
| int_lap_physical_ahead | intermediate | SOUND | OPEN | 3 warn tests (110, 36, 3 rows), untriaged | int_traffic_exposure_driver_race | 2 | none |
| int_lap_proximity | intermediate | QUESTIONABLE | OPEN | per-lap distance bins; baseline test proximity_agrees_with_blue_flags fails | fct_cliff_prediction_features | 2 | app (comment only); via ML/assistant/export |
| int_lap_residual_decomposed | intermediate | QUESTIONABLE | OPEN | constructor term 0.0 fill; dirty-air 0.0 where no row (HD25) | fct_cliff_prediction_features, fct_driver_skill_features, fct_ghost_car_pace, fct_lap_residuals, fct_stint_features (+9) | 32 | ML, app (comment only); via assistant/export |
| int_lap_residual_decomposed_qualifying | intermediate | QUESTIONABLE | OPEN | zero residual for baseless laps; fuel 0.42 s constant (HD25, HD26) | int_qualifying_decomposed | 4 | via ML/app/assistant/export |
| int_lap_residual_stint_detrend | intermediate | QUESTIONABLE | OPEN | no weight filter; 0.0 conflates no data and zero slope | fct_cliff_prediction_features | 2 | via ML/app/assistant/export |
| int_lap_telemetry_aggregates | intermediate | QUESTIONABLE | OPEN | baseline includes scored lap (leakage), SC laps | fct_cliff_prediction_features, fct_driver_isolation_lap | 5 | via ML/app/assistant/export |
| int_lap_thermal_proxy | intermediate | SOUND | OPEN | baseline test assert_push_residual_fuel_neutral fails (18,585), untriaged | fct_cliff_prediction_features, fct_stint_features, int_tyre_surface_vs_bulk_decoupling | 4 | via ML/app/assistant/export |
| int_microsector_corner_class | intermediate | SOUND | OPEN | baseline test corner_class_covers_panel fails (2), untriaged | - | 0 | none |
| int_microsector_crossings | intermediate | SOUND | OPEN | shares failing baseline test with corner_class, untriaged | int_microsector_proximity | 1 | none |
| int_microsector_proximity | intermediate | QUESTIONABLE | OPEN | field median across clock times; baseline test blue_flags fails | - | 0 | none |
| int_pit_loss_circuit | intermediate | QUESTIONABLE | OPEN | whole-race median baseline; [8,60] s truncation (HD26) | int_pit_strategy_cost_curve, int_pit_strategy_value | 4 | via ML/app/assistant/export |
| int_pit_strategy_cost_curve | intermediate | QUESTIONABLE | OPEN | new tyre priced from age 1; free tyre when no curve (HD25, HD26) | int_pit_strategy_value | 3 | via ML/app/assistant/export |
| int_pit_strategy_value | intermediate | QUESTIONABLE | OPEN | GREATEST(NULL,0.0)=0 means no opportunity cost (HD25) | fct_driver_isolation_stint, fct_stint_features | 2 | app, assistant, export; via ML |
| int_qualifying_decomposed | intermediate | WRONG | OPEN | sign flipped, built, no sign test; 0.0 race fill and constant flags open | int_qualifying_driver_summary | 3 | app, export; via ML/assistant |
| int_qualifying_driver_summary | intermediate | SOUND | OPEN | baseline relationships test fails (434 rows, race_to_track seed gap), untriaged | fct_cliff_prediction_features | 2 | via ML/app/assistant/export |
| int_qualifying_push_laps | intermediate | SOUND | OPEN | baseline relationships test fails (6693 rows, race_to_track seed gap), untriaged | int_constructor_structural_pace_qualifying, int_lap_residual_decomposed_qualifying | 6 | via ML/app/assistant/export |
| int_qualifying_segments | intermediate | SOUND | OPEN | baseline relationships test fails (60 rows, race_to_track seed gap), untriaged | int_qualifying_push_laps | 7 | via ML/app/assistant/export |
| int_sector_residual_decomposed | intermediate | QUESTIONABLE | OPEN | sector baseline differs from lap baseline | - | 0 | app, export |
| int_stint_end_regime | intermediate | SOUND | OPEN | baseline relationships test fails (1107 rows, race_to_track seed gap), untriaged | fct_driver_isolation_stint, fct_stint_features, int_pit_strategy_value | 3 | app (comment only); via ML/assistant/export |
| int_stint_geometry | intermediate | SOUND | OPEN | baseline tests fail: 2018_compound_code_null, push_residual_fuel_neutral | fct_stint_features, int_compound_cliff_predicted, int_constructor_structural_pace, int_corner_drift_from_early_stint, int_corner_skill_residuals (+15) | 63 | ML, app, export; via assistant |
| int_synthetic_teammate | intermediate | QUESTIONABLE | OPEN | weight from own outcome sd; flag constant TRUE | fct_driver_skill_features | 1 | app, export; via assistant |
| int_track_evolution | intermediate | QUESTIONABLE | OPEN | LEAST(slope,0) turns NULL into 0; rubber clamp (HD25, HD28) | int_constructor_structural_pace, int_dirty_air_tax_component, int_driver_race_paired_laps, int_driver_race_skill_loro, int_lap_normalized_pace (+2) | 44 | app, assistant, export; via ML |
| int_tyre_surface_vs_bulk_decoupling | intermediate | QUESTIONABLE | OPEN | missing load imputed 0.5; unfitted probability | - | 0 | app, export |
| fct_cliff_prediction_features | marts | QUESTIONABLE | OPEN | ratio fills, drift 0.0 fill (HD25); baseline prior_season_labels_frozen fails | fct_power_law_training | 1 | ML, app, assistant, export |
| fct_driver_isolation_lap | marts | QUESTIONABLE | OPEN | SE assumes independence | fct_driver_isolation_race, fct_driver_isolation_stint | 2 | via assistant/export |
| fct_driver_isolation_race | marts | QUESTIONABLE | OPEN | SE does not match header | - | 0 | assistant, export |
| fct_driver_isolation_stint | marts | QUESTIONABLE | OPEN | SE assumes independence | - | 0 | assistant, export |
| fct_driver_skill_features | marts | QUESTIONABLE | OPEN | weights of NULL proxies in divisor; divergence 0.0 fill | - | 0 | app, assistant, export |
| fct_ghost_car_pace | marts | QUESTIONABLE | OPEN | ego constructor 0.0 fill, no ego flag (HD20, HD25) | fct_ghost_race_finish | 1 | app (comment only), assistant, export |
| fct_ghost_race_finish | marts | QUESTIONABLE | OPEN | SE approximations; confidence threshold mismatch | - | 0 | app, assistant, export |
| fct_telemetry_deltas | marts | SOUND | OPEN | baseline relationships test fails (165619 rows, race_to_track seed gap), untriaged | - | 0 | assistant, export |
| mart_corner_skill_driver | marts | QUESTIONABLE | OPEN | z-score not centred; SE assumes independent cells | - | 0 | app, assistant, export |
| mart_degradation_history_envelope | marts | QUESTIONABLE | OPEN | age/lap index mismatch; default coefficients shown as fitted (HD26) | - | 0 | ML, app, export |
| mart_driver_season_summary | marts | QUESTIONABLE | OPEN | constructor_rank averages the 0.0 fill (HD25) | - | 0 | assistant, export |
| mart_race_driver_summary | marts | QUESTIONABLE | OPEN | constructor_rank 0.0 fill (HD25); CI treats paired gaps as independent | mart_driver_season_summary | 1 | assistant, export |
| dim_constructors | reference | QUESTIONABLE | OPEN | pu_family wrong for McLaren 2018-20, Red Bull 2018 (judgement) | fct_driver_skill_features, fct_lap_residuals | 7 | export; via ML/app/assistant |
| dim_drivers | reference | QUESTIONABLE | OPEN | debut_year is first season in data (judgement) | fct_driver_skill_features, fct_lap_residuals | 7 | app (comment only), export; via ML/assistant |

## C. Not checked yet

Models with status NOT CHECKED:
- `int_corner_lap_measured`, `int_corner_length_measured`: written after the audit; built and shape tests pass; nobody has reviewed the logic as an audit. The method report is not saved (build-log).
- `int_constructor_car_fe`, `int_constructor_car_fe_isolation`: the SQL is a pass-through, the fitted values come from Python fit scripts outside the audit.

Also unverified:
- The fits sources (`source:fits+`): car-FE and theta_air fit scripts were not audited.
- Row counts and magnitudes of every QUESTIONABLE and WRONG finding: the audit ran nothing.
- 2026 data: not audited. 2018 Italian GP: known gap (HD15 B).
- Macros not shown as opened in full by any audit note: only used through the models. `compound_cliff_wear.sql` (header only read), `clamp_or_null.sql`, `trailing_median.sql`, `power_law_beta_grid.sql` (read where needed). Never named in any audit note: `assert_additive_identity.sql`, `clean_lap_filter.sql`, `driver_isolation_reliability.sql`, `normalize_compound.sql`. The rest (`bayesian_shrinkage`, `circuit_id_from_name`, `driver_isolation_identity_terms`, `driver_isolation_pure_season_offset`, `fuel_regulatory_max_kg`, `median_ci_order_rank`, `normal_cdf`, `posterior_variance`) are named once or twice only.
- Seeds whose values were never checked: `race_to_track` (audit says so explicitly), `circuit_reference`, `raw_dim_events`, `compound_cliff_params`, `tyre_allocations` (headers and a few rows only), `compound_hardness_scale`, `driver_isolation_method_scores`, `race_scheduled_laps`, `seed_manual_lap_exceptions`, `label_stability_baseline` (never named).
- Triage of the 41 failing tests: 32 are relationships tests (26 on `race_to_track`, 5 on `dim_constructors`, 1 on `dim_circuits`), 9 are singular tests; `assert_race_to_track_covers_all_races` also fails (76 races). All match the clean baseline; cause unverified.
- Orphans (no downstream model and no reader found by grep): stg_events, stg_session_status, dim_driver_seasons, int_lap_normalized_pace, int_microsector_proximity, int_microsector_corner_class, int_stint_power_law_fit, int_track_geometry, int_traffic_exposure_race, and four scratch new_data marts (fct_pit_stop_crosscheck, fct_speed_traps, fct_speed_traps_season, fct_track_limits_driver_session; consumer none by design until AP-09/AX-28). `export_app_data.py` also names `int_coast_tax_component`, which is not a model in the graph.

## D. Damage map

Format: broken model -> what it feeds. Tags: [app] [assistant] [export] [ML].

WRONG items
- `int_corner_skill_residuals` (FIXED, DONE; rebuilt with its 6 downstream models):
  - -> int_corner_drift_from_early_stint -> int_lap_corner_drift -> fct_cliff_prediction_features
  - -> int_lap_corner_inputs -> fct_cliff_prediction_features
  - -> mart_corner_skill_driver [app, assistant, export]
  - -> fct_cliff_prediction_features [app, assistant, export, ML] -> fct_power_law_training [app, ML]
- `int_constructor_deg_sensitivity` (OPEN, TX-32, HD29-HD34):
  - -> fct_ghost_car_pace [app, assistant, export] -> fct_ghost_race_finish [app, assistant, export]
- `int_qualifying_decomposed` (sign fixed, built, no sign test; 0.0 fill and constant flags open):
  - -> app quali-vs-race page and export (queries.ts changed to match the flipped delta: race = quali + delta, order by delta DESC)
  - -> int_qualifying_driver_summary -> fct_cliff_prediction_features [app, assistant, export, ML] -> fct_power_law_training
- `fct_stint_features` (FIXED, DONE, test `assert_stint_falloff_slope_uses_residual_laps` passes): feeds no model; reaches [app, assistant, export, ML] directly.
- `int_track_geometry` (FIXED, DONE, build only): feeds nothing, no reader.
- `stg_lap_tyre_qa` (OPEN, accepted DQ-01, 3 driver-races): 64 models downstream in the graph; magnitude of effect unverified.

Other open items
- Zero fills (HD25): `int_lap_residual_decomposed` (32 downstream models, constructor 0.0 fill) -> mart_race_driver_summary and mart_driver_season_summary (constructor_rank) [app, assistant, export]; -> fct_ghost_car_pace (ego side) [app, assistant, export].
- `int_compound_cliff_predicted` (free tyre for unseeded laps) -> 8 direct models, 48 downstream, incl. int_pit_strategy_cost_curve and the ML feature chain.
- `int_pit_strategy_value` (GREATEST(NULL,0.0)) -> fct_stint_features [app, assistant, export, ML]; -> fct_driver_isolation_stint [assistant, export]; also read directly by the app and the assistant.
- Cliff features zero fills -> fct_cliff_prediction_features [ML] -> fct_power_law_training.
- HD26 fixed constants: `int_pit_loss_circuit`, `int_pit_strategy_cost_curve`, `int_lap_fuel_state_qualifying`, `int_lap_normalized_pace`, `mart_degradation_history_envelope` [app, ML].
- HD27 zero-width uncertainty: int_constructor_structural_pace(_qualifying), int_era_normalized_driver_rating, int_circuit_x_constructor_interaction, the shrinkage models. All reach export/app.
- `stg_results` DNF classification (7 direct downstream). `is_valid_lap` NULL in stg_laps (33 direct downstream). `stg_pits` compound strings (6 downstream).
- `dim_constructors`, `dim_drivers`: judgement items, exported.
- `stg_jolpica_pit_stops`: no tests; feeds fct_pit_stop_crosscheck (scratch).

## E. Open decisions for the owner (build-log.json)

- HD25: zero-fill policy, NULL with a reason or a declared prior with a flag.
- HD26: non-zero constant defaults, same choice.
- HD27: zeros inside an uncertainty (pooled variance, collapsed CIs).
- HD28: track-evolution rubber clamp, NULL where clamped or raw plus clamped columns.
- HD20: ghost-car 0 fills (TX-18), constructor with no pace cell or no degradation cell.
- HD29: cliff event for constructor cliff timing (TX-32 method A).
- HD30: cliff onset, two estimands now or the x2.5 stopgap first.
- HD31: cliff thin-cell uncertainty, prior sd tau or NULL.
- HD32: cliff onset +/-3 lap clip and the +/-2 s interaction clip, remove or keep.
- HD33: ML, as-of constructor cliff timing as a cliff_classifier candidate feature.
- HD34: cap H for the post-cliff cost exposure (TX-32 method B).
- Fuel burn: even-burn assumption kept; owner to decide whether team-wide fuel or energy orders need strategy data (not in project).
- HD18: delete old data, waiting on what exactly to delete.
- XW, XM: external, wake calibration to WC-06; ML redo, CD10 promotion.
- DQ-01 is RESOLVED (stint 0 accepted, no code change). Corner length: the 88 m band and exclusion policy were owner-approved, no decision id opened.
- Also open per build-log: owner commit of the corner-length changes; cause of `assert_prior_season_labels_frozen` and `assert_rain_flag_matches_tyres` (needs a HEAD build); 2026 alignment flags (China 2026 turn 14).

## F. Models that feed no one

A model is listed here when its downstream count is 0, or when everything downstream of it reaches no app, assistant, export or ML consumer (the "reaches" column in section B is "none"). Being here does not mean the model is wrong. It means the output is either unused, or waiting for a consumer that has not been built yet. Removing a model is a decision for the owner.

Built from section B (reaches = none), 2026-11-19. Section C's orphan list is a subset of this table.

| model | layer | status | feeds | why it has no consumer | what would change this |
|---|---|---|---|---|---|
| stg_events | staging | REALLY DONE | - | staging table nothing reads | remove, or add a reader |
| stg_session_status | staging | OPEN | - | staging table nothing reads; baseline relationships test fails | remove, or add a reader |
| stg_jolpica_pit_stops | staging | OPEN | fct_pit_stop_crosscheck | feeds only a scratch cross-check; no tests | add tests; decide if the cross-check ships |
| int_stint_power_law_fit | intermediate | DONE WITH CAVEAT | - | output not read by any model | check whether the power-law app page reads it directly |
| int_traffic_exposure_driver_race | intermediate | REALLY DONE | int_traffic_exposure_race | chain ends in a model with no reader | add a reader or remove the chain |
| int_traffic_exposure_race | intermediate | REALLY DONE | - | end of the traffic chain; no reader | add a reader or remove the chain |
| int_lap_physical_ahead | intermediate | OPEN | int_traffic_exposure_driver_race | feeds the dead traffic chain; 3 warn tests untriaged | same as the traffic chain |
| int_lap_normalized_pace | intermediate | OPEN | - | no reader; fallback 0.004 is a constant | remove, or add a reader and fix the constant |
| int_microsector_proximity | intermediate | OPEN | - | no reader; baseline blue_flags test fails | remove, or add a reader |
| int_microsector_crossings | intermediate | OPEN | int_microsector_proximity | feeds the dead microsector chain; baseline test fails | same as microsector chain |
| int_microsector_corner_class | intermediate | OPEN | - | no reader; baseline test fails (2 rows) | remove, or add a reader |
| int_track_geometry | intermediate | DONE WITH CAVEAT | - | no reader; curvature guards present, values need re-check | re-check values, then decide |
| dim_driver_seasons | reference | REALLY DONE | - | no reader | remove, or add a reader |
| fct_pit_stop_crosscheck | new_data | DONE WITH CAVEAT | - | scratch mart; consumer comes with AP-09 | keep until AP-09, or remove |
| fct_speed_traps | new_data | REALLY DONE | - | scratch mart; consumer none by design | keep until its consumer is built |
| fct_speed_traps_season | new_data | REALLY DONE | - | scratch mart; consumer none by design | keep until its consumer is built |
| fct_track_limits | new_data | REALLY DONE | fct_track_limits_driver_session | feeds the scratch session mart; no reader | keep until its consumer is built |
| fct_track_limits_driver_session | new_data | REALLY DONE | - | scratch mart; consumer none by design | keep until its consumer is built |

Notes:
- Two chains are dead end to end: the traffic exposure chain (`int_lap_physical_ahead` -> `int_traffic_exposure_driver_race` -> `int_traffic_exposure_race`) and the microsector chain (`int_microsector_crossings` -> `int_microsector_proximity`, plus `int_microsector_corner_class`).
- Four `new_data` marts are scratch by design, waiting on AP-09 and AX-28.
- `int_corner_drift_from_early_stint` is not listed here. It has readers: `int_lap_corner_drift` and `fct_cliff_prediction_features`. Those readers reach ML's feature table, but the drift columns are not in the shipped model contract (see the 02h note in section C and the session discussion). It is an unused experiment, not a dead end.
- `stg_events` and `dim_driver_seasons` have no reader in the graph, so their status says nothing about whether they are needed.

## G. History

Fresh audit totals (108 models, read-only, no dbt run): staging and reference 24 (17 sound, 6 questionable, 1 wrong); intermediate A-L 38 (14, 22, 2); intermediate M-Z 22 (12, 8, 2); marts 24 (12, 11, 1). Total SOUND 55, QUESTIONABLE 47, WRONG 6. Notes in `_evidence/fresh-audit/`. The top unit finding was checked against the code: the mid-corner term divided a speed difference by a speed, so it had no corner length and was not seconds.

Audit priority list. Wrong first: mid-corner units (`int_corner_skill_residuals`), cliff-onset shift units (`int_constructor_deg_sensitivity`), 0.0 race-residual fill and dead filters (`int_qualifying_decomposed`), mis-scaled falloff slope (`fct_stint_features`), stint 0 (`stg_lap_tyre_qa`), tenth-of-metre positions (`int_track_geometry`). Questionable, zero-fills (HD25): `int_compound_cliff_predicted`, ghost ego constructor fill, `constructor_rank`, cliff features, `int_pit_strategy_value`. Zero-width uncertainties (HD27). Other: `is_valid_lap` NULL for 909 laps, pit cost curve prices the new tyre from age 1, DNF classification in `stg_results`.

Fixes (files dated from modification times, 2026-11-18; no git used):
- 2026-11-18 12:06 `fct_stint_features`: falloff slope uses only laps with a residual; new test `assert_stint_falloff_slope_uses_residual_laps` passes in the 13:32 test run.
- 2026-11-18 12:06 `int_qualifying_decomposed`: delta now race minus quali (positive = faster in qualifying); 12:07 `app/src/features/quali-vs-race-skill/queries.ts` changed to match. Built OK; no test pins the sign.
- 2026-11-18 12:07 `int_track_geometry`: X/Y/Z divided by 10 (tenths of a metre). Built OK; no unit test.
- 2026-11-18 13:10 `int_corner_skill_residuals`, `int_corner_metrics`, `int_corner_length_measured`, `int_corner_lap_measured`: measured corner length (3-sample median speed, 88 m apex band, per-lap exclusions). Built in scratch, tests pass. Reported by the implementer, not re-run here: |mid_corner_residual_s| above 60 s went 29 to 2, max 390.7 to 133.6.
- 2026-11-18 DQ-01: stint 0 on three pre-stop laps accepted by the owner, no code change.
- 2026-11-18 TX-32 added at SPEC with HD29-HD34 open; no ruling made.
- Corrections made by verification (2026-11-18): (1) DONE 49 to 35 and OPEN 57 to 71: 14 SOUND models had their own failing baseline relationships test (stg_circuit_info, stg_race_control, stg_results_qualifying, stg_sector_times, stg_session_status, stg_session_status_qualifying, stg_telemetry, stg_telemetry_position, stg_track_status, int_qualifying_driver_summary, int_qualifying_push_laps, int_qualifying_segments, int_stint_end_regime, fct_telemetry_deltas), which the status key counts as OPEN; (2) relationships failures are 32 (26/5/1), not 29; (3) int_corner_lap_measured has 8 passing tests, not 9; (4) 12 reaches entries marked comment only; int_stint_geometry assistant moved to via; int_dirty_air_tax_component assistant is a held stub; (5) summary wording: the 3 fixed WRONG are confirmed in the file and built, not all test-verified; (6) typo removed in the FIXED-NOT-VERIFIED row. No verdict changed.
