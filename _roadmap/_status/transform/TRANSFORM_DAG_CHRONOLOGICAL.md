# Transform DAG - Chronological Execution Order

## Overview
60 dbt models executed in dependency order. Each line shows execution sequence, dependencies, and potential breakage points.

---

## Stage 1: STAGING (12 models) — Raw Data Cleanup

```
 1. stg_circuit_info              ← raw_circuit_info
 2. stg_tyre_allocations          ← (source)
 3. stg_laps                       ← raw_laps
 4. stg_results                    ← raw_results
 5. stg_pits                       ← raw_laps
 6. stg_session_status            ← raw_session_status
 7. stg_telemetry                  ← raw_telemetry
 8. stg_track_status              ← raw_track_status
 9. stg_laps_qualifying           ← raw_laps_qualifying
10. stg_events                     ← raw_dim_events
11. dim_events                     ← raw_dim_events
```

### Breakage Points
- **stg_laps**: If raw_laps has missing columns or wrong types, all downstream deps fail
- **stg_tyre_allocations**: Manual source—if not maintained, no compound labels
- **stg_telemetry**: Large table—if import fails, corner metrics break

---

## Stage 2: DIMENSIONS & REFERENCES (5 models) — Lookup Tables

```
12. int_constructor_car_fe        ← constructor_car_fe (seed)
13. dim_compounds_season          ← compound_cliff_params (seed)
14. dim_circuits                  ← circuit_reference (seed)
15. dim_constructors              ← stg_laps
16. dim_drivers                   ← stg_laps
```

### Breakage Points
- **int_constructor_car_fe**: If seed missing, constructor pace calculations break
- **dim_compounds_season**: Cliff params seed—if outdated, cliff predictions wrong
- **dim_circuits, dim_drivers**: Extract from stg_laps—if deduplication logic wrong, missing rows

---

## Stage 3: STINT-LEVEL FEATURES (5 models) — Fuel & Tyre State

```
17. int_event_corrections         ← stg_laps, seed_manual_lap_exceptions
18. int_stint_geometry            ← stg_laps
19. stg_sector_times              ← stg_laps
20. stg_weather                   ← raw_weather, stg_laps
21. int_corner_metrics            ← stg_telemetry, race_to_track +1
```

### Breakage Points
- **int_stint_geometry**: Stint ID sequencing—if lap-to-stint mapping wrong, all stint features downstream are wrong
- **int_event_corrections**: Manual exceptions seed—if stale, corrupted laps not filtered
- **int_corner_metrics**: Requires telemetry + race_to_track mapping—if mapping wrong, lap-corner alignment breaks

---

## Stage 4: PHYSICS MODELING (8 models) — Fuel, Cliff, Aero, Thermal

```
22. int_pit_loss_circuit          ← stg_track_status, stg_results +2
23. int_sc_hazard_history         ← stg_track_status, stg_laps
24. int_constructor_structural_pace_qualifying ← stg_laps_qualifying
25. int_lap_fuel_state_qualifying ← stg_laps_qualifying
26. int_lap_air_state             ← raw_telemetry, int_stint_geometry
27. int_lap_fuel_state            ← int_stint_geometry, stg_laps +2
28. int_lap_thermal_proxy         ← int_stint_geometry, stg_laps
29. int_compound_cliff_predicted   ← int_stint_geometry, race_to_track +2
```

### Breakage Points
- **int_lap_fuel_state**: Fuel curve fitting—if polynomial wrong order, degradation all scaled wrong
- **int_compound_cliff_predicted**: Cliff onset model—if parameters outdated (seed), cliff detection completely wrong
- **int_lap_air_state**: Air state from telemetry—if DRS detection wrong, dirty air tax cascades wrong
- **int_lap_thermal_proxy**: Temperature proxy—if formula wrong, thermal penalty misapplied

---

## Stage 5: DRIVER SKILL DECOMPOSITION (6 models) — Core 7-Term Identity

```
30. fct_telemetry_deltas          ← int_corner_metrics, stg_laps
31. int_corner_skill_residuals    ← int_corner_metrics, int_stint_geometry +2
32. int_field_pace_curve          ← int_lap_fuel_state, int_stint_geometry +1
33. int_pit_strategy_value        ← int_stint_geometry, int_compound_cliff_predicted +4
34. int_synthetic_teammate        ← int_lap_fuel_state, int_stint_geometry +2
35. int_track_evolution           ← int_field_pace_curve, stg_weather
```

### Breakage Points
- **int_field_pace_curve**: Base pace per circuit—if interpolation logic wrong, all normalized pace wrong
- **int_track_evolution**: Tire deg over race—if formula wrong, track surface aging misrepresented
- **int_synthetic_teammate**: Synthetic opponent for comparison—if seed/generation wrong, counterfactual features wrong

