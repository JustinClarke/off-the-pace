-- Third Model Sequence #7 (part 2): Ghost car race finish simulator.
-- For each (host_constructor, race) scenario, computes the projected finish
-- position if every driver had been in the given host constructor's car.
--
-- Method: sum predicted_lap_time_s over all laps per driver in the scenario,
-- rank by cumulative race time. Ties broken by actual finish position.
--
-- Grain: (host_constructor_id, ego_driver_id, race_id) one row per scenario.
-- PK: surrogate hash of the three keys.

{{ config(materialized='table', tags=['marts', 'simulation', 'ghost_car']) }}

WITH ghost_laps AS (
    SELECT
        race_year,
        race_id,
        ego_driver_id,
        host_constructor_id,
        lap_number,
        predicted_lap_time_s,
        actual_lap_time_s,
        recombination_confidence
    FROM {{ ref('fct_ghost_car_pace') }}
    WHERE recombination_confidence >= 0.3   -- minimum confidence for position sim
),

-- Actual finish position from stg_laps (last valid lap's position)
actual_finish AS (
    SELECT
        race_year,
        race_id,
        driver_id                               AS ego_driver_id,
        MAX(position) FILTER (WHERE is_valid_lap = TRUE) AS actual_finish_position
    FROM {{ ref('stg_laps') }}
    GROUP BY race_year, race_id, driver_id
),

-- Cumulative race time per (driver, host_constructor, race)
race_totals AS (
    SELECT
        race_year,
        race_id,
        ego_driver_id,
        host_constructor_id,
        SUM(predicted_lap_time_s)               AS predicted_total_race_time_s,
        SUM(actual_lap_time_s)                  AS actual_total_race_time_s,
        COUNT(*)                                AS laps_counted,
        AVG(recombination_confidence)           AS avg_recombination_confidence
    FROM ghost_laps
    GROUP BY race_year, race_id, ego_driver_id, host_constructor_id
),

-- Projected finish positions within each scenario
ranked AS (
    SELECT
        race_year,
        race_id,
        ego_driver_id,
        host_constructor_id,
        predicted_total_race_time_s,
        actual_total_race_time_s,
        laps_counted,
        avg_recombination_confidence,
        -- Rank by predicted total time within this (race, host_constructor) scenario
        RANK() OVER (
            PARTITION BY race_year, race_id, host_constructor_id
            ORDER BY predicted_total_race_time_s ASC
        )                                       AS predicted_finish_position,
        RANK() OVER (
            PARTITION BY race_year, race_id, host_constructor_id
            ORDER BY actual_total_race_time_s ASC
        )                                       AS actual_rank_in_scenario
    FROM race_totals
)

SELECT
    MD5(CONCAT(
        r.race_year, '_',
        r.race_id, '_',
        r.ego_driver_id, '_',
        r.host_constructor_id
    ))                                          AS ghost_race_id,
    r.race_year,
    r.race_id,
    r.ego_driver_id,
    r.host_constructor_id,
    r.predicted_finish_position,
    af.actual_finish_position,
    r.predicted_finish_position
       -COALESCE(af.actual_finish_position, 10) AS delta_vs_actual_position,
    r.predicted_total_race_time_s,
    r.actual_total_race_time_s,
    r.laps_counted,
    r.avg_recombination_confidence
FROM ranked r
LEFT JOIN actual_finish af
    ON r.race_year     = af.race_year
    AND r.race_id      = af.race_id
    AND r.ego_driver_id = af.ego_driver_id
ORDER BY r.race_year, r.race_id, r.host_constructor_id, r.predicted_finish_position
