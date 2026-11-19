# Fresh audit 01: STAGING and REFERENCE models

Scope: `transform/models/staging/*.sql` (18 models) and `transform/models/reference/*.sql` (6 models), plus `staging/schema.yml`, `staging/src_*.yml`, `reference/schema.yml`. Read only. Current Bronze (2018-2026) taken as the only truth; 2018 Italian GP race (HD15 B) is a known gap; 2026 not audited.

Method note: I read all SQL and yml. For a few claims I ran read-only DuckDB queries straight on the Bronze parquet in `data/bronze` (no warehouse touched, nothing written to the repo). Those are marked "Bronze check". I did not run dbt, so no model output was inspected.

## Flow diagram (this group)

Sources and seeds into this group:

```
source bronze_f1.raw_laps                 -> stg_laps
source bronze_f1.raw_laps                 -> stg_pits
source bronze_f1.raw_laps_qualifying      -> stg_laps_qualifying
source bronze_f1.raw_weather              -> stg_weather
source bronze_f1.raw_results              -> stg_results
source bronze_f1.raw_results              -> dim_driver_seasons
source bronze_f1.raw_results_qualifying   -> stg_results_qualifying
source bronze_f1.raw_track_status         -> stg_track_status
source bronze_f1.raw_race_control         -> stg_race_control
source bronze_f1.raw_session_status       -> stg_session_status
source bronze_f1.raw_session_status_qualifying -> stg_session_status_qualifying
source bronze_f1.raw_circuit_info         -> stg_circuit_info
source bronze_f1.raw_telemetry            -> stg_telemetry
source bronze_f1.raw_telemetry (source='pos') -> stg_telemetry_position
source bronze_jolpica.raw_jolpica_pit_stops -> stg_jolpica_pit_stops
seed raw_dim_events                       -> stg_events
seed tyre_allocations                     -> stg_tyre_allocations
seed circuit_reference                    -> dim_circuits
seed compound_cliff_params                -> dim_compounds_season
seed seed_manual_lap_exceptions           -> stg_laps (is_valid_lap NOT EXISTS)
seed race_to_track                        -> dim_corners
```

Edges inside the group:

```
stg_laps            -> stg_weather
stg_laps            -> stg_sector_times
stg_laps            -> stg_lap_tyre_qa
stg_laps            -> dim_drivers
stg_laps            -> dim_corners
stg_pits            -> stg_lap_tyre_qa
stg_results         -> stg_race_control
stg_circuit_info    -> dim_corners
dim_circuits        -> dim_corners
```

Models in the group with no in-group upstream: stg_laps_qualifying, stg_results_qualifying, stg_telemetry, stg_telemetry_position, stg_track_status, stg_session_status, stg_session_status_qualifying, stg_events, stg_jolpica_pit_stops, stg_tyre_allocations, stg_circuit_info, stg_pits, stg_results, dim_circuits, dim_compounds_season, dim_constructors, dim_driver_seasons.

Dependencies outside the group (upstream): only Bronze sources and seeds listed above. No staging/reference model reads an intermediate or mart.

Downstream consumers outside the group (by `ref()` search of models/, tests/, macros/, analyses/) are given per model below. dbt vars used inside this group: `wet_humidity_min_pct` 70.0, `wet_field_tyre_share_min` 0.5, `tyre_qa_max_unassigned_leading_laps` 2, `tyre_qa_boundary_window_laps` 3, `tyre_qa_race_unexplained_boundaries_min` 5, `tyre_qa_race_unmatched_pit_share_min` 0.3, `corner_entry_margin_m` 250, `corner_exit_margin_m` 150 (dbt_project.yml lines 170-171, 188-206).

Summary of verdicts: SOUND 17, QUESTIONABLE 6, WRONG 1 (24 models).

---

# STAGING

## stg_laps  (view) - QUESTIONABLE (low severity)

1. Purpose: one row per race lap; renames Bronze, ns to s, and derives the SC / VSC / red-flag lap flags and `is_valid_lap`.
2. Flow: reads `source('bronze_f1','raw_laps')` and `ref('seed_manual_lap_exceptions')`. Read by in-group stg_weather, stg_sector_times, stg_lap_tyre_qa, dim_drivers, dim_corners; and by (models) fct_ghost_race_finish, mart_race_coverage, mart_corner_skill_driver, fct_ghost_car_pace, fct_track_limits, fct_track_limits_driver_session, fct_speed_traps, fct_speed_traps_season, fct_pit_stop_crosscheck, fct_stint_features, fct_telemetry_deltas, int_pit_loss_circuit, int_synthetic_teammate, int_driver_race_paired_laps, int_driver_race_skill_loro, int_sc_hazard_history, int_sector_residual_decomposed, int_stint_geometry, int_lap_fuel_state, int_lap_residual_decomposed, int_event_corrections, int_lap_normalized_pace, int_corner_skill_residuals, int_microsector_corner_class, int_constructor_structural_pace, int_lap_air_state, int_lap_thermal_proxy; plus about 15 singular tests.
3. How it works: every time column is `CAST(x AS DOUBLE)/1e9` (stg_laps.sql:43-85). Bronze time columns are BIGINT nanoseconds (Bronze check: LapTime, LapStartTime, Sector*Time are BIGINT). Compound is upper-cased and `NONE/NAN/UNKNOWN/NULL/''` become NULL (105-112). Flags are digit-presence regexes on the TrackStatus string: 4 = SC, 6/7 = VSC, 5 = red (127-129). `is_valid_lap` = timed, not pit lap (PitIn or PitOut present), not deleted, accurate, no digit 4-7 anywhere in TrackStatus, `lap_number > 1`, and not in the manual exclusion seed (135-153). Surrogate `lap_id` = season_race_driver_lap.
4. Maths check:
   - Units: ns to s is correct. SOUND.
   - Sign / indexing: lap 1 excluded by `lap_number > 1` (139). Intended (standing start). SOUND.
   - NULL propagation: `is_valid_lap` is a bare AND chain (135-153). If `lap_time_s` is NULL (909 of 210,660 Bronze laps have no LapTime, Bronze check) or `is_accurate` is NULL, the result is NULL, not FALSE, unless another term is FALSE. `WHERE is_valid_lap` drops those rows (right answer), but `WHERE NOT is_valid_lap` or a `COUNT(*) FILTER (WHERE NOT is_valid_lap)` would silently skip them. The yml declares no not_null test on `is_valid_lap` (the three other flags have one). QUESTIONABLE, stg_laps.sql:135-153.
   - Regex `REGEXP_MATCHES(x,'.*4.*')` is a partial match in DuckDB so the `.*` is redundant but harmless.
   - A lap whose TrackStatus merely contains a 4 (SC ending mid-lap) is excluded entirely. Conservative; design choice, not an error.
   - `seed_manual_lap_exceptions` NOT EXISTS is a correlated anti-join to `renamed`; one seed row per lap so no fan-out. SOUND.