---

## Stage 6: CONSTRUCTOR & MULTI-DRIVER MODELS (4 models)

```
36. int_constructor_structural_pace ← int_lap_fuel_state, int_field_pace_curve +4
37. int_dirty_air_tax_component   ← int_lap_fuel_state, int_field_pace_curve +4
38. int_driver_race_skill_loro    ← int_lap_fuel_state, int_field_pace_curve +5
39. int_lap_residual_decomposed_qualifying ← stg_laps_qualifying, int_lap_fuel_state_qualifying +4
```

### Breakage Points
- **int_driver_race_skill_loro**: LORO (Least-Outliers Regression)—if shrinkage threshold wrong, ratings collapse
- **int_constructor_structural_pace**: De-biased constructor pace—if HDFE subtraction wrong, constructor skill absorbed into driver
- **int_dirty_air_tax_component**: Aerodynamic penalty per position—if not monotonic increasing by deficit, invalid physics

---

## Stage 7: DIMENSION AGGREGATIONS (7 models) — Race→Season

```
40. mart_corner_skill_driver      ← stg_laps, int_event_corrections +2
41. int_circuit_x_constructor_interaction ← int_constructor_structural_pace, race_to_track
42. int_driver_circuit_affinity   ← int_driver_race_skill_loro
43. int_driver_circuit_era_affinity ← circuit_reference, int_driver_race_skill_loro
44. int_driver_season_ratings     ← int_driver_race_skill_loro
45. int_lap_residual_decomposed   ← int_field_pace_curve, int_lap_fuel_state +8
46. int_era_normalized_driver_rating ← int_driver_season_ratings
```

### Breakage Points
- **int_driver_season_ratings**: Aggregates race→season—if shrinkage wrong (min-races threshold), low-sample drivers rated unreliably
- **int_driver_circuit_affinity**: Per-circuit ratings—if grouping loses interaction, double-count caveat applies
- **int_lap_residual_decomposed**: CORE decomposition (7-term identity)—if any component missing or formula wrong, waterfall breaks

---

## Stage 8: FACT TABLES & FEATURE ENGINEERING (6 models) — ML & Analysis

```
47. int_constructor_deg_sensitivity ← int_lap_residual_decomposed, int_compound_cliff_predicted +1
48. int_lap_anomaly_flags         ← int_lap_residual_decomposed
49. int_lap_residual_stint_detrend ← int_lap_residual_decomposed
50. int_qualifying_decomposed     ← int_lap_residual_decomposed_qualifying, int_lap_residual_decomposed
51. int_sector_residual_decomposed ← stg_sector_times, stg_laps +2
52. int_tyre_surface_vs_bulk_decoupling ← int_lap_thermal_proxy, int_lap_residual_decomposed
```

### Breakage Points
- **int_lap_anomaly_flags**: Outlier detection—if thresholds too loose/aggressive, impacts all downstream filtering
- **int_lap_residual_stint_detrend**: De-trends stint-level effects—if slope wrong direction, degradation trends inverted
- **int_sector_residual_decomposed**: Sector-level 7-term—if mapping wrong, sector decomposition scatter

---

## Stage 9: FINAL EXPORTS (5 models) — App & ML

```
53. mart_degradation_history_envelope ← degradation_isotonic (seed), int_lap_residual_decomposed +2
54. fct_ghost_car_pace            ← int_lap_residual_decomposed, int_compound_cliff_predicted +4
55. fct_driver_skill_features     ← int_lap_residual_decomposed, int_lap_anomaly_flags +6
56. fct_stint_features            ← int_stint_geometry, stg_laps +5
57. int_lap_telemetry_aggregates  ← stg_telemetry, int_lap_anomaly_flags
```

### Breakage Points
- **fct_ghost_car_pace**: Recombination of driver skill + fuel envelope—if interpolation endpoints wrong, ghost pace invalid for end-of-race
- **fct_stint_features**: ML input table—if feature scaling wrong or missing values not coalesced, inference fails
- **mart_degradation_history_envelope**: Exported to app—if envelope bounds wrong, simulator shows implausible bounds

---

## Stage 10: ML & RACE-LEVEL (2 models) — Final Outputs

```
58. fct_ghost_race_finish         ← fct_ghost_car_pace, stg_laps +1
59. fct_cliff_prediction_features ← int_lap_residual_decomposed, int_lap_anomaly_flags +9
```

### Breakage Points
- **fct_ghost_race_finish**: DNF flag source—if crash vs retire vs fuel logic wrong, ghost race finish order wrong
- **fct_cliff_prediction_features**: ML training table—if target (cliff binary) mislabeled or features scaled inconsistently, model trained on noise

---

## Critical Validation Gates

