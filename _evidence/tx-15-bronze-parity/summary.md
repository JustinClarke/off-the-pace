# TX-15 parity report: current tree on the 2026-11-16 Bronze vs the published Nov-8 export

Measurement only. Nothing here has been reviewed by the owner. No conclusion about what to change is drawn. Method, commands and caveats are in README.md; every number is also in summary.json.

## 0. What was compared, and what moves for more than one reason

"Published" is app/public/data (manifest e5b324bf3e6d07a6, 2026-11-08, built from the old Bronze). "Scratch" is a dbt build of the working tree (HEAD 4320460 plus the uncommitted edits listed in README.md) on data/bronze (2026-11-16), exported with scripts/export_app_data.py. Differences are therefore the sum of three things that this report does not separate: (1) the new Bronze, (2) every SQL/seed change in the tree since Nov 8, including the TX-17, TX-18 and TX-20 edits that are already in the tree, (3) the scratch car-FE refit (pyfixest 0.60; data/fits is empty in the repo, so the published fit files are not available to compare against).

Excluded from the build, as in the earlier attempt: mart_degradation_history_envelope (no degradation_isotonic.parquet; TX-09/XM), int_lap_physical_ahead and everything downstream of it. The scratch export therefore has no envelope rows (an empty stub table was used only so the exporter would run), no int_coast_tax_component, and no ML outputs (driver_network_rating and mart_degradation_predictions are produced from ML files, not dbt, and were not produced).

Tolerance: a float cell counts as moved when |new - old| > 1e-9 (TX-14 compares floats at ROUND(x, 9)); NULL vs value counts as moved; non-float columns by IS DISTINCT FROM. Comparisons are matched on the grain key over the races present in both exports with race_year <= 2025 ("scope"; 171 races), so 2018_14, 2021_12 and all 2026 rows are outside it and reported separately. fit_timestamp columns always differ (a build clock, not data).

## 1. Races

Dropped from the scratch export (in published, absent in scratch): 2018_14 Italian Grand Prix (833 laps in fct_lap_residuals).
Added (absent in published, present in scratch): 2021_12 Belgian Grand Prix (20 laps in fct_lap_residuals).

2018_14 is absent from stg_laps (0 rows); mart_race_coverage now says SOURCE_UNAVAILABLE (published: OK with 833 laps). 2021_12 is the 2021 Belgian GP: published had NO_RACING_LAPS and 0 laps; scratch has 20 valid laps (60 rows in stg_laps), has_rating false, coverage_reason OK. 2020_1 (Austrian GP) stays in fct_lap_residuals but with 684 laps instead of 758, its tyre QA is now quarantined_race (published: partial), and it is absent from fct_ghost_car_pace, fct_ghost_race_finish, int_field_pace_curve, int_track_evolution, int_sector_residual_decomposed and int_tyre_surface_vs_bulk_decoupling.

| race | published (status, telemetry, rating, reason, laps) | scratch (status, telemetry, rating, reason, laps) | stg_laps rows scratch |
|---|---|---|---|
| 2018_14 | ['ok', True, True, 'OK', 833] | [None, False, False, 'SOURCE_UNAVAILABLE', 0] | 0 |
| 2020_1 | ['partial', True, True, 'OK', 758] | ['quarantined_race', True, True, 'TYRE_QA_QUARANTINED', 684] | 1061 |
| 2021_12 | ['ok', True, False, 'NO_RACING_LAPS', 0] | ['ok', True, False, 'OK', 20] | 60 |

Laps in fct_lap_residuals per season:

| season | races pub | races scratch | laps pub | laps scratch | delta laps |
|---|---|---|---|---|---|
| 2018 | 21 | 20 | 18,213 | 17,380 | -833 |
| 2019 | 21 | 21 | 20,723 | 20,723 | 0 |
| 2020 | 17 | 17 | 15,225 | 15,153 | -72 |
| 2021 | 21 | 22 | 20,560 | 20,596 | 36 |
| 2022 | 22 | 22 | 19,395 | 19,430 | 35 |
| 2023 | 22 | 22 | 20,908 | 20,911 | 3 |
| 2024 | 24 | 24 | 23,256 | 23,261 | 5 |
| 2025 | 24 | 24 | 22,760 | 22,760 | 0 |

Total 161,040 -> 160,214 (-826 = -833 for 2018_14, +20 for 2021_12, -13 net across the other races).

Races whose lap count changes (fct_lap_residuals; 9 races other than the dropped and added ones):

| race | name | laps pub | laps scratch | delta |
|---|---|---|---|---|
| 2020_1 | Austrian Grand Prix | 758 | 684 | -74 |
| 2020_9 | Tuscan Grand Prix | 555 | 557 | +2 |
| 2021_10 | British Grand Prix | 849 | 855 | +6 |
| 2021_21 | Saudi Arabian Grand Prix | 527 | 530 | +3 |
| 2021_6 | Azerbaijan Grand Prix | 725 | 732 | +7 |
| 2022_10 | British Grand Prix | 666 | 668 | +2 |
| 2022_18 | Japanese Grand Prix | 370 | 403 | +33 |
| 2023_19 | Mexico City Grand Prix | 1123 | 1126 | +3 |
| 2024_4 | Japanese Grand Prix | 777 | 782 | +5 |

2026 races: 2026_1 to 2026_20 appear in stg tables and some intermediates (e.g. fct_stint_features, int_lap_air_state, fct_telemetry_deltas, int_corner_metrics: 19 or 17 races), but none of them appears in fct_lap_residuals, fct_ghost_car_pace or fct_ghost_race_finish, because race_to_track has no 2026 rows. The exported manifest stats block still says seasons 2018-2025.

Per-table race-set differences (races only in published; races only in scratch other than 2026):

