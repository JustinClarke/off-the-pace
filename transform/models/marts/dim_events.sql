-- dim_events.sql · marts · grain: one row per race-level event
-- Lifts the raw_dim_events seed into a query-ready events dimension: retirements,
-- damage flags, penalties, and safety-car triggers. Consumed by fct_lap_residuals
-- (correction_weight) and int_lap_anomaly_flags (anomaly_class).
{{ config(
    materialized='table'
) }}

with source as (
    -- This references your brand-new dim_events.csv file
    select * from {{ ref('raw_dim_events') }}
)

select
    cast(event_id as varchar) as event_id,
    cast(race_id as varchar) as race_id,
    cast(round_number as integer) as round_number,
    cast(circuit_name as varchar) as circuit_name,
    cast(event_type as varchar) as event_type,
    cast(description as varchar) as event_description,
    cast(affects_driver as varchar) as target_driver_code,
    cast(magnitude_estimate as double) as event_severity_multiplier,
    cast(is_performance_event as boolean) as is_performance_impact,
    cast(is_reliability_event as boolean) as is_reliability_impact

from source