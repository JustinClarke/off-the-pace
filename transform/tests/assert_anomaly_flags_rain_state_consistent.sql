-- int_lap_anomaly_flags carries rain_state from int_track_evolution. Missing
-- weather must stay visible and must not be read as dry or wet:
--   * rain_state is one of DRY / WET / NO_WEATHER, never NULL.
--   * NO_WEATHER laps have rainfall_flag NULL, is_rain_lap FALSE (the two-valued
--     "not known wet" flag, kept so training eligibility is unchanged) and are
--     never anomaly_class 'conditions' (that class is set only by rainfall).
--   * WET is exactly is_rain_lap = TRUE; DRY has rainfall_flag = FALSE.
-- NO_WEATHER laps remain trainable by owner decision, so this test asserts no
-- count and no usable_for_modelling value. Returns offending rows; passes when empty.
-- rainfall_flag is not an output column of int_lap_anomaly_flags (it is folded
-- into is_rain_lap), so it is read from the model it is carried from.
SELECT
    f.lap_id,
    f.race_year,
    f.race_id,
    f.rain_state,
    r.rainfall_flag,
    f.is_rain_lap,
    f.anomaly_class
FROM {{ ref('int_lap_anomaly_flags') }} AS f
LEFT JOIN {{ ref('int_lap_residual_decomposed') }} AS r
    ON f.lap_id = r.lap_id
WHERE
    f.rain_state IS NULL
    OR f.rain_state NOT IN ('DRY', 'WET', 'NO_WEATHER')
    OR (f.rain_state = 'NO_WEATHER' AND (r.rainfall_flag IS NOT NULL OR f.is_rain_lap OR f.anomaly_class = 'conditions'))
    OR (f.rain_state = 'WET' AND NOT f.is_rain_lap)
    OR (f.rain_state <> 'WET' AND f.is_rain_lap)
    OR (f.rain_state = 'DRY' AND r.rainfall_flag IS DISTINCT FROM FALSE)
