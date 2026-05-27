-- De-biased constructor car pace (constructor×race fixed effect).
--
-- A thin reader over data/fits/constructor_car_fe.parquet, emitted by
-- tasks/coefficients/fit_constructor_car_fe.py (a two-way FE regression
-- pace_delta_s ~ 1 | driver_id + constructor_race on the clean lap panel).
--
-- This is the proper HDFE car term that int_constructor_structural_pace's header
-- calls itself a placeholder for: car_fe_s estimates the car pace *net of who
-- drove it* (global driver anchor), so subtracting it removes the car without
-- handing a weak driver's slowness back as "skill". It is consumed ONLY by
-- int_driver_race_skill_loro.driver_skill_field_s → int_driver_circuit_era_affinity
-- (the Ghost Car Standings "equal-car track record" leaderboard).
--
-- It deliberately does NOT replace int_constructor_structural_pace, which has
-- 10+ consumers including the calibration-gated ghost-pace models
-- (fct_ghost_car_pace, fct_ghost_race_finish) that must stay byte-identical.
--
-- Output grain: one row per (race_year, race_id, constructor_id).
-- Sign convention: negative = faster than field.

{{ config(materialized='table', tags=['causal_decomposition', 'constructor']) }}

SELECT
    CONCAT(
        CAST(race_year AS VARCHAR), '_',
        CAST(race_id AS VARCHAR), '_',
        CAST(constructor_id AS VARCHAR)
    )                                       AS constructor_car_fe_id,
    CAST(race_year AS INTEGER)              AS race_year,
    CAST(race_id AS VARCHAR)                AS race_id,
    CAST(constructor_id AS VARCHAR)         AS constructor_id,
    CAST(car_fe_s AS DOUBLE)               AS car_fe_s,
    fit_method,
    fit_timestamp
FROM {{ source('fits', 'constructor_car_fe') }}
