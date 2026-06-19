-- int_pit_loss_circuit.sql · intermediate · grain: one row per circuit (venue
-- slug)
-- Empirical circuit-specific pit-lane loss prior, to replace the
-- largely-imputed
-- constant (circuit_reference.pit_lane_loss_s, default 21 s) used by
-- int_pit_strategy_value. Estimated from the time lost on the in-lap and
-- out-lap
-- of each real pit stop relative to the driver's green-lap baseline that race.
--
-- per-stop loss = (in_lap_time − ref_lap) + (out_lap_time − ref_lap)
--   where ref_lap = the driver's median VALID (green, non-pit) lap that race.
-- Stops under SC/VSC or with anomalous laps are filtered by a sane [{{
-- var('pit_loss_min_s', 8) }},
-- {{ var('pit_loss_max_s', 60) }}] s window before aggregation; the circuit
-- value is the median
-- across stops, EB-shrunk toward the global median for thin circuits.
--
-- Scope: races with a venue slug available (results / track_status ingested  
-- partial during the v0.2 backfill). The numeric race_id is per-season; the
-- slug
-- (e.g. monaco_grand_prix) is the cross-season venue key.
{{ config(materialized='table') }}

WITH race_slug_map AS (
    SELECT DISTINCT race_year, race_id, race_slug
    FROM {{ ref('stg_track_status') }}
    UNION
    SELECT DISTINCT race_year, race_id, race_slug FROM {{ ref('stg_results') }}
),

-- Driver's green-lap baseline per race (median valid lap).
ref_lap AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        MEDIAN(lap_time_s) AS ref_lap_s
    FROM {{ ref('stg_laps') }}
    WHERE is_valid_lap = TRUE
    GROUP BY race_year, race_id, driver_id
),

-- Lap times keyed by (race, driver, lap_number) for the in/out-lap lookups.
lap_times AS (
    SELECT race_year, race_id, driver_id, lap_number, lap_time_s
    FROM {{ ref('stg_laps') }}
    WHERE lap_time_s > 0
),

stops AS (
    SELECT
        m.race_slug AS circuit_slug,
        p.race_year,
        p.race_id,
        p.driver_id,
        il.lap_time_s AS in_lap_s,
        ol.lap_time_s AS out_lap_s,
        r.ref_lap_s,
        (il.lap_time_s - r.ref_lap_s)
        + (ol.lap_time_s - r.ref_lap_s) AS time_lost_s
    FROM {{ ref('stg_pits') }} AS p
    INNER JOIN
        race_slug_map AS m
        ON p.race_year = m.race_year AND p.race_id = m.race_id
    INNER JOIN ref_lap AS r
        ON
            p.race_year = r.race_year AND p.race_id = r.race_id
            AND p.driver_id = r.driver_id
    -- in-lap (the lap the car pitted on) and out-lap (next lap) times
    INNER JOIN lap_times AS il
        ON
            p.race_year = il.race_year AND p.race_id = il.race_id
            AND p.driver_id = il.driver_id
            AND p.pit_in_lap_number = il.lap_number
    INNER JOIN lap_times AS ol
        ON
            p.race_year = ol.race_year AND p.race_id = ol.race_id
            AND p.driver_id = ol.driver_id
            AND p.pit_out_lap_number = ol.lap_number
),

clean_stops AS (
    SELECT *
    FROM stops
    WHERE
        time_lost_s
        BETWEEN {{ var('pit_loss_min_s', 8) }}
        AND {{ var('pit_loss_max_s', 60) }}
),

per_circuit AS (
    SELECT
        circuit_slug,
        COUNT(*) AS n_stops,
        MEDIAN(time_lost_s) AS pit_loss_s_empirical
    FROM clean_stops
    GROUP BY circuit_slug
),

global_loss AS (
    SELECT MEDIAN(time_lost_s) AS global_pit_loss_s FROM clean_stops
)

SELECT
    c.circuit_slug,
    c.n_stops,
    c.pit_loss_s_empirical,
    g.global_pit_loss_s,
    -- EB shrink toward the global median; pseudo-count {{
    -- var('pit_loss_prior_stops', 15) }}
    -- stops of prior weight keeps thin circuits from over-trusting a few
    -- samples.
    (
        c.pit_loss_s_empirical * c.n_stops
        + g.global_pit_loss_s * {{ var('pit_loss_prior_stops', 15) }}
    )
    / (c.n_stops + {{ var('pit_loss_prior_stops', 15) }}) AS pit_loss_s_shrunk
FROM per_circuit AS c
CROSS JOIN global_loss AS g
ORDER BY c.circuit_slug