| table | only in published | only in scratch (non-2026) | 2026 races in scratch | races with a changed row count |
|---|---|---|---|---|
| fct_cliff_prediction_features | 2018_14 | 2021_12 | - | 9 |
| fct_driver_isolation_race | 2018_14 | - | - | 6 |
| fct_driver_isolation_stint | 2018_14 | - | - | 51 |
| fct_driver_skill_features | 2018_14 | 2021_12 | - | 0 |
| fct_ghost_car_pace | 2020_1, 2018_14 | - | - | 41 |
| fct_ghost_race_finish | 2020_1, 2018_14 | - | - | 7 |
| fct_lap_residuals | 2018_14 | 2021_12 | - | 9 |
| fct_stint_features | 2018_14 | - | 19 | 11 |
| fct_telemetry_deltas | 2018_14 | - | 17 | 17 |
| int_circuit_x_constructor_interaction | 2018_14 | - | - | 0 |
| int_compound_cliff_predicted | 2018_14 | 2021_12 | - | 9 |
| int_constructor_structural_pace | 2018_14 | - | - | 0 |
| int_constructor_structural_pace_qualifying | - | - | 20 | 0 |
| int_corner_metrics | 2018_14 | - | 17 | 21 |
| int_corner_skill_residuals | 2018_14 | 2021_12 | 17 | 15 |
| int_driver_race_skill_loro | 2018_14 | - | - | 2 |
| int_field_pace_curve | 2020_1, 2018_14 | - | - | 4 |
| int_lap_air_state | 2018_14 | - | 19 | 12 |
| int_lap_anomaly_flags | 2018_14 | 2021_12 | - | 9 |
| int_pit_strategy_value | 2018_14 | 2021_12 | 19 | 3 |
| int_qualifying_decomposed | - | - | 20 | 0 |
| int_sector_residual_decomposed | 2020_1, 2018_14 | 2021_12 | - | 14 |
| int_synthetic_teammate | 2018_14 | 2021_12 | - | 8 |
| int_track_evolution | 2020_1, 2018_14 | - | - | 3 |
| int_tyre_surface_vs_bulk_decoupling | 2020_1, 2018_14 | - | - | 12 |
| mart_race_driver_summary | 2018_14 | - | - | 1 |
| qv_driver_race | 2018_14 | - | - | 1 |
| qv_laps | 2018_14 | 2021_12 | - | 9 |
| qv_pit_stops | 2018_14 | 2021_12 | 19 | 3 |
| qv_race_laps | 2018_14 | - | 19 | 3 |
| qv_stints | 2018_14 | - | 19 | 11 |
| qv_teammate_corners | 2018_14 | 2021_12 | - | 9 |
| race_caution_timeline | 2018_14 | - | 19 | 3 |
| stg_pits | 2018_14 | - | 19 | 0 |
| stg_results | 2018_14 | - | 19 | 0 |

## 2. Rows per exported table

"rows" are whole-table counts. "only pub / only scratch" are grain keys present on one side only inside the scope (so they include laps/rows that shift inside the 171 common races). "moved" is the number of matched rows with at least one column beyond tolerance. "cols changed" is the number of columns whose multiset hash differs within scope (per-column hashes are sum(hash(col)) per table, in summary.json under tables_detail[table].col_hashes, for both the whole table and the scope).

| table | rows pub | rows scratch | delta | only pub (scope) | only scratch (scope) | matched | moved > tol | cols changed (scope) |
|---|---|---|---|---|---|---|---|---|
| assistant_entities | 296 | 299 | 3 | 0 | 3 | 296 | 2 | 7/7 |
| dim_circuits | 44 | 44 | 0 | 0 | 0 | 44 | 0 | 0/12 |
| dim_compounds_season | 499 | 499 | 0 | 0 | 0 | 499 | 0 | 0/16 |
| dim_constructors | 19 | 19 | 0 | 0 | 0 | 19 | 0 | 0/3 |
| dim_drivers | 43 | 46 | 3 | 0 | 3 | 43 | 31 | 4/4 |
| fct_cliff_prediction_features | 161,040 | 160,214 | -826 | 115 | 102 | 160,092 | 158,446 | 97/97 |
| fct_driver_isolation_race | 3,102 | 3,092 | -10 | 0 | 9 | 3,083 | 3,079 | 37/37 |
| fct_driver_isolation_stint | 26,325 | 26,231 | -94 | 109 | 157 | 26,074 | 25,871 | 47/47 |
| fct_driver_skill_features | 3,312 | 3,313 | 1 | 0 | 0 | 3,293 | 1,737 | 12/23 |
| fct_ghost_car_pace | 1,384,558 | 1,372,651 | -11,907 | 6887 | 3130 | 1,369,521 | 1,369,521 | 38/38 |
| fct_ghost_race_finish | 30,344 | 30,054 | -290 | 190 | 90 | 29,964 | 29,964 | 26/26 |
| fct_lap_residuals | 161,040 | 160,214 | -826 | 115 | 102 | 160,092 | 92,510 | 49/49 |
| fct_stint_features | 8,945 | 10,002 | 1,057 | 28 | 19 | 8,856 | 5,096 | 27/27 |
| fct_telemetry_deltas | 1,623,427 | 1,779,348 | 155,921 | 7107 | 3166 | 1,609,994 | 512,147 | 10/10 |
| int_circuit_x_constructor_interaction | 1,644 | 1,634 | -10 | 0 | 0 | 1,634 | 1,099 | 3/8 |
| int_compound_cliff_predicted | 161,040 | 160,214 | -826 | 115 | 102 | 160,092 | 1,717 | 18/18 |
| int_constructor_structural_pace | 1,644 | 1,634 | -10 | 0 | 0 | 1,634 | 1,634 | 7/12 |
| int_constructor_structural_pace_qualifying | 1,730 | 1,950 | 220 | 0 | 0 | 1,710 | 1,710 | 1/10 |
| int_corner_metrics | 3,036,871 | 3,344,727 | 307,856 | 535 | 5827 | 3,025,076 | 972,696 | 9/9 |
| int_corner_skill_residuals | 2,585,908 | 2,843,862 | 257,954 | 1188 | 6263 | 2,575,557 | 892,974 | 17/17 |
| int_dirty_air_tax_component | 149,452 | 147,930 | -1,522 | 1541 | 19 | 147,911 | 147,911 | 7/7 |
| int_driver_circuit_affinity | 1,024 | 1,021 | -3 | 3 | 0 | 1,021 | 1,021 | 16/16 |
| int_driver_circuit_era_affinity | 1,419 | 1,416 | -3 | 3 | 0 | 1,416 | 1,416 | 16/16 |
| int_driver_race_skill_loro | 3,275 | 3,254 | -21 | 2 | 0 | 3,254 | 3,096 | 13/13 |
| int_era_normalized_driver_rating | 173 | 173 | 0 | 0 | 0 | 173 | 173 | 12/18 |
| int_field_pace_curve | 9,136 | 9,044 | -92 | 49 | 6 | 9,038 | 1,186 | 11/11 |
| int_lap_air_state | 189,418 | 210,660 | 21,242 | 19 | 10 | 188,412 | 153,327 | 16/16 |
| int_lap_anomaly_flags | 161,040 | 160,214 | -826 | 115 | 102 | 160,092 | 84,651 | 35/35 |
| int_pit_strategy_value | 8,211 | 9,214 | 1,003 | 20 | 35 | 8,156 | 8,156 | 24/24 |
| int_qualifying_decomposed | 16,876 | 18,904 | 2,028 | 0 | 0 | 16,669 | 8,159 | 1/36 |
| int_sc_hazard_history | 173 | 191 | 18 | 1 | 0 | 172 | 152 | 15/15 |
| int_sector_residual_decomposed | 477,069 | 474,081 | -2,988 | 2055 | 1506 | 472,515 | 226,833 | 19/19 |
| int_synthetic_teammate | 140,460 | 139,788 | -672 | 80 | 76 | 139,692 | 1,554 | 14/14 |
| int_track_evolution | 8,667 | 8,572 | -95 | 47 | 1 | 8,571 | 4,022 | 10/10 |
| int_tyre_surface_vs_bulk_decoupling | 38,819 | 38,723 | -96 | 51 | 194 | 38,529 | 352 | 14/14 |
| mart_build_provenance | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 3/15 |
| mart_corner_skill_driver | 161 | 183 | 22 | 0 | 0 | 161 | 161 | 15/18 |
| mart_degradation_history_envelope | 8,115 | 0 | -8,115 | 8115 | 0 | 0 | 0 | 19/19 |
| mart_driver_season_summary | 173 | 173 | 0 | 0 | 0 | 173 | 173 | 15/26 |
| mart_metric_benchmark | 48 | 48 | 0 | 0 | 0 | 48 | 45 | 6/9 |
| mart_race_coverage | 173 | 173 | 0 | 0 | 0 | 171 | 74 | 10/15 |
| mart_race_driver_summary | 3,138 | 3,118 | -20 | 2 | 0 | 3,118 | 1,586 | 27/27 |
| qv_circuit_history | 173 | 191 | 18 | 1 | 0 | 172 | 11 | 7/7 |
| qv_circuits | 44 | 44 | 0 | 0 | 0 | 44 | 0 | 0/6 |
| qv_compounds | 499 | 499 | 0 | 0 | 0 | 499 | 0 | 0/3 |
| qv_driver_race | 3,138 | 3,118 | -20 | 2 | 0 | 3,118 | 128 | 12/12 |
| qv_laps | 161,040 | 160,214 | -826 | 594 | 581 | 159,613 | 1,232 | 11/11 |
| qv_pit_stops | 5,507 | 6,198 | 691 | 18 | 17 | 5,467 | 85 | 9/9 |
| qv_race_laps | 10,373 | 11,468 | 1,095 | 3 | 0 | 10,314 | 189 | 6/6 |
| qv_stints | 8,945 | 10,002 | 1,057 | 28 | 19 | 8,856 | 122 | 13/13 |
| qv_teammate_corners | 1,529,933 | 1,527,804 | -2,129 | 302 | 2818 | 1,524,417 | 511,621 | 11/11 |
| race_caution_timeline | 10,373 | 11,468 | 1,095 | 3 | 0 | 10,314 | 189 | 9/9 |
| race_to_track | 173 | 173 | 0 | 0 | 0 | 171 | 0 | 0/2 |
| stg_pits | 6,177 | 6,956 | 779 | 0 | 0 | 6,135 | 80 | 3/12 |
| stg_results | 3,458 | 3,856 | 398 | 0 | 0 | 3,418 | 0 | 0/16 |

