-- dim_events.sql · marts · grain: one row per race-level event
-- Lifts the raw_dim_events seed into a query-ready events dimension:
-- retirements,
-- damage flags, penalties, and safety-car triggers. Consumed by
-- fct_lap_residuals
-- (correction_weight) and int_lap_anomaly_flags (anomaly_class).
{{ config(
    materialized='table'
) }}

WITH source AS (
    -- This references your brand-new dim_events.csv file
    SELECT * FROM {{ ref('raw_dim_events') }}
)

SELECT
    CAST(event_id AS varchar) AS event_id,
    CAST(race_id AS varchar) AS race_id,
    CAST(round_number AS integer) AS round_number,
    CAST(circuit_name AS varchar) AS circuit_name,
    CAST(event_type AS varchar) AS event_type,
    CAST(description AS varchar) AS event_description,
    CAST(affects_driver AS varchar) AS target_driver_code,
    CAST(magnitude_estimate AS double) AS event_severity_multiplier,
    CAST(is_performance_event AS boolean) AS is_performance_impact,
    CAST(is_reliability_event AS boolean) AS is_reliability_impact

FROM source
