-- Layer 03: Fuel burnoff and weight penalty correction.
-- Deterministic only, no fitting. Keeps raw lap_time_s alongside the corrected
-- value so the correction is invertible.
--
-- WI-05 (F6, F32, F52). The fuel load is a PRE-RACE quantity, so it is priced
-- from the race's SCHEDULED distance, never from how the race went:
--   race_lap_count  = scheduled_laps (race_scheduled_laps seed: the distance
--                     F1 live timing announced before the start)
--   initial_fuel_kg = the season's FIA race-fuel limit (fuel_regulatory_max_kg
--                     macro: 105 kg in 2018, 110 kg from 2019)
--   fuel_consumption_rate_kg_per_lap = initial_fuel_kg / scheduled_laps
-- so the car is modelled as starting at the limit and burning it evenly over
-- the scheduled distance.
--
-- What this replaced, and why. race_lap_count used to be MAX(lap_number) over
-- VALID laps, which reads the race's ending: a neutralised or red-flagged
-- finish shortened it (12 of 172 races, up to 6 laps -- F6), so every lap of
-- those races carried fuel that encoded how the race ended. The rate was a
-- hand-set per-slug constant (dim_circuits.fuel_consumption_rate_kg_per_lap)
-- multiplied into the lap count with no cap, which put 134 of 171 races over
-- the regulatory limit (median 117.8 kg, Sakhir 2020 147.9 kg -- F32). The two
-- compound on the same neutralised races (F52); one scheduled-distance column
-- fixes both. dim_circuits.fuel_consumption_rate_kg_per_lap is no longer read
-- here (the app's simulator still uses it; the weight-penalty fitter divides by
-- this model's rate since WI-13, F55).
--
-- JOIN COMPLETENESS (F8). The two seed joins below are INNER on purpose -- a
-- race with no track or no scheduled distance cannot be priced -- and they
-- must never drop a race silently. assert_race_to_track_covers_all_races (T4)
-- fails the build if any stg_laps race lacks a race_to_track row or its track
-- lacks a dim_circuits row, and assert_fuel_load_matches_scheduled_distance
-- (T6/T24) fails it if any race lacks a scheduled distance or a fuel row.
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
        weight_penalty_factor
    FROM {{ ref('dim_circuits') }}
),

-- One row per race: the scheduled distance and the fuel it implies. Seed rows,
-- not an aggregate over laps -- nothing here reads the race itself.
race_fuel AS (
    SELECT
        race_id,
        race_year,
        scheduled_laps AS race_lap_count,
        {{ fuel_regulatory_max_kg('race_year') }} AS initial_fuel_kg,
        {{ fuel_regulatory_max_kg('race_year') }}
        / NULLIF(scheduled_laps, 0) AS fuel_consumption_rate_kg_per_lap
    FROM {{ ref('race_scheduled_laps') }}
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
        rf.fuel_consumption_rate_kg_per_lap,
        c.weight_penalty_factor,
        rf.race_lap_count,
        rf.initial_fuel_kg
    FROM geom AS g
    INNER JOIN laps AS l
        ON g.lap_id = l.lap_id
    INNER JOIN race_map AS rm
        ON g.race_id = rm.race_id
    INNER JOIN circuits AS c
        ON rm.track_id = c.circuit_key
    INNER JOIN race_fuel AS rf
        ON g.race_id = rf.race_id
),

with_fuel AS (
    SELECT
        *,
        -- Fuel remaining at start of this lap (lap 1 = full tank). Never below
        -- zero: race_lap_count is the scheduled distance, so no lap a race can
        -- actually run exhausts the modelled load.
        GREATEST(
            initial_fuel_kg
            - fuel_consumption_rate_kg_per_lap * (lap_number - 1),
            0.0
        ) AS fuel_mass_kg,
        -- Expected fuel consumed by this lap
        fuel_consumption_rate_kg_per_lap
        * lap_number AS expected_fuel_consumed_kg
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
    fuel_mass_kg * weight_penalty_factor AS weight_penalty_s,
    lap_time_s
    - (fuel_mass_kg * weight_penalty_factor) AS weight_corrected_lap_time,
    -- Positive = lap consumed more fuel than model expects (lift-and-coast →
    -- negative delta)
    (initial_fuel_kg - fuel_mass_kg)
    - expected_fuel_consumed_kg AS fuel_delta_vs_expected,
    -- The race-level constants the load was priced from, carried so the fuel
    -- test (T6/T24) and the audit can check them against the scheduled distance
    -- directly instead of re-deriving them.
    race_lap_count,
    initial_fuel_kg,
    fuel_consumption_rate_kg_per_lap
FROM with_fuel
