-- Third Model Sequence #5 (sub): Fuel state for qualifying laps.
-- Qualifying cars run with 10-20 kg fuel nearly constant across a push lap.
-- The fuel component is structurally ~zero for qualifying; we model it honestly as a
-- tiny constant offset per lap so the identity closes without approximation.
--
-- Output grain: lap_id one row per valid qualifying lap.
-- PK: lap_id (FK to stg_laps_qualifying).

{{ config(materialized='view', tags=['simulation', 'qualifying']) }}

WITH source AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        tyre_life,
        compound
    FROM {{ ref('stg_laps_qualifying') }}
    WHERE is_valid_lap = TRUE
      AND lap_time_s IS NOT NULL
)

SELECT
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    lap_time_s,
    compound,
    tyre_life,
    -- Qualifying fuel load: assume flat 12 kg (mid of 10-20 kg range).
    -- At 0.035 kg/km and ~5 km avg circuit, a push lap burns ~0.175 kg.
    -- Weight penalty at 0.035 s/kg → ~0.006 s per lap. Effectively zero.
    12.0                          AS fuel_mass_kg,
    12.0 * 0.035                  AS fuel_component_s
FROM source
