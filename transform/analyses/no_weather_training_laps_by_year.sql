-- Diagnostic (reports, never fails): how many training-eligible laps carry each
-- rain_state, per race_year. NO_WEATHER laps (no weather reading, rainfall_flag
-- NULL) stay in the training population by owner decision; this query shows how
-- many there are so that choice can be audited. Compile with
-- `dbt compile --select no_weather_training_laps_by_year` and run the SQL from
-- target/compiled/ against the warehouse; it is not a test and asserts nothing.
--
-- Eligibility = fct_cliff_prediction_features.is_training_eligible (the ML
-- training flag). usable_for_modelling (anomaly flags) is shown alongside.
SELECT
    f.race_year,
    a.rain_state,
    COUNT(*) AS n_laps,
    COUNT(*) FILTER (WHERE f.is_training_eligible) AS n_training_eligible,
    COUNT(*) FILTER (WHERE a.usable_for_modelling) AS n_usable_for_modelling,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE f.is_training_eligible)
        / NULLIF(SUM(COUNT(*) FILTER (WHERE f.is_training_eligible)) OVER (PARTITION BY f.race_year), 0),
        2
    ) AS pct_of_year_training_eligible
FROM {{ ref('fct_cliff_prediction_features') }} AS f
INNER JOIN {{ ref('int_lap_anomaly_flags') }} AS a ON f.lap_id = a.lap_id
GROUP BY f.race_year, a.rain_state
ORDER BY f.race_year, a.rain_state