Not produced in the scratch export: driver_network_rating, mart_degradation_predictions (ML outputs, not dbt). mart_degradation_history_envelope: 8,115 published rows, 0 scratch (excluded). Columns present only in scratch: fct_ghost_car_pace (the five *_is_prior flags), fct_ghost_race_finish (n_laps_prior_filled, finish_pos_se_unavailable_reason), fct_stint_features (n_dirty_air_measured_laps, dirty_air_unavailable_reason), mart_race_coverage (n_bronze_lap_rows). No published column is missing.

dbt model row counts in the scratch warehouse, including the marts that are not exported, are in summary.json under scratch_db_row_counts (no published counterpart to diff those).

## 3. Marts and key facts: what moves, and the top movers

Per-column counts of moved rows (top columns) and the largest single-cell moves. Full top-40 lists per table are in movers_<table>.csv (columns: grain key, column, old published value, new scratch value, absolute delta).

### mart_driver_season_summary

Key ['race_year', 'driver_id']; matched 173; rows moved 173.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| ci_low | 173 | 0.1154 | 50 | 0 | 0 |
| ci_high | 173 | 0.09931 | 69 | 0 | 0 |
| rating_se_s | 173 | 0.004113 | 20 | 0 | 0 |
| mean_constructor_component_s | 172 | 0.05022 | 132 | 0 | 0 |
| mean_dirty_air_tax_s | 136 | 0.01307 | 52 | 0 | 0 |
| rating_s | 113 | 0.1074 | 48 | 0 | 0 |
| teammate_gap_s | 113 | 0.1074 | 48 | 0 | 0 |
| n_dirty_air_measured_laps | 92 | - | - | - | - |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2018|VAN | total_clean_laps_n | 798.0 | 752.0 | 46.0 |
| 2018|LEC | total_clean_laps_n | 749.0 | 704.0 | 45.0 |
| 2018|OCO | total_clean_laps_n | 783.0 | 738.0 | 45.0 |
| 2018|HAM | total_clean_laps_n | 938.0 | 893.0 | 45.0 |
| 2018|VER | total_clean_laps_n | 819.0 | 774.0 | 45.0 |

### mart_race_driver_summary

Key ['race_id', 'driver_id']; matched 3,118; rows moved 1,586.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| mean_constructor_component_s | 1,509 | 0.3046 | 1254 | 8 | 18 |
| mean_dirty_air_tax_s | 253 | 0.1372 | 220 | 8 | 20 |
| constructor_rank | 110 | - | - | - | - |
| mean_compound_component_s | 103 | 2.653 | 76 | 8 | 18 |
| n_dirty_air_measured_laps | 93 | - | - | - | - |
| n_clean_laps | 88 | - | - | - | - |
| mean_fuel_component_s | 88 | 0.0512 | 62 | 8 | 18 |
| avg_lap_time_s | 88 | 1.269 | 61 | 8 | 18 |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2018_8|SIR | mean_compound_component_s | 4.1936785714 | 1.5407428571 | 2.65293571 |
| 2024_14|STR | mean_compound_component_s | 1.1749307692 | 3.3277333333 | 2.15280256 |
| 2024_14|ALO | mean_compound_component_s | 1.2300425000 | 3.2512425000 | 2.02120000 |
| 2020_7|VER | mean_compound_component_s | 0.5292324324 | 2.4457621621 | 1.91652972 |
| 2020_7|RAI | mean_compound_component_s | 0.4529 | 2.2077571428 | 1.75485714 |

