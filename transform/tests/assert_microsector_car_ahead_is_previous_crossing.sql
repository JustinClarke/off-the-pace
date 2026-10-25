-- DA-02: the car ahead in int_microsector_proximity is the previous ON-TRACK
-- crossing of the same boundary, and the order is total.
--
-- Re-derived here from int_microsector_crossings by a different route: the
-- pit-window exclusion is an anti-join (the model uses EXISTS), and the
-- neighbour is the row ranked one place earlier with ROW_NUMBER (the model uses
-- LAG). Inside one (race, boundary) the key (crossing_time_s, driver_id) must
-- be unique, or a rebuild could pick a different neighbour from a tied block
-- (the int_lap_proximity defect, 1.39% of crossings there).
--
-- One row per failure:
--   'order_key_not_unique'  two on-track crossings share (race, boundary,
--                           crossing_time_s, driver_id)
--   'ahead_differs'         the model's ahead_driver_id, ahead_lap_number or
--                           gap_ahead_s disagrees with the re-derivation
{{ config(severity='error') }}

WITH on_track AS (
    SELECT c.*
    FROM {{ ref('int_microsector_crossings') }} AS c
    LEFT JOIN {{ ref('stg_pits') }} AS p
        ON
            c.race_id = p.race_id
            AND c.driver_id = p.driver_id
            AND p.pit_in_time_s IS NOT NULL
            AND c.crossing_time_s BETWEEN p.pit_in_time_s
            AND COALESCE(
                p.pit_out_time_s,
                p.pit_in_time_s + {{ var('proximity_pit_window_open_s', 120.0) }}
            )
    WHERE p.race_id IS NULL
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY race_year, race_id, microsector
            ORDER BY crossing_time_s, driver_id
        ) AS rn
    FROM on_track
),

derived AS (
    SELECT
        r.race_year,
        r.race_id,
        r.driver_id,
        r.lap_number,
        r.microsector,
        CASE
            WHEN
                q.driver_id IS NOT NULL
                AND q.driver_id != r.driver_id
                AND r.crossing_time_s - q.crossing_time_s
                <= {{ var('proximity_max_gap_s') }}
                THEN q.driver_id
        END AS ahead_driver_id,
        CASE
            WHEN
                q.driver_id IS NOT NULL
                AND q.driver_id != r.driver_id
                AND r.crossing_time_s - q.crossing_time_s
                <= {{ var('proximity_max_gap_s') }}
                THEN q.lap_number
        END AS ahead_lap_number,
        CASE
            WHEN
                q.driver_id IS NOT NULL
                AND q.driver_id != r.driver_id
                AND r.crossing_time_s - q.crossing_time_s
                <= {{ var('proximity_max_gap_s') }}
                THEN r.crossing_time_s - q.crossing_time_s
        END AS gap_ahead_s
    FROM ranked AS r
    LEFT JOIN ranked AS q
        ON
            r.race_year = q.race_year
            AND r.race_id = q.race_id
            AND r.microsector = q.microsector
            AND r.rn - 1 = q.rn
),

ties AS (
    SELECT
        'order_key_not_unique' AS failure,
        race_id,
        microsector,
        CAST(crossing_time_s AS VARCHAR) AS detail
    FROM on_track
    GROUP BY race_year, race_id, microsector, crossing_time_s, driver_id
    HAVING COUNT(*) > 1
),

differs AS (
    SELECT
        'ahead_differs' AS failure,
        m.race_id,
        m.microsector,
        m.microsector_id AS detail
    FROM {{ ref('int_microsector_proximity') }} AS m
    INNER JOIN derived AS d
        ON
            m.race_year = d.race_year
            AND m.race_id = d.race_id
            AND m.driver_id = d.driver_id
            AND m.lap_number = d.lap_number
            AND m.microsector = d.microsector
    WHERE
        m.ahead_driver_id IS DISTINCT FROM d.ahead_driver_id
        OR m.ahead_lap_number IS DISTINCT FROM d.ahead_lap_number
        OR (m.gap_ahead_s IS NULL) != (d.gap_ahead_s IS NULL)
        OR ABS(m.gap_ahead_s - d.gap_ahead_s) > 1e-5
)

SELECT * FROM ties
UNION ALL
SELECT * FROM differs