5. Fills: line 95 `COALESCE(pitouttime IS NOT NULL OR pitintime IS NOT NULL, FALSE)`: that OR is never NULL (two IS NOT NULL terms), so the COALESCE is a no-op. Compound to NULL (105-112) is a blanking, not a fill. No numeric default enters any number.
6. Tests (staging/schema.yml 4-~140, src_formula1.yml raw_laps): lap_id not_null+unique; race_id and circuit_key relationships to race_to_track; driver_id to dim_drivers; constructor_id to dim_constructors; compound accepted_values and relationships to dim_compounds_season; the three flags not_null. Singular: assert_track_status_flag_partition (checks the regex decode, a logic test), assert_raw_laps_has_both_sessions. Source test: unique (season, race_id, Driver, LapNumber). No test on `is_valid_lap` maths beyond the flag-partition check. Mostly shape plus one decode test.
Doc note: the yml description of `tyre_life` ("laps already completed ... at the start of this lap") conflicts with stg_lap_tyre_qa's finding that TyreLife counts from the first assigned lap; description only.

## stg_laps_qualifying  (view) - QUESTIONABLE (low severity, same cause as stg_laps)

1. Purpose: mirror of stg_laps for the Q session; adds `session_type = 'Q'`.
2. Flow: reads `source('bronze_f1','raw_laps_qualifying')`. Read by int_qualifying_segments, int_qualifying_push_laps, int_lap_fuel_state_qualifying, int_lap_residual_decomposed_qualifying, fct_track_limits, fct_track_limits_driver_session, fct_speed_traps, fct_speed_traps_season, and tests assert_track_limits_reconcile, assert_speed_traps_missing_not_zero, assert_raw_laps_has_both_sessions, assert_quali_valid_share_consistent_across_seasons.
3. How it works: identical rename and ns to s as stg_laps. `is_valid_lap` differs: `(is_accurate OR race_year < 2019)` (161). Accuracy is required only from 2019 (header 149-157 explains 2018 sync flag is mostly unpopulated). It lists columns explicitly instead of `* EXCLUDE`, so it drops `compound_raw`.
4. Maths check: units SOUND. Same 3-valued NULL issue as stg_laps (158-164): a NULL `lap_time_s` yields NULL `is_valid_lap`. For 2018, `NULL OR TRUE` is TRUE, so a 2018 lap with NULL accuracy is not blocked by accuracy (intended). The 2018 waiver is a design choice that the owner should confirm; it is documented and guarded by T25. QUESTIONABLE only for NULL propagation, stg_laps_qualifying.sql:158-164.
5. Fills: line 95 COALESCE no-op (as above). Line 161 `OR race_year < 2019` is a rule bypass, not a numeric fill.
6. Tests: lap_id not_null+unique, race_id/driver_id/constructor_id/compound relationships, flags not_null (schema.yml ~190-338). Singular assert_quali_valid_share_consistent_across_seasons checks the valid share by season, which is a real logic guard on the 2018 rule. Shape plus one share test.

## stg_pits  (view) - QUESTIONABLE

1. Purpose: one row per pit stop (in-lap), with exit side resolved from the next pit lap.
2. Flow: reads `source('bronze_f1','raw_laps')`. Read by in-group stg_lap_tyre_qa; by fct_pit_stop_crosscheck, int_pit_strategy_value, int_pit_loss_circuit, int_microsector_proximity, int_lap_proximity; tests assert_pit_loss_excludes_neutralised, assert_microsector_excludes_pit_lane, assert_stint_boundaries_match_pits, assert_proximity_excludes_pit_lane, assert_microsector_car_ahead_is_previous_crossing, assert_pit_stop_grain.
3. How it works: keep laps with PitInTime or PitOutTime (52); `LEAD` over the driver's pit laps gives next pit lap number, its PitOutTime and compound (62-70); keep rows with PitInTime (105). A stop gets an exit only when the next pit lap is exactly `lap_number + 1` (89-103); duration = next pit-out time minus this pit-in time (102). Times ns to s.
4. Maths check:
   - Sign and indexing: in-lap n, out-lap n+1, `pit_out_time - pit_in_time` positive. SOUND. 358 Bronze laps carry both PitIn and PitOut (Bronze check); these are correctly handled because the LEAD reads the following row's PitOut, not the same row's.
   - Compound is `UPPER(CAST(compound AS VARCHAR))` only (stg_pits.sql:37), NOT the NONE/NAN/UNKNOWN to NULL mapping that stg_laps uses. Bronze holds `'NAN'` (646 laps), `'NONE'` (484), `'UNKNOWN'` (60) (Bronze check, all laps). Any of those on a pit lap flows into `compound_in` / `compound_out` as the literal string, so "compound changed at this stop" comparisons (the yml quotes 3,844 of 5,109 differ) can count NAN to HARD as a change. QUESTIONABLE, stg_pits.sql:37, 87, 99.
   - `pit_out_lap_number` can be set while `pit_out_time_s` is NULL if the next row lacks PitOut; assert_pit_stop_grain check 3 catches that.
   - Duration spans whole pit lane and red-flag waits (documented in header lines 12-15; consumers must filter). Not an error, a trap.