### mart_corner_skill_driver

Key ['race_year', 'driver_id']; matched 161; rows moved 161.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| braking_skill_s | 161 | 0.0411 | 125 | 0 | 0 |
| mid_corner_skill_s | 160 | 0.0325 | 92 | 0 | 0 |
| exit_skill_s | 159 | 0.0363 | 139 | 0 | 0 |
| braking_skill_z | 152 | 0.49 | 152 | 0 | 0 |
| mid_corner_skill_z | 149 | 0.6 | 149 | 0 | 0 |
| corner_skill_index | 149 | 1.31 | 149 | 0 | 0 |
| braking_skill_se_s | 144 | 0.0045 | 21 | 0 | 0 |
| exit_skill_z | 144 | 0.43 | 144 | 0 | 0 |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2020|GRO | corner_skill_index | -0.31 | 1.0 | 1.31 |
| 2020|RUS | corner_skill_index | -1.22 | -2.46 | 1.24 |
| 2020|LAT | corner_skill_index | 1.22 | 2.46 | 1.24 |
| 2020|MAG | corner_skill_index | 0.07 | -1.1 | 1.17000000 |
| 2020|RAI | corner_skill_index | 1.23 | 0.33 | 0.89999999 |

### mart_metric_benchmark

Key ['race_year', 'metric_name']; matched 48; rows moved 45.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| mean | 45 | 0.6951 | 20 | 0 | 0 |
| sd | 45 | 0.2886 | 17 | 0 | 0 |
| sample_size | 44 | - | - | - | - |
| p50 | 24 | 0.5235 | 24 | 0 | 0 |
| p95 | 24 | 0.2864 | 19 | 0 | 0 |
| p05 | 23 | 0.141 | 21 | 0 | 0 |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2020|lap_time_s | mean | 85.886516596 | 86.581571417 | 0.69505482 |
| 2018|lap_time_s | p50 | 85.83 | 86.3535 | 0.52349999 |
| 2020|lap_time_s | p50 | 84.907 | 85.253 | 0.34600000 |
| 2018|lap_time_s | sd | 12.149177813 | 12.437737214 | 0.28855940 |
| 2020|lap_time_s | p95 | 108.09499999 | 108.3814 | 0.28640000 |

### mart_race_coverage

Key ['race_id']; matched 171; rows moved 74.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| n_ml_eligible_laps | 54 | - | - | - | - |
| residual_measured_share | 17 | 0.8113 | 17 | 0 | 0 |
| air_measured_share | 15 | 0.001917 | 7 | 0 | 0 |
| base_measured_share | 12 | 0.8931 | 12 | 0 | 0 |
| n_lap_rows | 9 | - | - | - | - |
| bronze_tyre_life_share | 9 | 0.052 | 7 | 0 | 0 |
| tyre_qa_status | 7 | - | - | - | - |
| rain_lap_share | 1 | 0.07281 | 1 | 0 | 0 |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2020_1 | base_measured_share | 0.8931398416 | 0.0 | 0.89313984 |
| 2020_1 | residual_measured_share | 0.8113456464 | 0.0 | 0.81134564 |
| 2018_5 | residual_measured_share | 0.8467933491 | 0.9667458432 | 0.11995249 |
| 2018_18 | residual_measured_share | 0.8930288461 | 0.9795673076 | 0.08653846 |
| 2022_18 | base_measured_share | 0.8891891891 | 0.8163771712 | 0.07281201 |

### fct_lap_residuals

Key ['lap_id']; matched 160,092; rows moved 92,510.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| ambient_component_s | 80,854 | 0.3196 | 29882 | 0 | 12162 |
| constructor_component_ci_low_s | 77,645 | 0.369 | 60617 | 0 | 643 |
| constructor_component_ci_high_s | 77,645 | 0.5342 | 61406 | 0 | 643 |
| constructor_component_se_s | 76,067 | 0.1555 | 16027 | 0 | 8400 |
| constructor_component_s | 73,016 | 1.307 | 60937 | 0 | 0 |
| total_explained_s | 72,650 | 4.417 | 59754 | 337 | 570 |
| driver_skill_residual_s | 69,945 | 4.417 | 58504 | 338 | 571 |
| track_unexplained_s | 69,325 | 1.541 | 53824 | 19 | 633 |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2020_2020_1_ALB_3 | ambient_temp_delta | 0.0 | 30.0 | 30.0 |
| 2020_2020_1_ALB_4 | ambient_temp_delta | 0.0 | 30.0 | 30.0 |
| 2020_2020_1_ALB_5 | ambient_temp_delta | 0.0 | 30.0 | 30.0 |
| 2020_2020_1_ALB_8 | ambient_temp_delta | 0.0 | 30.0 | 30.0 |
| 2020_2020_1_ALB_2 | ambient_temp_delta | 0.0 | 30.0 | 30.0 |

### fct_ghost_car_pace

Key ['ghost_id']; matched 1,369,521; rows moved 1,369,521.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| host_deg_slope_sd_s_per_lap | 1,369,490 | 0.01469 | 9928 | 0 | 76590 |
| ego_deg_slope_sd_s_per_lap | 1,369,211 | 0.01341 | 8690 | 0 | 76311 |
| host_cliff_shift_se_laps | 1,362,212 | 0.1836 | 321542 | 0 | 206970 |
| ego_cliff_shift_se_laps | 1,361,780 | 0.1836 | 319609 | 0 | 192513 |
| ego_deg_slope_s_per_lap | 1,292,920 | 0.01886 | 202673 | 0 | 0 |
| host_deg_slope_s_per_lap | 1,291,692 | 0.07289 | 203870 | 0 | 0 |
| predicted_lap_time_s | 1,196,448 | 1.936 | 994893 | 0 | 0 |
| predicted_residual_pace_s | 1,196,448 | 1.936 | 994893 | 0 | 0 |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 7d97b7521a9daf9ba52bbe82d497ee50 | age_in_stint | 19.0 | 2.0 | 17.0 |
| 59f81ff1687cdd160165d307d0a41230 | age_in_stint | 21.0 | 4.0 | 17.0 |
| 199e0a703432dcabef0767fc96ddb8e8 | age_in_stint | 22.0 | 5.0 | 17.0 |
| ded43ab1461c3b20e344ffefb1b434b6 | age_in_stint | 25.0 | 8.0 | 17.0 |
| c2467a3250891c05f32f06efe898664f | age_in_stint | 20.0 | 3.0 | 17.0 |

