-- Layer 03: Fuel burnoff and weight penalty correction.
-- Deterministic only no fitting. Initial fuel uses a seed-based estimate:
--   race_lap_count × consumption_per_lap × safety_factor (1.0, conservative).
-- Keep raw lap_time_s alongside corrected value so correction is invertible.
{{ config(materialized='table') }}

WITH geom AS (
    SELECT * FROM {{ ref('int_stint_geometry') }}
),

laps AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s
    FROM {{ ref('stg_laps') }}
    WHERE is_valid_lap = TRUE
),

race_map AS (
    SELECT race_id, track_id FROM {{ ref('race_to_track') }}
),

circuits AS (
    SELECT
        circuit_key,
        fuel_consumption_rate_kg_per_lap,
        weight_penalty_factor
    FROM {{ ref('dim_circuits') }}
),

-- Estimate race lap count per race to derive initial fuel load
race_lap_counts AS (
    SELECT
        race_year,
        race_id,
        MAX(lap_number) AS race_lap_count
    FROM laps
    GROUP BY race_year, race_id
),

combined AS (
    SELECT
        g.stint_id,
        g.lap_id,
        g.race_year,
        g.race_id,
        g.driver_id,
        l.lap_number,
        l.lap_time_s,
        c.fuel_consumption_rate_kg_per_lap,
        c.weight_penalty_factor,
        r.race_lap_count,
        -- Initial fuel = race_lap_count × consumption × safety_factor (1.0)
        r.race_lap_count * c.fuel_consumption_rate_kg_per_lap AS initial_fuel_kg
    FROM geom g
    JOIN laps l
        ON g.lap_id = l.lap_id
    JOIN race_map rm
        ON g.race_id = rm.race_id
    JOIN circuits c
        ON rm.track_id = c.circuit_key
    JOIN race_lap_counts r
        ON g.race_year = r.race_year AND g.race_id = r.race_id
),

with_fuel AS (
    SELECT
        *,
        -- Fuel remaining at start of this lap (lap 1 = full tank)
        GREATEST(
            initial_fuel_kg-fuel_consumption_rate_kg_per_lap * (lap_number-1),
            0.0
        ) AS fuel_mass_kg,
        -- Expected fuel consumed by this lap
        fuel_consumption_rate_kg_per_lap * lap_number AS expected_fuel_consumed_kg
    FROM combined
)

SELECT
    stint_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    lap_time_s,
    fuel_mass_kg,
    fuel_mass_kg * weight_penalty_factor                        AS weight_penalty_s,
    lap_time_s-(fuel_mass_kg * weight_penalty_factor)         AS weight_corrected_lap_time,
    -- Positive = lap consumed more fuel than model expects (lift-and-coast → negative delta)
    (initial_fuel_kg-fuel_mass_kg)-expected_fuel_consumed_kg AS fuel_delta_vs_expected
FROM with_fuel
