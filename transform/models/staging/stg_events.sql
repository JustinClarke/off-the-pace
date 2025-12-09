-- Race-level events: damage, engine clipping, retirements, penalties.
-- Currently sourced from the raw_dim_events seed (manual entries for 2021).
-- Expand to a proper source table once automated event detection is in place.
{{ config(materialized='view') }}

WITH seed AS (
    SELECT * FROM {{ ref('raw_dim_events') }}
)

SELECT
    CONCAT(race_id, '_', event_id)      AS stg_event_id,
    event_id,
    race_id,
    affects_driver                      AS driver_id,
    event_type,
    CAST(magnitude_estimate AS DOUBLE)  AS event_severity,
    'manual'                            AS source,
    CAST(is_performance_event AS BOOLEAN) AS is_performance_impact,
    CAST(is_reliability_event AS BOOLEAN) AS is_reliability_impact
FROM seed
