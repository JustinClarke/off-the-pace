-- TX-01. The paired lap-time gaps behind the race rating, one row per
-- (race, driver, lap_number, teammate). paired_delta_s = own lap_time_s minus
-- the same-car teammate's lap_time_s on the same lap number, over laps both
-- drivers ran clean. int_driver_race_skill_loro.driver_skill_loro_s is the
-- MEDIAN of these rows and its paired_lap_count is their COUNT, per
-- (race, driver); mart_race_driver_summary builds its order-statistic CI for
-- that median from the same rows.
--
-- The clean filter below (lap time present, correction_weight = 1, no
-- rainfall on the lap) is the rating's clean panel and must stay identical to
-- clean_panel in int_driver_race_skill_loro, which still needs the unpaired
-- laps (and their pace delta) for its median and field-anchored signals.
-- assert_mart_race_ci_brackets_rating checks that the two agree on n and on
-- the median for every rated driver-race.
--
-- For a two-driver car the teammate's rows are this driver's rows with the
-- sign flipped. (race_year, race_id, driver_id, lap_number) is unique in
-- int_lap_fuel_state, so a two-driver car gives at most one row per lap per
-- direction.
{{ config(
    materialized='table', tags=['driver_rating', 'causal_decomposition']
) }}

WITH fuel AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s
    FROM {{ ref('int_lap_fuel_state') }}
),

laps_meta AS (
    SELECT
        lap_id,
        constructor_id
    FROM {{ ref('stg_laps') }}
),

corrections AS (
    SELECT
        lap_id,
        correction_weight
    FROM {{ ref('int_event_corrections') }}
),

evolution AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        rainfall_flag
    FROM {{ ref('int_track_evolution') }}
),

clean_panel AS (
    SELECT
        f.race_year,
        f.race_id,
        f.driver_id,
        lm.constructor_id,
        f.lap_number,
        f.lap_time_s
    FROM fuel AS f
    INNER JOIN laps_meta AS lm ON f.lap_id = lm.lap_id
    LEFT JOIN corrections AS cor ON f.lap_id = cor.lap_id
    LEFT JOIN evolution AS e
        ON
            f.race_year = e.race_year
            AND f.race_id = e.race_id
            AND f.lap_number = e.lap_number
    WHERE
        f.lap_time_s IS NOT NULL
        AND COALESCE(cor.correction_weight, 1.0) = 1.0
        AND COALESCE(e.rainfall_flag, FALSE) = FALSE
)

SELECT
    own.race_year,
    own.race_id,
    own.constructor_id,
    own.driver_id,
    mate.driver_id AS teammate_id,
    own.lap_number,
    own.lap_time_s - mate.lap_time_s AS paired_delta_s
FROM clean_panel AS own
INNER JOIN clean_panel AS mate
    ON
        own.race_year = mate.race_year
        AND own.race_id = mate.race_id
        AND own.constructor_id = mate.constructor_id
        AND own.lap_number = mate.lap_number
        AND own.driver_id <> mate.driver_id
ORDER BY
    own.race_year, own.race_id, own.driver_id, own.lap_number, mate.driver_id