### fct_ghost_race_finish

Key ['ghost_race_id']; matched 29,964; rows moved 29,964.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| predicted_mean_lap_se_s | 29,964 | 0.2144 | 9516 | 0 | 1615 |
| finish_pos_se | 29,964 | 1.185 | 19664 | 0 | 8116 |
| p_beats_next | 28,449 | 0.4973 | 23858 | 54 | 2072 |
| predicted_mean_lap_s | 26,598 | 1.078 | 23500 | 0 | 0 |
| predicted_mean_residual_pace_s | 26,598 | 1.078 | 23507 | 0 | 0 |
| predicted_total_race_time_s | 26,598 | 198 | 26469 | 0 | 0 |
| predicted_finish_position | 6,368 | - | - | - | - |
| delta_vs_actual_position | 5,763 | - | - | - | - |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 7000fe144ac71e3f26cea7c479c3963d | predicted_total_race_time_s | 3527.6585296 | 3329.6870158 | 197.971513 |
| 5a15cab703ef3c32f7af70e50fe73249 | predicted_total_race_time_s | 3420.9990474 | 3223.7704557 | 197.228591 |
| 68cbdac8418805fc0a95858f6c4997dc | predicted_total_race_time_s | 3811.7049471 | 3614.8657461 | 196.839200 |
| d72a1716ba9b9629267094b7d59ee53f | predicted_total_race_time_s | 3606.4701859 | 3410.1975048 | 196.272681 |
| bf1d51b9059a565fd1625ee0acf6d734 | predicted_total_race_time_s | 3721.7351713 | 3525.4861811 | 196.248990 |

### fct_stint_features

Key ['stint_id']; matched 8,856; rows moved 5,096.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| tyre_management_score | 3,258 | 2.856 | 1305 | 24 | 9 |
| cumulative_dirty_air_tax_s | 1,341 | 4.303 | 244 | 0 | 1097 |
| end_of_stint_pace_falloff_s_per_lap | 1,018 | 0.2903 | 881 | 28 | 38 |
| end_regime | 141 | - | - | - | - |
| compound | 106 | - | - | - | - |
| starting_tyre_age_laps | 96 | - | - | - | - |
| pit_decision_class | 90 | - | - | - | - |
| cumulative_thermal_load_end | 80 | 96.02 | 36 | 36 | 7 |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2022_2022_18_ZHO_2 | cumulative_thermal_load_end | 5.1044 | 101.1257 | 96.0213 |
| 2022_2022_18_ALO_2 | cumulative_thermal_load_end | 2.9227 | 97.9135 | 94.9908 |
| 2022_2022_18_RIC_2 | cumulative_thermal_load_end | 3.7117 | 92.2248 | 88.5131000 |
| 2022_2022_18_MSC_2 | cumulative_thermal_load_end | 5.4696 | 76.4758 | 71.0062 |
| 2024_2024_4_PIA_1 | cumulative_thermal_load_end | 0.0123 | 24.7625 | 24.7502 |

### int_constructor_structural_pace

Key ['constructor_race_id']; matched 1,634; rows moved 1,634.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| fit_timestamp | 1,634 | - | - | - | - |
| constructor_structural_pace_ci_low_s | 871 | 0.369 | 696 | 0 | 10 |
| constructor_structural_pace_ci_high_s | 871 | 0.5342 | 704 | 0 | 10 |
| constructor_structural_pace_s | 820 | 0.3046 | 689 | 0 | 10 |
| constructor_structural_pace_se_s | 773 | 0.1555 | 214 | 0 | 10 |
| panel_observations_n | 67 | - | - | - | - |
| clean_teammate_pair_laps_n | 67 | - | - | - | - |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2025_2025_12_Ferrari | constructor_structural_pace_ci_high_s | 0.7780485548 | 0.2438804015 | 0.53416815 |
| 2024_2024_14_Williams | constructor_structural_pace_ci_low_s | -0.046713737 | 0.3223112758 | 0.36902501 |
| 2024_2024_14_Williams | constructor_structural_pace_s | 0.2674866273 | 0.5720575686 | 0.30457094 |
| 2025_2025_12_Aston Martin | constructor_structural_pace_ci_low_s | -0.295635385 | 0.0073631294 | 0.30299851 |
| 2024_2024_14_Ferrari | constructor_structural_pace_ci_high_s | -0.357145533 | -0.642261260 | 0.28511572 |

### int_corner_skill_residuals

Key ['corner_id']; matched 2,575,557; rows moved 892,974.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| mid_corner_residual_s | 475,746 | 15.99 | 451916 | 6761 | 3637 |
| braking_loss_s | 465,002 | 13.02 | 394154 | 9346 | 4785 |
| corner_residual_total_s | 390,247 | 22.52 | 348181 | 4163 | 4778 |
| exit_residual_s | 316,688 | 6.345 | 266672 | 4048 | 4265 |
| field_corner_sample_n | 122,869 | - | - | - | - |
| corner_unmapped_flag | 10,398 | - | - | - | - |
| corner_residual_unexplained_s | 8,941 | 0 | 0 | 4163 | 4778 |
| stint_id | 7,869 | - | - | - | - |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2020_2020_1_LAT_31_C_Turn_2 | corner_residual_total_s | 8.0026296823 | -14.51795486 | 22.5205845 |
| 2020_2020_1_GRO_18_C_Turn_3 | corner_residual_total_s | -15.30480399 | 4.2987779586 | 19.6035819 |
| 2020_2020_1_GRO_19_C_Turn_3 | corner_residual_total_s | -12.59719835 | 5.7343166374 | 18.3315149 |
| 2020_2020_1_GRO_36_C_Turn_3 | corner_residual_total_s | -17.19383908 | 0.9727527806 | 18.1665918 |
| 2020_2020_1_RAI_36_C_Turn_3 | corner_residual_total_s | 0.9574124505 | -16.31000553 | 17.2674179 |

