-- Field pace honest range test: field_pace_smoothed_s / race_fastest_lap_s
-- should be between 0.990 and 1.055 for normal dry, non-SC races/laps.
-- Lower bound: early laps where fastest lap (lap 1-3) is faster than rolling smoothed mean.
-- Upper bound: p99 of real data is 1.047; 1.055 gives headroom without catching normal spread.
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
      f.field_pace_smoothed_s / rf.race_fastest_lap_s < 0.990
      OR f.field_pace_smoothed_s / rf.race_fastest_lap_s > 1.055
  )
