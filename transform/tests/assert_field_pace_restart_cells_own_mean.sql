-- CO-04 / W43, restart laps (owner decision 2026-10-15). The first two green
-- lap numbers after a safety car or red flag are restart-adjacent: each takes
-- its own trimmed mean as its field base, and no other cell's smoothing window
-- reaches one. So a restart cell never averages with the green laps before the
-- neutralisation, nor with the faster green laps after it. Restart laps are
-- re-derived here from int_stint_geometry (any driver's lap at that number
-- flagged), not read from the model's own is_restart_adjacent_lap.
--
-- One row per failure:
--   'restart_flag_mismatch' -- the model's is_restart_adjacent_lap disagrees
--     with the re-derivation.
--   'restart_cell_not_own_mean' -- a restart-adjacent cell with a base whose
--     span is not its own lap, or whose base is not its own trimmed mean.
--   'window_reaches_restart_cell' -- another cell's averaged span contains a
--     restart-adjacent lap number.
{{ config(severity='error') }}

WITH lap_flags AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        BOOL_OR(
            COALESCE(is_safety_car_lap, FALSE)
            OR COALESCE(is_vsc_lap, FALSE)
            OR COALESCE(is_red_flag_lap, FALSE)
        ) AS is_neutralised,
        BOOL_OR(
            COALESCE(is_safety_car_lap, FALSE)
            OR COALESCE(is_red_flag_lap, FALSE)
        ) AS is_sc_or_red
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY race_year, race_id, lap_number
),

ordered AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        is_neutralised,
        LAG(is_neutralised, 1) OVER w AS prev1_neutralised,
        LAG(is_sc_or_red, 1) OVER w AS prev1_sc_or_red,
        LAG(is_sc_or_red, 2) OVER w AS prev2_sc_or_red
    FROM lap_flags
    WINDOW w AS (PARTITION BY race_year, race_id ORDER BY lap_number)
),

restart AS (
    SELECT
        race_year,
        race_id,
        lap_number
    FROM ordered
    WHERE
        NOT is_neutralised
        AND (
            prev1_sc_or_red
            OR (NOT prev1_neutralised AND prev2_sc_or_red)
        )
),

cells AS (
    SELECT
        c.race_year,
        c.race_id,
        c.lap_number,
        c.field_pace_trimmed_mean_s,
        c.field_pace_smoothed_s,
        c.smoothing_window_first_lap,
        c.smoothing_window_last_lap,
        c.is_restart_adjacent_lap,
        r.lap_number IS NOT NULL AS is_restart
    FROM {{ ref('int_field_pace_curve') }} AS c
    LEFT JOIN restart AS r
        ON
            c.race_year = r.race_year
            AND c.race_id = r.race_id
            AND c.lap_number = r.lap_number
),

flag_mismatch AS (
    SELECT
        'restart_flag_mismatch' AS failure,
        race_year,
        race_id,
        lap_number
    FROM cells
    WHERE is_restart_adjacent_lap IS DISTINCT FROM is_restart
),

not_own_mean AS (
    SELECT
        'restart_cell_not_own_mean' AS failure,
        race_year,
        race_id,
        lap_number
    FROM cells
    WHERE
        is_restart
        AND field_pace_smoothed_s IS NOT NULL
        AND (
            smoothing_window_first_lap IS DISTINCT FROM lap_number
            OR smoothing_window_last_lap IS DISTINCT FROM lap_number
            OR ABS(field_pace_smoothed_s - field_pace_trimmed_mean_s) > 1e-9
        )
),

reaches_restart AS (
    SELECT DISTINCT
        'window_reaches_restart_cell' AS failure,
        c.race_year,
        c.race_id,
        c.lap_number
    FROM cells AS c
    INNER JOIN restart AS r
        ON
            c.race_year = r.race_year
            AND c.race_id = r.race_id
            AND r.lap_number BETWEEN c.smoothing_window_first_lap
            AND c.smoothing_window_last_lap
    WHERE c.lap_number != r.lap_number
)

SELECT * FROM flag_mismatch
UNION ALL
SELECT * FROM not_own_mean
UNION ALL
SELECT * FROM reaches_restart
