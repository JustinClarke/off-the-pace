-- CO-22: fct_telemetry_deltas pairs teammates only -- the two drivers a
-- constructor entered in that race (stg_laps.constructor_id). Fails on any
-- pair that is not same-constructor in that race, and on any pair that is not
-- ordered driver_a < driver_b. Before CO-22 every driver in the race was
-- paired with every other.
WITH pairs AS (
    SELECT DISTINCT
        race_id,
        driver_a,
        driver_b
    FROM {{ ref('fct_telemetry_deltas') }}
),

entries AS (
    SELECT DISTINCT
        race_id,
        driver_id,
        constructor_id
    FROM {{ ref('stg_laps') }}
)

SELECT
    p.race_id,
    p.driver_a,
    p.driver_b
FROM pairs AS p
LEFT JOIN entries AS ea
    ON p.race_id = ea.race_id AND p.driver_a = ea.driver_id
LEFT JOIN entries AS eb
    ON p.race_id = eb.race_id AND p.driver_b = eb.driver_id
WHERE
    p.driver_a >= p.driver_b
    OR ea.constructor_id IS NULL
    OR eb.constructor_id IS NULL
    OR ea.constructor_id <> eb.constructor_id