5. Fills: none (NULLs are left NULL by design, 88-103).
6. Tests: lap_id not_null+unique, pit_in_lap_number and pit_in_time_s not_null, relationships (schema.yml 485-552). assert_pit_stop_grain is a real logic test (out-lap is next lap, exit columns resolve together, etc.). No test on compound values.

## stg_lap_tyre_qa  (view) - WRONG (narrow: stint 0, 3 driver-races) plus QUESTIONABLE items

1. Purpose: repair lap-1 stint/tyre-life gap in Bronze (F25) and quarantine races / driver-races where Bronze stint numbering contradicts the pit record (F24). Serves `stint_number`, `tyre_life`, `compound` to int_stint_geometry.
2. Flow: reads `ref('stg_laps')`, `ref('stg_pits')`. Read by int_stint_geometry, int_pit_strategy_value, int_sector_residual_decomposed, mart_race_coverage; tests assert_stint_boundaries_match_pits, assert_pit_not_taken_from_joined_boundary, assert_tyre_run_key (and assert_stint1_includes_lap1 reads via int_stint_geometry).
3. How it works: (a) `driver_race` finds each driver's first assigned stint lap and its stint, TyreLife, compound (97-118). (b) Repair when 1 to 2 leading laps are unassigned (121-196): gap laps take the first stint and compound, `TyreLife = first_tyre_life + lap_number - 1`, and the first stint's later laps get `+unassigned_leading_laps`. If the car pitted inside the gap, laps to the in-lap get stint `first_stint - 1` and NULL tyres. (c) Stint changes on the repaired numbering are matched to in-laps within 3 laps, one stop per change (199-273). (d) Race quarantined at >= 5 unexplained changes or >= 30% of racing stops unmatched with >= 3 (336-357); driver-race quarantined on any unexplained change or partial assignment (373-386). Quarantined units serve `pit_stint_ordinal` = 1 + exits before the lap + red-flag changes and NULL compound/tyre_life (389-399, 417-422).
4. Maths check:
   - TyreLife offset arithmetic. Gap lap i: `T + i - 1` (169); first assigned lap L: `T + (L-1)` (175-177); continuous across the join. SOUND.
   - Stint 0. Line 159: `first_stint_number - 1`. Bronze check: three 2018 driver-races (2018_5 HAR, 2018_5 SIR, 2018_13 VER) pitted on lap 1, first assigned lap 2, and Bronze's first stint is `1`. The formula gives `qa_stint_number = 0` for lap 1, a 0-based ordinal in a 1-based column. `stint_number` is served as this value when `tyre_qa_status = 'ok'` (418); if the verdict is quarantined it is replaced by the pit ordinal. I did not run the model so I cannot say which verdict those three get. WRONG at stg_lap_tyre_qa.sql:159 (potential stint 0; check the three driver-races).
   - `stint_source` label: `tyre_life_offset_laps` is a per-driver-race constant applied to every lap (190-194), and line 427 tests `tyre_life_offset_laps > 0`, so every lap of a repaired driver-race, including later stints that were not offset, is labelled `'bronze_lap1_repaired'`. Metadata only, no number changes. QUESTIONABLE, lines 190-194, 426-429.
   - `pit_stint_ordinal` assumes consecutive lap rows (LAG/ROWS windows by row, not by `lap_number`); a missing lap row would misalign `prev_is_exited_in_lap` (203-205). Low risk, only matters in quarantined units. QUESTIONABLE, 203-205, 389-399.
   - `last_in_lap_before` includes in-laps where the car never exited (`is_in_lap` not `is_exited_in_lap`, 206-208), so such an in-lap can "explain" a stint change. Plausible; flag for owner.
   - Join fan-out: lap_pit joins stg_pits on (race, driver, in-lap), one row per in-lap, no fan-out. racing_stops self-join on `lap_number + 1` is one-to-one. matched_stops is DISTINCT. `lap_id` unique test protects the grain. SOUND.
   - Thresholds (2 leading laps, 3-lap window, 5 changes, 30%, 3 stops) are tunable vars; owner design choice.
5. Fills: 67 `COALESCE(is_red_flag_lap, FALSE)`; 85 `COALESCE(p.car_exited, FALSE)`; 130 `COALESCE(first_in_lap < first_assigned_lap, FALSE)` (no in-lap means not stopped in gap); 203-205 `COALESCE(LAG(...), FALSE)`; 218-223 `COALESCE(change test, FALSE)` (a NULL stint is never a change); 257, 260 `COALESCE(prev_claimed_in_lap, -1)` sentinel -1 for "no earlier claim" (safe because lap numbers are positive); 341-342 `COALESCE(n_racing_stops, 0)`; 343-353 `COALESCE(..., FALSE)` so a race with no racing stops is never race-quarantined. These affect only the quarantine flags and stint ordinal, no lap-time number.
6. Tests: lap_id not_null+unique; compound relationships; `stint_source` and `tyre_qa_status` accepted_values (schema.yml 553-660). Singular assert_stint_boundaries_match_pits (T19), assert_stint1_includes_lap1 (T20), assert_tyre_run_key, assert_pit_not_taken_from_joined_boundary independently re-derive the rules, so they test the logic. Nothing in the yml asserts `stint_number >= 1`, which is why stint 0 can pass.

## stg_weather  (view) - SOUND

