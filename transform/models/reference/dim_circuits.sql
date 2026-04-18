-- dim_circuits.sql · reference · grain: one row per circuit
-- Lifts the circuit_reference seed into a typed dimension: lap length, corner count,
-- lateral-g proxy, and weight-penalty coefficient fitted by tasks/coefficients/.
{{ config(materialized='table') }}

SELECT
    CAST(circuit_key                      AS VARCHAR) AS circuit_key,
    CAST(circuit_name                     AS VARCHAR) AS circuit_name,
    CAST(lap_length_km                    AS DOUBLE)  AS lap_length_km,
    CAST(corner_count                     AS INTEGER) AS corner_count,
    CAST(avg_lateral_g                    AS DOUBLE)  AS avg_lateral_g,
    CAST(fuel_consumption_rate_kg_per_lap AS DOUBLE)  AS fuel_consumption_rate_kg_per_lap,
    CAST(track_energy_index               AS DOUBLE)  AS track_energy_index,
    CAST(abrasiveness_index               AS INTEGER) AS abrasiveness_index,
    CAST(weight_penalty_factor            AS DOUBLE)  AS weight_penalty_factor,
    CAST(era_start_year                   AS INTEGER) AS era_start_year
FROM {{ ref('circuit_reference') }}
