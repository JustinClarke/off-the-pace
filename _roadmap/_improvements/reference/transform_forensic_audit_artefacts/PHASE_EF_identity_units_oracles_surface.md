# Phase E — identity, classification, units, oracles (2026-09-24)

## Identity
- §4.1 beyond the listing: stg_laps.lap_id (season+race+driver+lap) unique over 189,418 rows; lap_number
  contiguous per (race, driver) (0 violations), min 1. A second session at race depth would duplicate
  (driver, lap_number) -> would break uniqueness. Clean today. Weather/track_status/session_status/results all
  carry session=Q dirs (173 each); race models read race depth only; no model reads Q weather at all.
- race_id: race_to_track 172 rows unique; race_id -> round agrees with bronze schedule EventName 172/172.
- stg_laps.circuit_key (= race_id alias, §4.3) is read by NO model. The mart's circuit_key is race_to_track.track_id,
  an event-NAME slug recurring across seasons (36 in mart). It splits four venues: brazilian(2018-19)/são_paulo(2021+),
  mexican(2018-19)/mexico_city(2021+), austrian/styrian, british/70th_anniversary. Consumers: evaluate.py:215-230
  per-(compound, circuit_key, age_bucket) baseline (venue-intended, event-keyed); evaluate.py:1127 cohort table
  (reporting); int_sc_hazard_history (event-keyed, not in contract); seed cells (per race; fallback pools by venue
  via dim_circuits.circuit_id -- correct). 01b "every 2024 circuit hosts exactly one race": true under both readings.
- dim_events.round_number: consumed by nothing (app useRaces.ts is dead code, and queries columns season/round
  that dim_events does not have).
- raw_dim_events seed: race_id loaded INTEGER (202110) -> dim_events/stg_events.race_id '202110' never equals
  '2021_10'. Consumers: fit_compound_cliff.py:136 forced_stop_flag (always FALSE; field unused by the fit),
  export to app (unread). §4.6's feared season-shaped correction_weight bias DOES NOT EXIST: int_event_corrections
  no longer reads stg_events (not in lineage); correction_weight is data-derived (yellow/outlier/exclude/pit/
  neutralisation), downweight share 16-21% in every season. seed_manual_lap_exceptions is header-only.
- §4.4 pu_family: consumers fct_driver_skill_features, fct_lap_residuals (passthrough, exported, app never reads).
  No pace index is conditioned on it (dim_constructors header claim false). fct_driver_skill_features.sql:153-154
  constructor_power_pace_index_final and constructor_aero_pace_index_final are the SAME column.
- §4.5 driver_number: only int_lap_proximity uses a driver_number, and it takes stg_results' per-race number
  (correct). dim_drivers.driver_number unread by app/ML.
- Driver/constructor: 0 (driver, race) with >1 constructor (stg_laps and stg_results; laps agree with results).
  8 driver-seasons change team. ANY_VALUE collapses: mart_corner_skill_driver.sql:234 (7 driver-seasons get an
  arbitrary constructor), app synthetic-teammate/queries.ts:28-29 (28 driver-seasons show one arbitrary teammate
  while averaging over 2-3).
- nationality: absent (dim_drivers.sql:4 says so); nothing fabricates it.

## Classification (§5.3)
- Exactly one finish_position=1 per race (0 violations); is_classified AND is_dnf never both.
- DSQ with numeric ClassifiedPosition in bronze: HAM, LEC 2023_18; RUS 2024_14 -> stg_results is_classified TRUE,
  is_dnf FALSE, dnf_cause NULL (the other 13 DSQs are non_classified). Earliest point: bronze. Consumers:
  int_stint_end_regime, fct_ghost_race_finish.actual_is_dnf.
- Note: stg_results.sql:57-61 also excludes status 'Finished' (charter omits this). 'Lapped' (2025 status) handled by
  '%Lap%'. No other status contains 'Lap'.