1. Purpose: weather sample at or before each race lap's start, plus a two-of-three wet vote that becomes `rainfall_flag`.
2. Flow: reads `source('bronze_f1','raw_weather')`, `ref('stg_laps')` (twice). Read by int_compound_cliff_predicted, int_pit_strategy_cost_curve, int_track_evolution; tests assert_track_evolution_monotone_wet/dry, assert_field_base_drift_tracks_observed, assert_rain_flag_matches_tyres, assert_field_pace_honest_range.
3. How it works: for each lap take `MAX(weather.session_time_s)` with `session_time_s <= lap_start_time_s` (66-89); laps starting before the first sample fall back to `MIN` (92-121); join back to the weather row on that exact time (176-180). `field_tyres` is the share of cars with a known compound on INTERMEDIATE or WET at that race-lap (131-142). Votes = Bronze Rainfall + (humidity >= 70) + (field share >= 0.5); `rainfall_flag = votes >= 2` (160-198). `rain_signal_disagreement` marks vote vs Bronze.
4. Maths check:
   - Clock: LapStartTime and weather `session_time_s` share an origin. Bronze check over 191 races: lap starts never precede the first weather sample except in 1 race (handled by the fallback), and last lap start is within 120 s of the last weather sample in all. SOUND.
   - Fan-out: final join is on exact `session_time_s`; Bronze check found 0 duplicate (season, race_id, session_time_s) in raw_weather, and `lap_id` unique test guards it. The lap x all earlier weather rows join (77-81) is quadratic in cost but returns one row per lap after `GROUP BY`. SOUND.
   - Laps with NULL `lap_start_time_s` are dropped (60). Bronze check: 0 NULL LapStartTime, so no laps lost today.
   - Averages: `AVG(CASE ... 1.0/0.0)` over cars with a compound; lapped or retired cars drop out naturally. Share is over the right grain (race-lap). SOUND. Share counts cars whose Bronze compound is a wet compound; a lap with only NULL compounds gives NULL share which then votes 0.
5. Fills: 161 `COALESCE(w.rainfall_flag, FALSE)` (NULL Bronze rainfall counts as no vote; Bronze check: 0 NULLs); 163-166 and 167-173 `ELSE 0` (a NULL humidity or NULL field share casts no wet vote, so missing data biases toward dry); 206 `COALESCE(rainfall_flag_bronze, FALSE)` in the disagreement flag. 91-121 fallback to first sample. None enter a continuous number; they only move the boolean.
6. Tests: lap_id not_null+unique; race_id/driver_id relationships; `rainfall_flag` not_null (schema.yml 662-750). Singular assert_rain_flag_matches_tyres checks the vote outcome per race against compound share, a real logic test. Weather yml text says "2018-2024" (stale count).

## stg_sector_times  (view) - SOUND

1. Purpose: unpivot lap sectors to one row per lap x sector.
2. Flow: reads `ref('stg_laps')`. Read by int_corner_skill_residuals, int_sector_residual_decomposed.
3. How it works: three `UNION ALL` branches, each filtered to non-NULL sector time; sector 1 pairs with `speed_i1`, 2 with `speed_i2`, 3 with `speed_fl` (finish line trap). `speed_st` is not used. Carries `is_valid_lap`.
4. Maths check: units already seconds. Speed-trap pairing is geometrically reasonable (I1 at end S1, I2 at end S2, FL at line). Grain: one row per (lap, sector), `sector_id` unique. The header claim "3 rows per lap" (line 2) is not exact because NULL sectors are dropped; harmless. No division. SOUND.
5. Fills: none.
6. Tests: sector_id not_null+unique; `sector` accepted_values 1-3; relationships. Shape only. No test that sector times sum to lap time (no maths test in this model).

## stg_results  (view) - QUESTIONABLE

1. Purpose: classified result per driver per race with DNF and cause flags.
2. Flow: reads `source('bronze_f1','raw_results')`. Read by in-group stg_race_control; mart_race_driver_summary, fct_ghost_race_finish, int_pit_loss_circuit, int_stint_end_regime, int_stint_geometry, int_lap_proximity; tests assert_dsq_not_classified, assert_ghost_self_scenario_rank, assert_mart_positions_gained_pit_lane, assert_stint_end_cause_partition, assert_tyre_run_key, assert_pit_loss_excludes_neutralised.
3. How it works: `classified_rank` = NULL if Status = 'Disqualified' else `TRY_CAST(ClassifiedPosition AS INTEGER)` (22-25). `is_classified` = rank not NULL (69). `is_dnf` = not classified AND status not like '%Lap%' AND status <> 'Finished' (74-78). `dnf_cause` by regex on status (83-96). `time_or_gap_s` = Time/1e9.
4. Maths check:
   - Classified retirements are not DNFs. Bronze check: 3,330 rows have a numeric ClassifiedPosition and 72 of them carry a non-finish status (Retired 36, Collision 6, Engine 4, Collision damage 5, ...; 3 of the 72 are the Disqualified rows that line 23 re-routes). So about 69 retirements who were still classified (they ran 90% distance) get `is_dnf = FALSE` and `dnf_cause = NULL` (line 84). Whether this is wrong depends on what "DNF" means to the hazard model; the code comment and yml say "not classified" so it is the stated rule, but for a DNF hazard model it understates retirements. QUESTIONABLE, stg_results.sql:74-78, 84.
   - 'Did not start' (17 rows) and 'Withdrew' (class W) are counted `is_dnf = TRUE` with `dnf_cause = 'non_classified'` (93). A non-starter did not retire. QUESTIONABLE, lines 74-78, 92-94.
   - `ELSE 'mechanical'` (95): any unmatched status, including the generic `'Retired'` (202 unclassified rows, Bronze check, the single largest status), is labelled mechanical. Cause unknown becomes "mechanical" silently. QUESTIONABLE, line 95.
   - Regex 'spin|spun|damage|contact' puts "Collision damage" and "Spun off" under racing, reasonable. A mechanical failure described with "damage" (e.g. "Front wing" is not matched, goes mechanical) is fine.
   - `time_or_gap_s` mixes a winner's total race time and others' gaps in one column (documented). Any consumer that treats it uniformly would be wrong; not an error here.
   - No division. Status NULLs: Bronze check 0 NULL status, so NULL-handling in `is_dnf` is not exercised.
5. Fills: `ELSE 'mechanical'` at 95 (above). `TRY_CAST` silently maps 'R','D','W','E','F','N' to NULL (24), intended.
6. Tests: result_id not_null+unique; `is_classified`, `is_dnf` not_null; `dnf_cause` accepted_values; relationships (schema.yml 802-890). Singular assert_dsq_not_classified tests the disqualification routing (logic). No test for classified-retirement or non-starter handling.