### 1. 7-Term Identity (fct_lap_residuals)
```sql
SELECT lap_id,
  pace_delta,
  (component1 + component2 + ... + component6 + driver_skill) as reconstructed,
  ABS(pace_delta - reconstructed) as error
FROM fct_lap_residuals
WHERE error > 0.5
LIMIT 10;
-- Must return 0 rows. If not, decomposition identity broken.
```

### 2. Fuel Curve Monotonicity (int_lap_fuel_state)
```sql
SELECT driver_id, stint_id, 
  ROW_NUMBER() OVER (PARTITION BY driver_id, stint_id ORDER BY fuel_remaining_kg) as rank,
  lap_time_ms
FROM int_lap_fuel_state
-- Lap time MUST decrease as fuel decreases (negative relationship)
-- If any stint shows increasing lap time w/ fuel drop, outlier or formula wrong
```

### 3. Cliff Onset Monotonicity (int_compound_cliff_predicted)
```sql
SELECT compound, constructor_id, 
  tyre_age, cliff_probability
FROM int_compound_cliff_predicted
-- Cliff prob MUST increase monotonically w/ tyre age
-- If cliff_prob decreases or non-smooth, onset model params wrong
```

### 4. LORO Weights Sanity (int_driver_race_skill_loro)
```sql
SELECT driver_id, season, skill_estimate, shrinkage_weight
FROM int_driver_race_skill_loro
WHERE shrinkage_weight < 0.1 OR shrinkage_weight > 1.0
-- Weights must be (0, 1]. Outside = error in shrinkage calculation
```

### 5. Affinity Min-Races Threshold (int_driver_circuit_era_affinity)
```sql
SELECT driver_id, circuit_id, era, races_at_circuit, affinity
FROM int_driver_circuit_era_affinity
WHERE races_at_circuit < 2 AND affinity IS NOT NULL
-- If races < 2, affinity MUST be NULL (shrinkage threshold not applied)
```

---

## Common Off-The-Pace Breaks

| Break | Model(s) | Symptom | Check |
|-------|----------|---------|-------|
| Fuel curve wrong | int_lap_fuel_state | Lap times increase w/ fuel | Check monotonicity (SQL above) |
| Cliff params stale | int_compound_cliff_predicted, fct_cliff_prediction_features | Cliff predictions all 0.5 or all 0 | Check seed: dim_compounds_season |
| Stint ID off-by-one | int_stint_geometry | Stint boundaries wrong | SELECT COUNT(DISTINCT stint_id) per race, confirm ≈ 3 |
| LORO collapse | int_driver_race_skill_loro | All drivers rated near average | Check shrinkage weights > 0.3 |
| Decomposition missing term | int_lap_residual_decomposed | Waterfall chart shows < 6 components | Count non-NULL columns |
| Aero penalty inverted | int_dirty_air_tax_component | Positive delta (faster in traffic) | Check sign: delta must be negative/penalty |
| Thermal wrong | int_lap_thermal_proxy | All laps show same temp | Check temp range per circuit, confirm variance > 0.1K |
| Ghost recombination off | fct_ghost_car_pace | Ghost car laps implausibly fast/slow | Check fuel envelope bounds, interpolation logic |
| Encoder stale | (ML export) | ML predictions all same value | Compare manifest.input.feature_order to training code |

---

## Commit & Export Checklist

Before committing dbt changes:
- [x] All 60 models compile without error: `dbt parse`
- [x] All 451 tests pass: `make dbt-test` (verified 2026-07-06, see `TRANSFORM_TEST_FIXES_HANDOFF.md`)
- [ ] 7-term identity validated: `dbt test assert_lap_7term_identity` (not re-run standalone this session; covered by the full 451-test pass above)
- [ ] Manifest regenerated: commit target/manifest.json
- [ ] Export script run: `python scripts/export_app_data.py`
- [ ] _manifest.json updated with new table paths

Note: this checklist was previously pre-checked aspirationally, not reflecting a real run. The
2026-07-06 handoff session found and fixed 4 real test failures before reaching 451/451 green —
see `TRANSFORM_TEST_FIXES_HANDOFF.md` for root causes. Export/manifest steps remain unchecked
since this session only fixed+verified dbt tests; it did not run the export pipeline.

---

**Last updated**: 2026-07-06
**Models**: 60 (stg: 12, int: 34, fct/mart: 14)
**Tests**: 451 dbt tests (schema + singular + assert_* invariants)



ONLY DO AT THE END IGNORE UNLESS I MENTION IT:
Not published — make app-publish is user-gated, so app/public/data/ still serves the old generation (F9/F11 skew is fix 6). Run it when you want this live.
Pre-existing docs drift: scripts/docs_facts.py still hardcodes "443 tests" (real count is now 464) — already stale since fixes 1 & 2, updated in the separate docs-publish flow, so I left it as-is.