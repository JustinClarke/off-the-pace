{{ config(tags=['intermediate']) }}

-- Field pace honest range test: field_pace_smoothed_s / race_fastest_lap_s
-- should be between 0.920 and 1.070 for normal dry, non-SC races/laps.
--
-- Floor moved 0.945 -> 0.920 in WI-01's verification pass (2026-09-27, ruled).
-- Measured on the post-pass build (unknown-tyre laps out of the base, theta
-- re-fit): min 0.9471, p0.1 0.9541, p1 0.9718, p50 1.0115, max 1.0678, 0 of
-- 7,643 checked laps below either floor. 0.945 had been set just under the
-- observed minimum, and the minimum is set by the tyre model: the base is
-- corrected by expected_compound_pace_s, whose wear term is capped at
-- var('compound_wear_max_s_per_lap') = 10 s (337 laps, 0.21%, sit on the cap).
-- Note 0.920 is LOWER than 0.945, so this floor now catches fewer bases than
-- before, not more: it stops the bound being walked down to the minimum on
-- every rebuild, and whether the tyre cap binds too often is tracked on the
-- fixes board's watch list, not by this test.
--
-- Range widened by WI-01 (2026-09-27): field_pace_smoothed_s is now built from
-- fuel- AND compound-corrected lap times (F38), not fuel-corrected alone, so a
-- high-wear lap's base sits further below the race's raw fastest lap than it
-- used to (compound cost, typically positive and growing through a stint, is
-- now subtracted out of the base itself). Measured on the 2026-09-27 dev
-- build over the same dry/non-SC/non-low-sample population this test uses:
-- min 0.9488, p0.1 0.9544, p50 1.0117, p99.9 1.0618, max 1.0678 (previously
-- 0.990-1.055 against a fuel-only-corrected base, p99 ~1.047).
-- Lower bound: early laps where fastest lap (lap 1-3) is faster than rolling smoothed mean,
-- now compounded by the compound correction pulling worn-tyre laps' base down further.
-- Upper bound: p99.9 of real data is 1.0618; 1.070 gives headroom without catching normal spread.
WITH race_fastest AS (
    SELECT 
        race_year, 
        race_id, 
        MIN(lap_time_s) AS race_fastest_lap_s
    FROM {{ ref('stg_laps') }}
    WHERE is_valid_lap = TRUE
    GROUP BY race_year, race_id
),

wet_races AS (
    SELECT DISTINCT race_year, race_id
    FROM {{ ref('stg_weather') }}
    WHERE rainfall_flag = TRUE
),

sc_laps AS (
    SELECT DISTINCT race_year, race_id, lap_number
    FROM {{ ref('stg_laps') }}
    WHERE is_safety_car_lap = TRUE OR is_vsc_lap = TRUE
)

SELECT
    f.race_year,
    f.race_id,
    f.lap_number,
    f.field_pace_smoothed_s,
    rf.race_fastest_lap_s,
    f.field_pace_smoothed_s / rf.race_fastest_lap_s AS pace_ratio
FROM {{ ref('int_field_pace_curve') }} f
JOIN race_fastest rf USING (race_year, race_id)
LEFT JOIN wet_races w USING (race_year, race_id)
LEFT JOIN sc_laps sc USING (race_year, race_id, lap_number)
WHERE w.race_id IS NULL             -- exclude wet races
  AND sc.lap_number IS NULL         -- exclude SC/VSC laps
  AND f.low_sample_flag = FALSE     -- exclude low sample laps
  AND (
      f.field_pace_smoothed_s / rf.race_fastest_lap_s < 0.920
      OR f.field_pace_smoothed_s / rf.race_fastest_lap_s > 1.070
  )