### int_dirty_air_tax_component

Key ['lap_id']; matched 147,911; rows moved 147,911.
| column | rows moved | max abs delta | rows > 1e-3 | NULL -> value | value -> NULL |
|---|---|---|---|---|---|
| tax_calibration_confidence | 147,911 | 3.021e-05 | 0 | 0 | 0 |
| cumulative_dirty_air_tax_race_s | 5,421 | 5.627 | 5421 | 0 | 0 |
| dirtiest_air_lap_in_race_flag | 334 | - | - | - | - |
| dirty_air_intensity_lag1 | 266 | 1 | 266 | 0 | 0 |
| dirty_air_tax_s | 266 | 0.331 | 266 | 0 | 0 |
| dirty_air_tax_se_s | 266 | 0.04965 | 266 | 0 | 0 |

| key | column | old | new | abs delta |
|---|---|---|---|---|
| 2019_2019_16_STR_52 | cumulative_dirty_air_tax_race_s | 9.268 | 3.641 | 5.62700000 |
| 2019_2019_16_STR_53 | cumulative_dirty_air_tax_race_s | 9.599 | 3.972 | 5.62700000 |
| 2019_2019_16_STR_51 | cumulative_dirty_air_tax_race_s | 8.9370000000 | 3.641 | 5.29600000 |
| 2019_2019_16_STR_50 | cumulative_dirty_air_tax_race_s | 8.6060000000 | 3.641 | 4.96500000 |
| 2019_2019_16_STR_49 | cumulative_dirty_air_tax_race_s | 8.2750000000 | 3.641 | 4.63400000 |

Other tables with movement are in the table in section 2 and in summary.json. Note that for int_constructor_structural_pace every row moves only because of fit_timestamp; its value columns move on 773 to 871 of 1,634 rows.

## 4. dbt build and tests

Seeds 19 of 19 OK. dbt run (104 models, the full tree minus the exclusions): 104 of 104 OK (a first partial run of 16 and 21 upstream models preceded it, to give the car-FE fits their input). dbt test: 1,449 tests, 1,395 pass, 54 do not (fail or error). Run and test were separate commands (dbt build would skip every model downstream of a failing test).

| class | tests |
|---|---|
| A. 2026 rows missing from the race_to_track seed (26 relationships tests to race_to_track + assert_race_to_track_covers_all_races) | 27 |
| B. label-freeze (assert_prior_season_labels_frozen) | 1 |
| C. other | 26 |

Class C split: C4_2021_12_not_2026 = 2; C1_failing_rows_all_2026 = 6; C5_degradation_isotonic_parquet_absent = 12; C3_2026_event_slug_not_in_dim_circuits = 1; C2_2026_constructors_not_in_dim_constructors = 5. C1: failing rows are all 2026 (fuel-load, push-residual, stint-geometry compound code, microsector/proximity blue-flag, microsector class coverage). C2: Cadillac and Audi (2026 constructors) not in dim_constructors. C3: event slug barcelona_grand_prix not in dim_circuits. C4: 2021_12 (a lap race with no rating; wet flag with no tyre data). C5: ERROR status, the degradation_isotonic.parquet source does not exist in the scratch fits dir (excluded by design). Whether C1 to C3 follow from the seed gap was not tested; they are 2026-only by their failing rows.

Every failing test, one line each:

