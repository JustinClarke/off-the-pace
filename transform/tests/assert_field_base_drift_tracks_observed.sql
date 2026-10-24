{{ config(tags=['intermediate'], severity='error') }}
-- CO-15 (ruling CD9). Loud companion to assert_field_pace_honest_range: names the
-- CAUSE, not the symptom. Per dry race, the wear term the field base subtracts
-- (int_compound_cliff_predicted.compound_wear_s) must not drift through the race
-- by more than 7 s beyond what the field's weight-corrected laps actually did.
-- Drift = median over laps in the last quarter of the race minus median over
-- laps 3 .. first quarter. A race with any rainfall is skipped (its observed
-- drift is weather, not tyres).
--
-- Probe, 2026-10-22, dev build: without the wear hold 2024_8 excess 10.25 s
-- (fails); next 2020_4 6.89, 2024_5 5.64, 2021_3 5.24. With the hold: max
-- 6.54 (2020_4, an in-range gradient, watch item W8), 2024_8 4.59, p99 4.61
-- over 149 dry races.
WITH nl AS (
    SELECT race_id, MAX(lap_number) AS n
    FROM {{ ref('stg_laps') }}
    WHERE is_valid_lap
    GROUP BY race_id
),

wet AS (
    SELECT DISTINCT race_id
    FROM {{ ref('stg_weather') }}
    WHERE rainfall_flag
),

l AS (
    SELECT
        f.race_id,
        f.lap_number,
        nl.n,
        f.weight_corrected_lap_time AS wc,
        c.compound_wear_s AS wear
    FROM {{ ref('int_lap_fuel_state') }} AS f
    INNER JOIN {{ ref('int_compound_cliff_predicted') }} AS c
        ON f.lap_id = c.lap_id
    INNER JOIN nl
        ON f.race_id = nl.race_id
    WHERE c.compound_wear_s IS NOT NULL
      AND f.race_id NOT IN (SELECT race_id FROM wet)
),

d AS (
    SELECT
        race_id,
        MEDIAN(wear) FILTER (WHERE lap_number >= n * 0.75)
        - MEDIAN(wear) FILTER (WHERE lap_number BETWEEN 3 AND n * 0.25)
            AS wear_drift_s,
        MEDIAN(wc) FILTER (WHERE lap_number >= n * 0.75)
        - MEDIAN(wc) FILTER (WHERE lap_number BETWEEN 3 AND n * 0.25)
            AS observed_drift_s
    FROM l
    GROUP BY race_id
)

SELECT
    race_id,
    wear_drift_s,
    observed_drift_s,
    wear_drift_s - observed_drift_s AS excess_s
FROM d
WHERE wear_drift_s - observed_drift_s > 7.0
