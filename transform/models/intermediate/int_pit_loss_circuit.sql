-- int_pit_loss_circuit.sql · intermediate · grain: one row per event slug
-- Empirical circuit-specific pit-lane loss prior, read by
-- int_pit_strategy_value in place of the largely-imputed constant
-- (circuit_reference.pit_lane_loss_s, default 21 s). Estimated from the time
-- lost on the in-lap and out-lap of each real pit stop relative to the
-- driver's green-lap baseline that race.
--
-- per-stop loss = (in_lap_time − ref_lap) + (out_lap_time − ref_lap)
--   where ref_lap = the driver's median VALID (green, non-pit) lap that race.
--
-- Three filters, in order of how much they remove:
--   1. stg_pits is one row per stop, so the in-lap and out-lap of a stop are
--      one observation, not two overlapping windows one lap apart.
--   2. Stops whose in-lap or out-lap ran under SC, VSC or a red flag are
--      dropped outright. Under a neutralisation the lap the stop is measured
--      against is not the lap the driver would otherwise have run, so the
--      difference is not a pit loss.
--   3. A sane [{{ var('pit_loss_min_s', 8) }},
--      {{ var('pit_loss_max_s', 60) }}] s window catches what is left.
--
-- Estimated per physical venue and emitted per event slug. circuit_id pools
-- races run at the same track under different event names (Silverstone's
-- british / 70th_anniversary, Interlagos' brazilian / são_paulo, Mexico,
-- Red Bull Ring): one pit lane, one loss, one sample. Rows stay keyed on the
-- event slug so int_pit_strategy_value's race_to_track join needs no change.
--
-- Scope: races with a venue slug available (results / track_status ingestion
-- is incomplete for some seasons).
{{ config(materialized='table') }}

WITH race_slug_map AS (
    SELECT DISTINCT race_year, race_id, race_slug
    FROM {{ ref('stg_track_status') }}
    UNION
    SELECT DISTINCT race_year, race_id, race_slug FROM {{ ref('stg_results') }}
),

circuit_map AS (
    SELECT circuit_key, circuit_id FROM {{ ref('dim_circuits') }}
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

-- Lap times keyed by (race, driver, lap_number) for the in/out-lap lookups,
-- carrying the neutralisation flags each lap ran under.
lap_times AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        is_safety_car_lap,
        is_vsc_lap,
        is_red_flag_lap
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
        COALESCE(cm.circuit_id, m.race_slug) AS circuit_id,
        (il.lap_time_s - r.ref_lap_s)
        + (ol.lap_time_s - r.ref_lap_s) AS time_lost_s
    FROM {{ ref('stg_pits') }} AS p
    INNER JOIN
        race_slug_map AS m
        ON p.race_year = m.race_year AND p.race_id = m.race_id
    LEFT JOIN circuit_map AS cm ON m.race_slug = cm.circuit_key
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
    WHERE
        NOT il.is_safety_car_lap AND NOT il.is_vsc_lap
        AND NOT il.is_red_flag_lap
        AND NOT ol.is_safety_car_lap AND NOT ol.is_vsc_lap
        AND NOT ol.is_red_flag_lap
),

clean_stops AS (
    SELECT *
    FROM stops
    WHERE
        time_lost_s
        BETWEEN {{ var('pit_loss_min_s', 8) }}
        AND {{ var('pit_loss_max_s', 60) }}
),

per_venue AS (
    SELECT
        circuit_id,
        COUNT(*) AS n_stops,
        MEDIAN(time_lost_s) AS pit_loss_s_empirical
    FROM clean_stops
    GROUP BY circuit_id
),

global_loss AS (
    SELECT MEDIAN(time_lost_s) AS global_pit_loss_s FROM clean_stops
),

-- Every event slug that contributed stops, back-mapped to its venue estimate.
slug_to_venue AS (
    SELECT DISTINCT circuit_slug, circuit_id FROM clean_stops
)

SELECT
    s.circuit_slug,
    s.circuit_id,
    v.n_stops,
    v.pit_loss_s_empirical,
    g.global_pit_loss_s,
    -- EB shrink toward the global median; pseudo-count {{
    -- var('pit_loss_prior_stops', 15) }}
    -- stops of prior weight keeps thin circuits from over-trusting a few
    -- samples.
    (
        v.pit_loss_s_empirical * v.n_stops
        + g.global_pit_loss_s * {{ var('pit_loss_prior_stops', 15) }}
    )
    / (v.n_stops + {{ var('pit_loss_prior_stops', 15) }}) AS pit_loss_s_shrunk
FROM slug_to_venue AS s
INNER JOIN per_venue AS v ON s.circuit_id = v.circuit_id
CROSS JOIN global_loss AS g
ORDER BY s.circuit_slug
