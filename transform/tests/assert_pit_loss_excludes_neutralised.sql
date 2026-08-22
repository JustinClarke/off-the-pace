-- int_pit_loss_circuit stop-population and pooling test.
-- The model's header claims stops under SC/VSC/red are filtered out and that
-- the estimate is pooled per physical venue. Both were untrue before 2026-08:
-- the [8, 60] s window was the only filter, and pooling keyed on the event
-- slug so Silverstone's british / 70th_anniversary halves never met.
--
-- Check 1 rebuilds the eligible stop population independently of the model and
-- compares counts, so dropping the neutralisation filter — or reverting
-- stg_pits to two rows per stop — fails here rather than silently shifting
-- every circuit's median.

WITH race_slug_map AS (
    SELECT DISTINCT race_year, race_id, race_slug
    FROM {{ ref('stg_track_status') }}
    UNION
    SELECT DISTINCT race_year, race_id, race_slug FROM {{ ref('stg_results') }}
),

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

green_laps AS (
    SELECT race_year, race_id, driver_id, lap_number, lap_time_s
    FROM {{ ref('stg_laps') }}
    WHERE
        lap_time_s > 0
        AND NOT is_safety_car_lap
        AND NOT is_vsc_lap
        AND NOT is_red_flag_lap
),

expected AS (
    SELECT
        COALESCE(cm.circuit_id, m.race_slug) AS circuit_id,
        COUNT(*) AS n_stops
    FROM {{ ref('stg_pits') }} AS p
    INNER JOIN race_slug_map AS m
        ON p.race_year = m.race_year AND p.race_id = m.race_id
    LEFT JOIN {{ ref('dim_circuits') }} AS cm
        ON m.race_slug = cm.circuit_key
    INNER JOIN ref_lap AS r
        ON
            p.race_year = r.race_year AND p.race_id = r.race_id
            AND p.driver_id = r.driver_id
    INNER JOIN green_laps AS il
        ON
            p.race_year = il.race_year AND p.race_id = il.race_id
            AND p.driver_id = il.driver_id
            AND p.pit_in_lap_number = il.lap_number
    INNER JOIN green_laps AS ol
        ON
            p.race_year = ol.race_year AND p.race_id = ol.race_id
            AND p.driver_id = ol.driver_id
            AND p.pit_out_lap_number = ol.lap_number
    WHERE
        (il.lap_time_s - r.ref_lap_s) + (ol.lap_time_s - r.ref_lap_s)
        BETWEEN {{ var('pit_loss_min_s', 8) }}
        AND {{ var('pit_loss_max_s', 60) }}
    GROUP BY COALESCE(cm.circuit_id, m.race_slug)
),

actual AS (
    SELECT DISTINCT circuit_id, n_stops
    FROM {{ ref('int_pit_loss_circuit') }}
)

-- 1. The model counted exactly the green-flag stops, no more.
SELECT
    'stop_population' AS check_name,
    a.circuit_id,
    CAST(a.n_stops AS VARCHAR) AS actual_n,
    CAST(e.n_stops AS VARCHAR) AS expected_n
FROM actual AS a
LEFT JOIN expected AS e ON a.circuit_id = e.circuit_id
WHERE a.n_stops IS DISTINCT FROM e.n_stops

UNION ALL

-- 2. Event slugs sharing a physical venue share its estimate exactly. This is
--    the pooling invariant: one pit lane, one loss.
SELECT
    'venue_pooling' AS check_name,
    circuit_id,
    CAST(COUNT(DISTINCT pit_loss_s_empirical) AS VARCHAR) AS actual_n,
    '1' AS expected_n
FROM {{ ref('int_pit_loss_circuit') }}
GROUP BY circuit_id
HAVING
    COUNT(DISTINCT pit_loss_s_empirical) > 1
    OR COUNT(DISTINCT n_stops) > 1

UNION ALL

-- 3. Shrinkage bound: the EB estimate lies between the raw circuit median and
--    the global median it is pulled toward, never outside them.
SELECT
    'shrinkage_bound' AS check_name,
    circuit_id,
    CAST(pit_loss_s_shrunk AS VARCHAR) AS actual_n,
    CAST(pit_loss_s_empirical AS VARCHAR) AS expected_n
FROM {{ ref('int_pit_loss_circuit') }}
WHERE
    pit_loss_s_shrunk
    NOT BETWEEN LEAST(pit_loss_s_empirical, global_pit_loss_s) - 1e-9
    AND GREATEST(pit_loss_s_empirical, global_pit_loss_s) + 1e-9