- is_dnf vs final-stint stint_end_cause: False/race_end 2946, False/retirement 61 (classified retirements),
  True/retirement 428, True/race_end 12 (ran to flag, then DSQ), True/NULL 2. Agree up to definition.

## Points (§5.4)
- No dbt model computes or reads points (grep marts: 0; int hits are telemetry "points"). stg_results.points has no
  model consumer. Jolpica consumed by nothing (grep).
- App counterfactual-championship/queries.ts:34-38 recomputes points in-browser: fixed 25..1 table, no fastest-lap
  point (2019-2024), no sprint points, "Actual Pts" summed over counted races only. Methodology discloses the table.
- Oracle (phaseE_oracle_points.py): Jolpica holds FINAL-round standings only (1 round/season). FastF1 race points
  per driver-season == official for 63/63 driver-seasons 2018-2020; from 2021 differ for 5/21, 11/22, 15/22, 13/24,
  16/21 (sprints not ingested). App table == official for 20/20 (2018), 14/20 (2019) ... max gap 54 pts (2023).

## Units (§5.7)
- Every /1e9 once (staging only); min lap 55.4 s, valid max 149.5 s, quali 53.4-194.7 s. time_or_gap_s: no consumer.
  pit_duration_s: no consumer (both stg_pits consumers use lap-time loss); 0 non-positive, 388 >60 s, 248 NULL.
- age_in_stint non-decreasing in stint, lap_in_stint 1..n contiguous, age >= lap_in_stint, stint_number monotone,
  fuel >= 0 (min 1.4) and non-increasing: 0 violations each. 2018 compounds: legacy names, no C-codes.
- int_stint_geometry.compound_code NULL for ALL 2025 slicks (24,680 stint-laps): tyre_allocations seed has no 2025 ->
  dbt test assert_stint_geometry_2018_compound_code_null rule 2 FAILS. compound_code is not an ML feature.

## Oracles
- Pits (phaseE_oracle_pits*.py): every Jolpica stop matched at the same lap in 2019, 2021-2025 (100%); 2018 99.1%
  (5 unmatched, all 2018 round 2); 2020 94.6% (32 unmatched, all round 1). stg_pits has 2-5% more stops/season
  (superset). 2020_1: Jolpica pit laps = ours +5 (36 stops) / +4 (2) -> lap numbering offset in bronze for that
  race (stg max lap 68). Which source is right needs a third source.
- Race length: FastF1 results 'Laps' NULL; Jolpica laps only 2011-2017; lap_length_km-implied schedule too noisy
  (one length per slug across layout changes). No usable race-length oracle in-tree.

# Phase F — shipped surface
- app/public/models/encoders.json == ml/models/encoders.json (identical); manifest identical to ml/models/manifest.json;
  per-model feature_order present (32/32/32/39/32); dataset_fingerprint 87e1d013... equals the fingerprint the
  current warehouse produces (Phase B replica) -> v14 trained on exactly this build.
- DEFECT: manifest.input has keys {tensor_name, dtype, feature_union, per_model_feature_order, encoding}; NO
  n_features, NO feature_order. app/src/ml/featureVector.ts:57-58,67 and infer.ts:101-104 read
  manifest.input.n_features / input.feature_order -> buildFeatureVector throws TypeError (reproduced,
  phaseF_manifest_contract.mjs). And even if read, one matrix is fed to all five models (32 vs 39 wide).
  Callers: degradation-simulator/page.tsx:159 (error caught -> scoreError), ml/verifyParity.ts:137.
  featureVector.test.ts:79-80 asserts n_features 32 against the shipped manifest -> would fail. app/src/ml last
  touched 2026-08-24 (cdf2523), before v13's per-model contract (09-21).
- ghost-race-standings: reads int_driver_circuit_era_affinity + int_driver_race_skill_loro; labels eras 2018-2021 /
  2022-2024 (page.tsx:116, methodology.tsx:21); "statistical reconstruction ... not a" prediction (methodology:48).
  Honest about coverage (2025 absent because constructor_car_fe.parquet is stale). No points claims.
- counterfactual-championship: see §5.4.
