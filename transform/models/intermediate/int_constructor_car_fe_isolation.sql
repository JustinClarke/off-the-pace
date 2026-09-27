-- Driver-isolation car term (WI-16a): the constructor×race FE fitted on the
-- isolation panel. A thin reader over
-- data/fits/constructor_car_fe_isolation.parquet, written by
-- tasks/coefficients/fit_constructor_car_fe.py --panel isolation (`make
-- car-fe-isolation-fit`), which fits
--     y_s ~ 1 | driver_era + constructor_race
-- on int_driver_isolation_lap_panel and re-centres the constructor×race FE to a
-- lap-weighted mean of zero inside each race.
--
-- Why a second car term, not int_constructor_car_fe: that one is fitted on
-- pace_delta_s, before compound and dirty air are taken out, so it carries each
-- team's average strategy and traffic exposure. The isolation ratings subtract
-- the car from y_s, which has both removed already; subtracting a car term
-- fitted on pace_delta_s would take those terms out a second time (the F22/F38
-- defect shape). int_constructor_car_fe keeps its own consumers
-- (int_driver_race_skill_loro, Ghost Standings) and is untouched.
--
-- Output grain: one row per (race_year, race_id, constructor_id) present in Ω.
-- Sign: car_iso_s in seconds, NEGATIVE = FASTER than the race's lap-weighted
-- car (the car_fe_s convention). NULL, never 0, when the cell is not identified
-- (car_term_source = 'unidentified' or 'not_estimated'): the downstream pace
-- (int_driver_isolation_lap_pace) is then NULL too.
--
-- Leakage: part of the driver-isolation subtree. No ML-contract mart may depend
-- on it (T48).

{{ config(materialized='table', tags=['driver_isolation', 'constructor']) }}

SELECT
    CONCAT(
        CAST(race_year AS VARCHAR), '_',
        CAST(race_id AS VARCHAR), '_',
        CAST(constructor_id AS VARCHAR)
    ) AS constructor_car_fe_isolation_id,
    CAST(race_year AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(constructor_id AS VARCHAR) AS constructor_id,
    CAST(era AS VARCHAR) AS era,
    CAST(n_laps AS INTEGER) AS n_laps,
    CAST(car_fe_raw_s AS DOUBLE) AS car_fe_raw_s,
    CAST(car_iso_s AS DOUBLE) AS car_iso_s,
    CAST(car_term_source AS VARCHAR) AS car_term_source,
    CAST(race_components_n AS INTEGER) AS race_components_n,
    connectivity_note,
    fit_method,
    fit_timestamp
FROM {{ source('fits', 'constructor_car_fe_isolation') }}