## stg_results_qualifying  (view) - SOUND

1. Purpose: official qualifying classification and Q1/Q2/Q3 best times per driver.
2. Flow: reads `source('bronze_f1','raw_results_qualifying')`. Read by int_qualifying_segments; test assert_quali_segment_matches_official.
3. How it works: rename, `q1/q2/q3` ns to s, `final_segment_reached` = Q3/Q2/Q1/'none' from which times are non-NULL.
4. Maths check: unit conversion right. `final_segment_reached` depends on non-NULL times; a driver who set a Q2 time but whose Q3 time was deleted gets Q2, correct. SOUND.
5. Fills: `ELSE 'none'` (49) is a label for "no time", not a number.
6. Tests: quali_result_id not_null+unique; relationships; `final_segment_reached` not_null (schema.yml 1216-1288). assert_quali_segment_matches_official checks segment logic downstream. Mostly shape.

## stg_session_status  (view) - SOUND

1. Purpose: race session lifecycle events; `is_red_flag_stop` = status 'Aborted'.
2. Flow: reads `source('bronze_f1','raw_session_status')`. No `ref()` consumers anywhere in transform (searched models, tests, macros, analyses); documented in docs only.
3. How it works: rename, key = race_session_time_status, `LOWER(status) = 'aborted'`.
4. Maths check: no arithmetic. Key could collide if two events share time and status; guarded by the grain test. SOUND. Unused model.
5. Fills: none.
6. Tests: session_status_id not_null+unique, `status` not_null, unique_combination (race_year, race_id, session_time_s, status) (schema.yml 1112-1156). Shape only.

## stg_session_status_qualifying  (view) - SOUND

1. Purpose: Q-session lifecycle events with `is_red_flag_stop`, `is_green_light`, `is_chequered_flag`.
2. Flow: reads `source('bronze_f1','raw_session_status_qualifying')`. Read by int_qualifying_segments.
3. How it works: as above plus two more boolean decodes ('started', 'finished').
4. Maths check: no arithmetic; the segment logic that interprets these lives downstream. SOUND.
5. Fills: none.
6. Tests: id not_null+unique, status not_null, unique_combination (schema.yml 1157-1214). Shape only.

## stg_race_control  (view) - SOUND

1. Purpose: FIA race-control messages with the car number resolved to `driver_id`, and an `is_blue_flag_event` label.
2. Flow: reads `source('bronze_f1','raw_race_control')` and `ref('stg_results')`. Read by int_stint_geometry; tests assert_microsector_agrees_with_blue_flags, assert_proximity_agrees_with_blue_flags, assert_tyre_run_key.
3. How it works: LEFT JOIN to a DISTINCT (race_id, driver_number, driver_id) from stg_results on race and trimmed car number (23-71). `is_blue_flag_event` = flag 'BLUE' and driver and lap resolved (97-101). `message_time_s` is `TRY_CAST(session_time_s AS DOUBLE)`.
4. Maths check: join fan-out would occur if two drivers share a car number in a race; Bronze check: 0 (race_id, DriverNumber) pairs map to more than one abbreviation. SOUND. `message_time_s` is deliberately not on the telemetry clock (comment 39-55) and nothing joins on it. TRY_CAST can hide a type change by returning NULL (documented, fixture-only). A blue flag with an unresolved number is FALSE (a gap, not a negative), documented.
5. Fills: line 98 `COALESCE(flag, '') = 'BLUE'` turns NULL flag into FALSE so the boolean is never NULL. Effect: non-flag messages are definite non-blue. Correct.
6. Tests: message_index not_null; race_id relationships; driver_id relationship; `is_blue_flag_event` not_null; unique_combination (race_year, race_id, message_index) (schema.yml 986-1047). The two blue-flag agreement tests check the label against proximity features (logic). The join-fan-out risk is covered by the unique grain test.

## stg_track_status  (view) - SOUND

1. Purpose: track-status change events with named decode and `status_duration_s`.
2. Flow: reads `source('bronze_f1','raw_track_status')`. Read by int_pit_loss_circuit, int_sc_hazard_history, int_microsector_proximity; tests assert_pit_loss_excludes_neutralised, assert_sc_hazard_no_forward_leakage.
3. How it works: `SELECT DISTINCT` to remove exact duplicates (17-57); decode 1/2/4/5/6/7 to labels and booleans; `LEAD(session_time_s) OVER (PARTITION BY race ORDER BY session_time_s, status_code) - session_time_s` for duration (72-74).
4. Maths check: duration is the time to the next event, NULL for the last. Same-instant events (Bronze check: 15 of 2,374 events have a zero gap to the next) get duration 0 for the first of the pair, so a duration-weighted sum is still right but a "duration > 0" filter drops them. `session_time_s` is DOUBLE, so the key relies on exact float equality; Bronze duplicates are exact copies. Comment at lines 42-43 ("corrects the stale comment in stg_laps") is itself stale (stg_laps is already correct). SOUND.
5. Fills: `ELSE 'unknown'` (51), a label.
6. Tests: id not_null+unique; `status_label` accepted_values; unique_combination (race_year, race_id, session_time_s, status_code) (schema.yml 1049-1111). The decode is also covered indirectly by assert_track_status_flag_partition. Shape plus decode.

## stg_circuit_info  (view) - SOUND

1. Purpose: FastF1 corner geometry per race (corner number, letter, x, y, angle, distance).
2. Flow: reads `source('bronze_f1','raw_circuit_info')`. Read by in-group dim_corners; test assert_corner_window_geometry.
3. How it works: rename and cast; `corner_id` = race_id_number+letter; ordered by year, race, distance.
4. Maths check: no arithmetic. `corner_distance_m` is passed as given. The final `ORDER BY` in a view does nothing for consumers. SOUND.
5. Fills: line 17 `COALESCE(letter,'')` in the key only; line 27 NULLIF maps '' back to NULL.
6. Tests: corner_id not_null+unique; race_id relationships (schema.yml 1290-1336). Shape only (maths of geometry is tested in assert_corner_window_geometry).