| class | test | status | failing rows | detail |
|---|---|---|---|---|
| A | assert_race_to_track_covers_all_races | FAIL | 76 | 19 races x 4 checks (missing from race_to_track; dropped by int_lap_fuel_state, int_compound_cliff_predicted, int_lap_residual_decomposed); all 2026 |
| A | relationships_fct_stint_features_race_id__race_id__ref_race_to_track_ | FAIL | 1,107 | 1107 orphan rows, 1107 of them 2026; non-2026: [] |
| A | relationships_fct_telemetry_deltas_race_id__race_id__ref_race_to_track_ | FAIL | 165,619 | 165619 orphan rows, 165619 of them 2026; non-2026: [] |
| A | relationships_int_corner_metrics_race_id__race_id__ref_race_to_track_ | FAIL | 312,693 | 312693 orphan rows, 312693 of them 2026; non-2026: [] |
| A | relationships_int_event_corrections_race_id__race_id__ref_race_to_track_ | FAIL | 22,178 | 22178 orphan rows, 22178 of them 2026; non-2026: [] |
| A | relationships_int_lap_fuel_state_qualifying_race_id__race_id__ref_race_to_track_ | FAIL | 2,839 | 2839 orphan rows, 2839 of them 2026; non-2026: [] |
| A | relationships_int_qualifying_driver_summary_race_id__race_id__ref_race_to_track_ | FAIL | 434 | 434 orphan rows, 434 of them 2026; non-2026: [] |
| A | relationships_int_qualifying_push_laps_race_id__race_id__ref_race_to_track_ | FAIL | 6,693 | 6693 orphan rows, 6693 of them 2026; non-2026: [] |
| A | relationships_int_qualifying_segments_race_id__race_id__ref_race_to_track_ | FAIL | 60 | 60 orphan rows, 60 of them 2026; non-2026: [] |
| A | relationships_int_stint_end_regime_race_id__race_id__ref_race_to_track_ | FAIL | 1,107 | 1107 orphan rows, 1107 of them 2026; non-2026: [] |
| A | relationships_int_stint_geometry_race_id__race_id__ref_race_to_track_ | FAIL | 22,178 | 22178 orphan rows, 22178 of them 2026; non-2026: [] |
| A | relationships_stg_circuit_info_race_id__race_id__ref_race_to_track_ | FAIL | 274 | 274 orphan rows, 274 of them 2026; non-2026: [] |
| A | relationships_stg_laps_circuit_key__race_id__ref_race_to_track_ | FAIL | 22,178 | 22178 orphan rows, 22178 of them 2026; non-2026: [] |
| A | relationships_stg_laps_qualifying_circuit_key__race_id__ref_race_to_track_ | FAIL | 6,693 | 6693 orphan rows, 6693 of them 2026; non-2026: [] |
| A | relationships_stg_laps_qualifying_race_id__race_id__ref_race_to_track_ | FAIL | 6,693 | 6693 orphan rows, 6693 of them 2026; non-2026: [] |
| A | relationships_stg_laps_race_id__race_id__ref_race_to_track_ | FAIL | 22,178 | 22178 orphan rows, 22178 of them 2026; non-2026: [] |
| A | relationships_stg_pits_race_id__race_id__ref_race_to_track_ | FAIL | 801 | 801 orphan rows, 801 of them 2026; non-2026: [] |
| A | relationships_stg_race_control_race_id__race_id__ref_race_to_track_ | FAIL | 3,346 | 3346 orphan rows, 3346 of them 2026; non-2026: [] |
| A | relationships_stg_results_qualifying_race_id__race_id__ref_race_to_track_ | FAIL | 440 | 440 orphan rows, 440 of them 2026; non-2026: [] |
| A | relationships_stg_results_race_id__race_id__ref_race_to_track_ | FAIL | 418 | 418 orphan rows, 418 of them 2026; non-2026: [] |
| A | relationships_stg_sector_times_race_id__race_id__ref_race_to_track_ | FAIL | 65,889 | 65889 orphan rows, 65889 of them 2026; non-2026: [] |
| A | relationships_stg_session_status_qualifying_race_id__race_id__ref_race_to_track_ | FAIL | 242 | 242 orphan rows, 242 of them 2026; non-2026: [] |
| A | relationships_stg_session_status_race_id__race_id__ref_race_to_track_ | FAIL | 101 | 101 orphan rows, 101 of them 2026; non-2026: [] |
| A | relationships_stg_telemetry_position_race_id__race_id__ref_race_to_track_ | FAIL | 7,374,946 | 7374946 orphan rows, 7374946 of them 2026; non-2026: [] |
| A | relationships_stg_telemetry_race_id__race_id__ref_race_to_track_ | FAIL | 14,625,196 | 14625196 orphan rows, 14625196 of them 2026; non-2026: [] |
| A | relationships_stg_track_status_race_id__race_id__ref_race_to_track_ | FAIL | 350 | 350 orphan rows, 350 of them 2026; non-2026: [] |
| A | relationships_stg_weather_race_id__race_id__ref_race_to_track_ | FAIL | 22,178 | 22178 orphan rows, 22178 of them 2026; non-2026: [] |
| B | assert_prior_season_labels_frozen | FAIL | 7 | season_label_stats differ for 2018, 2019, 2020, 2021, 2022, 2023, 2024 (observed vs expected row count / value) |
| C/C1 | assert_fuel_load_matches_scheduled_distance | FAIL | 38 | 38 rows = 19 2026 races x (no scheduled distance, no fuel rows) |
| C/C1 | assert_microsector_agrees_with_blue_flags | FAIL | 1 | 1 row, race_year 2026 |
| C/C1 | assert_microsector_corner_class_covers_panel | FAIL | 2 | 2 rows, 2026_6 and 2026_14 |
| C/C1 | assert_proximity_agrees_with_blue_flags | FAIL | 1 | 1 row, race_year 2026 |
| C/C1 | assert_push_residual_fuel_neutral | FAIL | 18,585 | 18,585 laps uncorrected_valid_lap, all lap_id 2026_* |
| C/C1 | assert_stint_geometry_2018_compound_code_null | FAIL | 1 | 21,618 rule_2 rows, all race_year 2026 (19 races) |
| C/C2 | relationships_mart_corner_skill_driver_constructor_id__constructor_id__ref_dim_constructors_ | FAIL | 4 | orphan values ['Cadillac', 'Audi'] (Cadillac, Audi), all rows 2026 |
| C/C2 | relationships_stg_laps_constructor_id__constructor_id__ref_dim_constructors_ | FAIL | 3,721 | orphan values ['Cadillac', 'Audi'] (Cadillac, Audi), all rows 2026 |
| C/C2 | relationships_stg_laps_qualifying_constructor_id__constructor_id__ref_dim_constructors_ | FAIL | 939 | orphan values ['Cadillac', 'Audi'] (Cadillac, Audi), all rows 2026 |
| C/C2 | relationships_stg_results_constructor_id__constructor_id__ref_dim_constructors_ | FAIL | 76 | orphan values ['Cadillac', 'Audi'] (Cadillac, Audi), all rows 2026 |
| C/C2 | relationships_stg_results_qualifying_constructor_id__constructor_id__ref_dim_constructors_ | FAIL | 80 | orphan values ['Cadillac', 'Audi'] (Cadillac, Audi), all rows 2026 |
| C/C3 | relationships_int_pit_loss_circuit_circuit_id__circuit_id__ref_dim_circuits_ | FAIL | 1 | circuit_id barcelona_grand_prix (1 row), event slug not in dim_circuits; no 2026 race_id in this table |
| C/C4 | assert_every_lap_race_rated_or_explained | FAIL | 1 | failing row is 2021_12 (20 valid laps now, no rating / no tyre data) |
| C/C4 | assert_rain_flag_matches_tyres | FAIL | 1 | failing row is 2021_12 (20 valid laps now, no rating / no tyre data) |
| C/C5 | dbt_utils_source_unique_combination_of_columns_fits_degradation_isotonic_circuit_id__era__compound__lap_in_stint | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_accepted_values_fits_degradation_isotonic_era__pre2022__post2022 | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_circuit_id | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_compound | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_dirty_air_deg_mult | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_era | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_lap_in_stint | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_obs_deg_from_fresh_p10_mono_s | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_obs_deg_from_fresh_p50_mono_s | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_obs_deg_from_fresh_p90_mono_s | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_temp_headroom_c | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |
| C/C5 | source_not_null_fits_degradation_isotonic_temp_penalty_s_per_deg | ERROR | - | source test on data/fits/degradation_isotonic.parquet, which is not in the scratch fits dir (by design: TX-09/XM) |

assert_prior_season_labels_frozen, observed vs expected: 2018 rows 10,813 vs 11,282, value 0.0771 vs 0.0441; 2019 14,561 vs 14,561, -0.1707 vs -0.1799; 2020 9,129 vs 9,383; 2021 14,260 vs 14,260, -0.0051 vs 0.0028; 2022 10,941 vs 10,941, -0.0478 vs -0.0435; 2023 12,682 vs 12,654, -0.2941 vs -0.2941; 2024 15,038 vs 15,069, -0.1605 vs -0.1878. 2025 passes.

## 5. Baseline counts for TX-17, TX-18, TX-19

The tree already carries the TX-17 and TX-18 edits and the TX-20 telemetry bound (fct_stint_features, fct_ghost_car_pace, fct_ghost_race_finish and stg_telemetry no longer zero-fill / clip as the Nov-8 export did). So each count is given as: the Nov-8 published value, the scratch value on the current tree, and, where it follows exactly, what the old fill rule would give on the scratch data. 2026 rows are not in the ghost marts; fct_stint_features has 1,107 2026 stints (all NULL dirty air).

