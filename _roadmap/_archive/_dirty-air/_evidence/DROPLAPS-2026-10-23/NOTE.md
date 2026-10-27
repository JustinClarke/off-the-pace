# Why 28,378 laps are missing from fct_cliff_prediction_features (2026-10-23)

Read-only trace. Counts from `app/dist/data` parquet and `data/bronze/laps` read in an in-memory DuckDB; scripts in the session scratchpad `droplaps/` (count.py, pos.py). No repo file or warehouse touched.

## Counts
- int_lap_air_state (lap-map spine): 189,418 laps. fct_cliff_prediction_features: 161,040. Missing: 28,378.
- Rebuilding `stg_laps.is_valid_lap` from bronze matches the cliff table exactly: 161,040 valid laps are all in the cliff table, 0 invalid laps are, 28,378 invalid laps are all missing.
- Missing laps by rule (a lap can trip several): IsAccurate false 26,775; SC/VSC/red TrackStatus 13,908; pit lap 11,944; lap 1 3,449 (all of them); no lap time 3,167; Deleted 1,691.
- IsAccurate is false on all 3,449 lap 1s, all 11,944 pit laps and all 13,908 neutralised laps in the missing set. Only 1,268 laps fail IsAccurate and nothing else. 1,603 missing laps are IsAccurate true (removed by Deleted / no lap time).
- First-match split (lap 1, no time, pit, deleted, not accurate, neutralised): 3,449 / 3,087 / 10,447 / 1,619 / 9,776 / 0.

## The rule (stg_laps.sql:129-138, "is_valid_lap")
    lap_time_s > 0 AND NOT is_pit_lap AND NOT is_deleted AND is_accurate
    AND NOT REGEXP_MATCHES(track_status, '.*[4567].*') AND lap_number > 1
It reaches the cliff table through `int_lap_fuel_state.sql:48` (`WHERE is_valid_lap = TRUE` in CTE `laps`) plus `:89` (`INNER JOIN laps AS l`). `int_lap_residual_decomposed.sql` has `FROM fuel AS f INNER JOIN geom` / `INNER JOIN laps_meta` (~l.317-319) and `WHERE lap_time_s IS NOT NULL` (~l.371). The fct_cliff `residuals` CTE reads int_lap_residual_decomposed and every other join is LEFT. int_compound_cliff_predicted.sql:48 has the same `WHERE is_valid_lap = TRUE` (161,040 rows). int_stint_geometry carries the full lap sequence (header lines 5-8), so the drop is not there.

## Intended?
Yes. Quotes:
- stg_laps.sql:129-131 "Valid laps: timed, on-track, not deleted, accurate, not lap 1, and no neutralisation (SC/red/VSC)".
- staging/schema.yml:9 "is_valid_lap = TRUE excludes pit laps, deleted laps, SC/VSC laps, and lap 1."
- fct_cliff_prediction_features.sql:2 "Grain: lap_id one row per valid race lap."
- intermediate/schema.yml:390-391 "lap 1 is never training-eligible"; :580 "int_lap_fuel_state carries valid laps only".
- int_stint_geometry.sql:5-8 geometry deliberately keeps "SC/VSC/pit/invalid laps" for window continuity.
I found no comment that says the lap-map and cliff tables are meant to have different row counts.

## Crossing-time gap (int_lap_proximity)
- Same spine as int_lap_air_state: `ident` reads int_stint_geometry (int_lap_proximity.sql:361-373), LEFT JOINs the scalars. One row per lap, 189,418, so no row gaps from the valid-lap rule.
- Whether the gap is non-NULL depends on position telemetry (stg_telemetry_position, Source='pos') crossings for that lap, minus pit-window crossings (`crossings_on_track`, lines 134-150), the self-match and 300 s stoppage guards. Neutralised laps get is_neutralised_lap (zeroed downstream).
- Bronze check, missing laps with any position sample: 3,398/3,449 lap 1s, 11,448/11,557 pit-lap rows, 13,139/13,372 other; with a car-ahead distance: 3,397 / 11,099 / 12,596. Kept laps: 159,440/161,040 with samples.
- Caveats: pit laps lose their pit-window bins; schema.yml:388-391 notes 139 lap-1 pit-lane starters are mis-identified as car ahead. I did not run dbt, so the actual proximity values are not checked.

## One line
The `is_valid_lap` filter (applied via the WHERE and INNER JOIN in int_lap_fuel_state), chiefly its `is_accurate` term (26,775 of 28,378; it also covers every lap 1, pit and SC/VSC lap), drops the laps; it is a deliberate, documented design choice.

To get these laps into the cliff table the valid-lap filter in int_lap_fuel_state (and int_compound_cliff_predicted) would have to change, and everything downstream that assumes valid-only rows (fct_cliff header, labels, windows) would need review.