## stg_telemetry  (view) - SOUND

1. Purpose: car telemetry samples (all channels) with a plausible-distance filter and DRS decode.
2. Flow: reads `source('bronze_f1','raw_telemetry')` and an inline circuit-bound table. Read by int_lap_telemetry_aggregates, int_corner_metrics; test assert_stg_telemetry_distance_bound.
3. How it works: keep rows with `0 < distance_m < bound`. Bound = `GREATEST(6500, CEIL(lap_length*1.10))` for four long circuits (Spa 7705, Las Vegas 6822, Saudi 6792, Baku 6604), else 6500 (32-43, 95-98). `session_time_s` = ns/1e9. DRS 10/12/14 = open, 8 = eligible, 0/1 = off, other = unknown.
4. Maths check: unit conversion right. The LEFT JOIN is on a unique slug so no fan-out. `distance_m > 0` removes stationary zero-distance samples; `< bound` is strict. The four hard-coded lengths duplicate `circuit_reference.lap_length_km` (seed values match: 7.004, 6.201, 6.174, 6.003); a fifth long circuit needs a manual row, which assert_stg_telemetry_distance_bound polices. `telemetry_id` is per lap, not per sample (documented as non-unique). SOUND.
5. Fills: line 98 `COALESCE(circuit_bound.max_distance_m, 6500.0)`: circuits not in the list use the 6500 m cap, so a lap longer than 6500 m at an unlisted circuit is dropped, not defaulted. Line 35 `GREATEST(6500.0, ...)` floor.
6. Tests: not_null on key columns, relationships, `session_time_s` not_null, unique_combination (race_year, race_id, driver_id, lap_number, session_time_s) (schema.yml 339-427). assert_stg_telemetry_distance_bound checks the bound logic. Good coverage of the ordering claim in the header.

## stg_telemetry_position  (view) - SOUND

1. Purpose: the position-channel ('pos') telemetry samples with relative distance, X/Y, FastF1's driver-ahead fields, DRS state.
2. Flow: reads `source('bronze_f1','raw_telemetry')` filtered to `source = 'pos'`. Read by int_microsector_corner_class, int_microsector_crossings, int_lap_proximity; test assert_proximity_crossing_total_order.
3. How it works: rename, ns to s, clamp `relative_distance` to [0, 0.999999] (53-55), TRIM/NULLIF the driver-ahead number. Rows with NULL relativedistance dropped.
4. Maths check: clamping, not filtering, is deliberate (comment 49-52); only floating-point dust at -3e-6 and 1.0000004 is affected, so values near the start/finish line become exactly 0 or 0.999999, which can create ties at the boundary bin. The unique_combination test on session_time_s keeps ordering well-defined. No unfiltered distance cap, by design (15-28). SOUND.
5. Fills: none beyond the clamp (LEAST/GREATEST at 53-55) and `NULLIF(TRIM(...), '')`.
6. Tests: not_null on keys, relationships, unique_combination (schema.yml 891-985). assert_proximity_crossing_total_order is a logic test downstream. Shape plus ordering.

## stg_jolpica_pit_stops  (view) - SOUND (untested)