### TX-17: stints with zero dirty-air tax (fct_stint_features)

| measure | published Nov-8 | scratch 2018-2025 | scratch 2026 |
|---|---|---|---|
| stints | 8,945 | 8,895 | 1,107 |
| cumulative_dirty_air_tax_s = 0 | 2,393 | 1,284 (all with measured laps) | 0 |
| cumulative_dirty_air_tax_s NULL | 0 | 1,134 | 1,107 |
|   of which NO_AIR_STATE / NO_TELEMETRY | - | 1,043 / 91 | 1,034 / 73 |
| stints with no measured dirty-air lap (n_dirty_air_measured_laps = 0) | - | 1,134 | 1,107 |
| zero under the old COALESCE rule (measured zeros + unmeasured) | 2,393 (as published) | 2,418 = 1,284 + 1,134 | - |

So on the scratch data 2,418 of 8,895 stints would be 0 under the old rule, of which 1,134 have no measured lap; the current tree writes those 1,134 as NULL and keeps 1,284 measured zeros.

### TX-18: ghost columns (fct_ghost_car_pace, 2018-2025 scratch; all rows 1,372,651; published 1,384,558)

| column | published Nov-8 (rows equal to 0) | scratch (rows) | note |
|---|---|---|---|
| host_constructor_pace_s = 0 (flag host_constructor_pace_is_prior) | 1,135 | 1,122 | flag true on 1,122 |
| host_constructor_pace_se_s | = 0 on 1,135 | = 0 on 0; NULL on 1,122 |  |
| host_deg_slope_s_per_lap = 0 (flag host_deg_slope_is_prior) | 82,298 | 79,527 | flag true on 77,430 |
| ego_deg_slope_s_per_lap = 0 (flag ego_deg_slope_is_prior) | 81,031 | 78,221 | flag true on 77,151 |
| host_deg_slope_sd_s_per_lap | = 0 on 80,261 | = 0 on 31; NULL on 77,430 | old rule would give 77,461 (77,430 + 31) |
| ego_deg_slope_sd_s_per_lap | = 0 on 80,261 | = 0 on 310; NULL on 77,151 | old rule would give 77,461 (77,151 + 310) |
| host_cliff_shift_se_laps | = 0 on 216,169 | = 0 on 0; NULL on 207,945 |  |
| ego_cliff_shift_se_laps | = 0 on 201,531 | = 0 on 0; NULL on 193,353 |  |
| circuit_interaction_s = 0 (flag circuit_interaction_is_prior) | 433,247 | 435,126 | flag true on 0 (its zeros are estimates) |

fct_ghost_race_finish: finish_pos_se = 0 on 4 of 30,344 published rows; scratch 0 of 30,054 rows are 0 and 8,178 are NULL (reason NO_SE_ESTIMATE 8,178, SINGLE_DRIVER_SCENARIO 0); predicted_mean_lap_se_s NULL on 1,619; p_beats_next NULL on 3,597 (published predicted_mean_lap_se_s NULL on 0). The 4 published zeros cannot be re-identified on the scratch build, because the zero-fill is gone from the tree.

### TX-19: Spa telemetry at or above 6,500 m

Bronze telemetry (data/bronze/telemetry, distance_m > 0 samples) for the Belgian GP, all seasons 2018-2026: 611,097 of 5,848,535 samples (10.4%) are at or above 6,500 m; the largest distance is 7,163.5 m (2025), under the bound of 7,705 m (7,004 x 1.10, rounded up; the 7,704 m column below counts samples at or above 7,704). The fixed 6,500 m cut that produced the Nov-8 export would have dropped all of them.

| season | samples (distance > 0) | >= 6,500 m | >= 7,704 m | max distance m |
|---|---|---|---|---|
| 2018 | 607,236 | 63,890 | 0 | 7068.2 |
| 2019 | 684,369 | 72,230 | 0 | 7080.9 |
| 2020 | 773,350 | 81,326 | 0 | 7013.2 |
| 2021 | 108,605 | 12,213 | 0 | 7077.7 |
| 2022 | 715,891 | 74,627 | 0 | 6993.8 |
| 2023 | 705,647 | 77,250 | 0 | 7045.7 |
| 2024 | 703,805 | 72,901 | 0 | 7067.4 |
| 2025 | 776,855 | 78,312 | 0 | 7163.5 |
| 2026 | 772,777 | 78,348 | 0 | 7065.9 |

On the scratch build stg_telemetry (per-circuit bound in the tree) keeps all of them: 611,097 samples at or above 6,500 m in total, all at Spa (2018-2025 rows: 532,749; the rest are the 2026 Belgian GP, 78,348). Other circuits with samples at or above 6,500 m in Bronze, which stg_telemetry still drops: abu_dhabi_grand_prix 725, austrian_grand_prix 13,497, bahrain_grand_prix 155, brazilian_grand_prix 302, canadian_grand_prix 423, chinese_grand_prix 425, dutch_grand_prix 826, hungarian_grand_prix 215, italian_grand_prix 8,171, japanese_grand_prix 651, styrian_grand_prix 303 (per-circuit table: bronze_telemetry_distance_by_race.csv). The Nov-8 export contains no telemetry-sample table, so the published side of this count is the rule, not a file.

## 6. Did not run, or limits

- mart_degradation_history_envelope and int_lap_physical_ahead plus everything downstream (including int_coast_tax_component, absent from the scratch export): excluded, as agreed.
- degradation_isotonic.parquet does not exist, so 12 source tests on it error (class C5).
- Car-FE fits (constructor_car_fe, constructor_car_fe_isolation) were fitted in a scratch venv with pyfixest 0.60.0 into scratch fits; the repo .venv has pyfixest 0.70.0, which was not touched. The published fits are not on disk, so no fit-level diff against them exists.
- The ML outputs (driver_network_rating, mart_degradation_predictions) and the assistant card files were not rebuilt; the 55 exported tables are the dbt-derived ones plus assistant_entities and the qv_* views.
- The exporter aborts if mart_degradation_history_envelope is missing, so the export was run on a second scratch copy (exportdb/export_copy.duckdb) with an empty stub table of that name; the stub is not in the dbt-built dev.duckdb.
- No test was re-run with an altered tree; no attempt was made to attribute movement to Bronze vs code vs refit.