1. Purpose: Jolpica pit stops, one per stop, as an independent measurement for cross-checking stg_pits.
2. Flow: reads `source('bronze_jolpica','raw_jolpica_pit_stops')`. Read only by fct_pit_stop_crosscheck.
3. How it works: rename, cast, `race_id` = season_round.
4. Maths check: `duration_s` taken as given (Jolpica's pit-lane time in seconds; no conversion). `race_id = 'YYYY_R'` must equal the FastF1 event id in other models; `round` equals FastF1 id only if every round ran (relies on the seed convention). No arithmetic. SOUND.
5. Fills: none.
6. Tests: NONE. No entry in staging/schema.yml and the Jolpica source has no tests. Cross-check model downstream is its only consumer.

## stg_events  (view) - SOUND

1. Purpose: race-level events (damage, retirements, penalties) from a manual seed.
2. Flow: reads `ref('raw_dim_events')`. No `ref()` consumers in transform.
3. How it works: rename; `'manual' AS source`; severity cast to DOUBLE.
4. Maths check: no arithmetic. `driver_id` can be 'ALL' (documented). SOUND. Unused in the transform tree.
5. Fills: constant `'manual'` (17) is a label.
6. Tests: stg_event_id not_null+unique; race_id and driver_id relationships (driver 'ALL' excluded) (schema.yml 751-800). Shape only.

## stg_tyre_allocations  (view) - SOUND (data provenance caveat)

1. Purpose: absolute compound code (C1-C5) per race per hard/medium/soft label, from a seed.
2. Flow: reads `ref('tyre_allocations')`. Read by int_stint_geometry; test assert_tyre_allocations_rows_per_season.
3. How it works: unpivot wide seed (hard/medium/soft) into three rows via `UNION ALL`; `allocated_sets_per_driver` is `CAST(NULL AS INTEGER)` by construction.
4. Maths check: no arithmetic; unique grain (race_year, circuit_key, compound_label). `circuit_key` here is an event slug (as in the seed), unlike stg_laps whose `circuit_key` column equals race_id; a naming trap, not an error. Provenance: header says values are user-supplied and unverified (47 of 128 URLs resolve; 2025 carried forward). That is a data-trust caveat, not a code defect. SOUND.
5. Fills: NULL constant for `allocated_sets_per_driver` (66). 2025 values carried forward from 2023/2024 (data, in seed).
6. Tests: not_null on keys, circuit_key relationship to dim_circuits, compound_code accepted C1-C5 and relationship to compound_hardness_scale, label accepted_values, unique_combination (schema.yml 1338-1414); assert_tyre_allocations_rows_per_season pins counts. Shape and counts, no verification of values.

---

# REFERENCE

## dim_circuits  (table) - SOUND

1. Purpose: typed lift of the `circuit_reference` seed (lap length, corners, lateral g, penalty factors) plus `circuit_id` physical-venue key.
2. Flow: reads `ref('circuit_reference')`. Read by in-group dim_corners; by mart_race_driver_summary, mart_race_coverage, mart_degradation_history_envelope, fct_driver_skill_features, fct_cliff_prediction_features, int_power_law_lap, int_pit_loss_circuit, int_lap_fuel_state; tests assert_fuel_load_matches_scheduled_distance, assert_pit_loss_excludes_neutralised, assert_dim_circuits_calibration_flag_matches_seed, assert_race_to_track_covers_all_races.
3. How it works: CASTs only, plus `circuit_id_from_name(circuit_name)` which slugifies the name (lowercase, non-alphanumerics to `_`, trimmed).
4. Maths check: no arithmetic. `circuit_key` has no duplicates in the seed (checked with `uniq -d`). Two keys at the same venue share a `circuit_id` (intended). Values are seed data, so numeric correctness is not testable here. SOUND.
5. Fills: none.
6. Tests: circuit_key not_null+unique; `circuit_id` not_null; a dbt_expectations range on one column (min 2, max 8, likely abrasiveness) (schema.yml 4-82); assert_dim_circuits_calibration_flag_matches_seed. Shape and one range check.

## dim_compounds_season  (table) - SOUND

1. Purpose: typed lift of the frozen `compound_cliff_params` fits (cliff onset laps, wear gradient, grip peak, temp window) by circuit x compound x season.
2. Flow: reads `ref('compound_cliff_params')`. Read by fct_cliff_prediction_features, int_compound_cliff_predicted, int_pit_strategy_cost_curve, int_constructor_deg_sensitivity, int_lap_residual_decomposed_qualifying; test assert_compound_params_cover_mart; and the relationships tests on stg_laps.compound.
3. How it works: CASTs only.
4. Maths check: no arithmetic. Provenance columns say which parameter is fitted vs class default; for example the seed shows a 2019 Abu Dhabi HARD cell with `class_default` for all parameters (0 stints). Consumers must read `*_source`. Grip peak and temp window are class constants in every row (documented). SOUND as a pass-through.
5. Fills: values filled at fit time (class defaults, cross-season fallback) are in the seed, not this model; they are labelled in `fit_source/onset_source/gradient_source/severity_source`.
6. Tests: not_null on keys and provenance, accepted_values on the three source columns, unique_combination (circuit_key, compound_code, season) (schema.yml 84-175); assert_compound_params_cover_mart. Shape plus coverage.

## dim_constructors  (table) - QUESTIONABLE

1. Purpose: team list with power-unit family and rename-lineage id.
2. Flow: hard-coded VALUES, no upstream. Read by fct_lap_residuals, fct_driver_skill_features; relationships tests on stg_laps, stg_laps_qualifying, stg_results, stg_results_qualifying; test assert_pu_family_coverage.
3. How it works: 19 hand-written rows (constructor_id, pu_family, lineage). Renames map to the same lineage (Force India / Racing Point / Aston Martin etc.).
4. Maths check: no arithmetic. `pu_family` is one value per team name, not per season (header line 11). On facts from outside the repo (not checkable here): McLaren 2018-2020 used Renault power but is listed `mercedes_pu` (line 32); Red Bull Racing 2018 used Renault but is listed `honda_pu` (line 30). The header says no pace index or model reads `pu_family`, though it is carried onto fct_lap_residuals and fct_driver_skill_features, so any future use would mislabel those seasons. QUESTIONABLE, dim_constructors.sql:30, 32. Aston Martin listed `mercedes_pu` is true for 2021-2025 (2026 is set aside). A new FastF1 team name fails the stg_laps relationships test, the stated safety net.
5. Fills: none (all constants are the data).
6. Tests: constructor_id not_null+unique, other columns not_null; assert_pu_family_coverage (schema.yml 199-226). Shape and coverage; nothing checks the PU values.

## dim_corners  (table) - SOUND

1. Purpose: telemetry corner windows per race, from FastF1's corner table, for the corner-skill chain.
2. Flow: reads `ref('stg_laps')` (race list), `ref('race_to_track')`, `ref('stg_circuit_info')`, `ref('dim_circuits')`. Read by int_corner_metrics, int_microsector_corner_class; test assert_corner_window_geometry.
3. How it works: every race in stg_laps gets a geometry session: its own corner table, else the nearest season at the same slug (79-114). Window = apex minus 250 m to apex plus 150 m, each end clipped at the neighbouring apex, start floored at 0 (152-163). Each corner's window is independent so neighbouring windows may overlap.
4. Maths check:
   - Fan-out: `candidates` joins on `race_id = g.race_id OR track_id = g.race_slug`, which multiplies rows, but `ROW_NUMBER() ... candidate_rank = 1` reduces to one per race (89-113). Ties on (own session, year gap, year) would pick arbitrarily; a tie needs two corner tables for the same slug and year, not seen as a pattern. The final `LEFT JOIN dim_circuits ON track_id = circuit_key` is safe because `circuit_key` is unique in dim_circuits. SOUND.
   - Window arithmetic: `GREATEST(apex - 250, prev_apex, 0)` and `LEAST(apex + 150, next_apex)`. The start is clipped at the previous apex (a corner never reaches into the previous apex), the end at the next apex. Consistent. Last corner has no next apex so end = apex + 150. First corner has no previous apex so `COALESCE(prev,0)` and start = max(apex-250, 0). SOUND.
   - Borrowed geometry: `nearest_season` windows assume the distance origin did not move between seasons; the header flags this risk and `geometry_source` records it. Design caveat, not an error.
   - Races with no laps (the 2018 Italian GP race, HD15 B) produce no rows because the race list comes from stg_laps.
5. Fills: 62 `COALESCE(corner_letter,'')` in the name; 126 `COALESCE(res.track_id, res.race_slug)` (a race missing from race_to_track uses the geometry slug); 154 `COALESCE(prev_apex_m, 0)`; 159-162 `COALESCE(next_apex_m, apex + exit_margin)`. Boundary conventions, no hidden number.
6. Tests: key columns not_null, corner_key unique, `geometry_source` accepted_values (schema.yml 228-310). assert_corner_window_geometry (five checks: apex inside window, inside neighbours, margins respected, counts match stg_circuit_info, no cross-venue geometry) tests the maths. Good.

## dim_driver_seasons  (table) - SOUND

1. Purpose: one row per season x driver code with DriverId, names, and the team most used that season.
2. Flow: reads `source('bronze_f1','raw_results')` directly (not stg_results). No `ref()` consumers in transform.
3. How it works: GROUP BY season, abbreviation; `MIN(driverid)`, `MIN(fullname)` etc., `MODE(teamname)`.
4. Maths check: no arithmetic. `MIN(driverid)` is safe only because assert_dim_driver_seasons_single_driver_id enforces one id per group. `MODE(teamname)` is arbitrary on a tie (a driver with two teams for exactly equal race counts); display field only. SOUND.
5. Fills: none; `WHERE abbreviation IS NOT NULL` filter.
6. Tests: not_null on key columns, unique_combination (season, driver_code) (schema.yml 311-347), assert_dim_driver_seasons_single_driver_id. Shape plus one logic guard.

## dim_drivers  (table) - QUESTIONABLE

1. Purpose: one row per driver code with latest car number, first season seen and races in the dataset.
2. Flow: reads `ref('stg_laps')`. Read by fct_lap_residuals, fct_driver_skill_features, and relationships tests on stg_laps, stg_laps_qualifying, stg_sector_times, stg_pits, stg_weather, stg_telemetry, stg_telemetry_position, stg_results, stg_results_qualifying, stg_race_control, stg_events.
3. How it works: count distinct races per (driver, number, constructor, year); `ARG_MAX(driver_number, (race_year, races_in_season))` picks the latest number; `MIN(race_year)` is `debut_year`; `SUM(races_in_season)` is `career_races_in_dataset`.
4. Maths check:
   - `debut_year` is the first season present in this dataset, so every driver active in 2018 reads 2018 whatever their real debut. Column name suggests a real debut. QUESTIONABLE (naming/meaning), dim_drivers.sql:31. `career_races_in_dataset` is correctly named.
   - `SUM(races_in_season)` is over (number, constructor) groups. A driver who races for two constructors in a season still adds each race once (a race belongs to one group), so no double count unless Bronze puts one driver under two teams in the same race. Not checked.
   - `ARG_MAX` struct order picks latest year then most races; a tie across two numbers with equal counts is arbitrary. Minor.
5. Fills: none.
6. Tests: driver_id not_null+unique (schema.yml 177-198). It is also the target of many relationships tests, which is its main test value (any driver code in laps missing here fails). Shape only; no test on `debut_year` or counts.

---

# Findings list (WRONG first, then QUESTIONABLE)

WRONG
1. stg_lap_tyre_qa.sql:159 `first_stint_number - 1` yields stint 0 where Bronze's first stint is 1 and the car pitted in the lap-1 gap. Bronze check: 3 driver-races (2018_5 HAR, 2018_5 SIR, 2018_13 VER). `qa_stint_number` is then 0 in a 1-based column; it is served only if the verdict is 'ok'. I did not run the model to see which verdict they get. No test asserts `stint_number >= 1`.

QUESTIONABLE
1. stg_results.sql:74-78, 84. `is_dnf` is FALSE and `dnf_cause` NULL for retirements that were still classified (about 69 in Bronze: Retired 36, Collision, Engine, ...). Understates retirements for a DNF hazard model if "DNF" means "did not finish".
2. stg_results.sql:74-78, 92-94. 'Did not start' (17) and 'Withdrew' rows are `is_dnf = TRUE`, cause 'non_classified'; a non-starter is not a retirement.
3. stg_results.sql:95. `ELSE 'mechanical'` labels every unmatched status, including the generic 'Retired' (202 unclassified rows, the largest status), as mechanical.
4. stg_pits.sql:37 (flows to 87, 99). Compound is only upper-cased; Bronze 'NAN' / 'NONE' / 'UNKNOWN' strings survive into `compound_in` / `compound_out`, unlike stg_laps which maps them to NULL.
5. stg_laps.sql:135-153 and stg_laps_qualifying.sql:158-164. `is_valid_lap` is NULL (not FALSE) when `lap_time_s` or `is_accurate` is NULL (909 untimed Bronze laps); `NOT is_valid_lap` filters miss them. No not_null test on the column.
6. dim_constructors.sql:30, 32. `pu_family` is one value per team name: McLaren (2018-2020) and Red Bull (2018) used Renault but are `mercedes_pu` / `honda_pu`. Carried onto two marts although no model reads it.
7. dim_drivers.sql:31. `debut_year` is the first season in the dataset (2018 for all veterans), not a debut year.
8. stg_lap_tyre_qa.sql:190-194, 426-429. Every lap of a repaired driver-race (including later, un-offset stints) is labelled `'bronze_lap1_repaired'` because `tyre_life_offset_laps` is a per-driver-race constant. Metadata only.
9. stg_lap_tyre_qa.sql:203-205, 389-399. Stint-ordinal windows use row order, not `lap_number`; a missing lap row would shift the pit ordinal in quarantined units.
10. Documentation staleness (no number affected): staging/schema.yml stg_pits "5,336 stops across 2018-2024" and stg_weather "2018-2024"; stg_track_status.sql:42-43 comment about a stale stg_laps comment; stg_sector_times.sql:2 "3 rows per lap".

Models with no tests at all: stg_jolpica_pit_stops (no model entry, no source tests).
Unused (no ref() consumer in transform): stg_session_status, stg_events, dim_driver_seasons.

## Could not check
- Model output: I did not run dbt, so the verdict of the three stint-0 driver-races, the exact count of stg_pits NAN compounds, and row counts of any model are unverified.
- Whether `race_to_track` and `circuit_reference` seed values are right (data, not model logic).
- pu_family facts rely on outside knowledge of F1 engine suppliers, not repo data.
- Seed content of `raw_dim_events`, `compound_cliff_params`, `tyre_allocations` was read only for headers and a few rows.
