-- CO-04 / W43 + W44. The field base's 5-row smoother must not average across
-- a safety car, VSC or red flag, and must not use a cell built on fewer than
-- 5 cars. Checked on every race, not one example, from the model's own
-- smoothing_window_first_lap / _last_lap and neutralisation re-derived here
-- from int_stint_geometry (any driver's lap at that number flagged).
--
-- One row per failure:
--   'window_crosses_neutralisation' -- a green cell whose averaged span
--     contains a neutralised lap number.
--   'neutralised_cell_not_isolated' -- a neutralised cell averaged with
--     anything but itself.
--   'thin_cell_has_base' -- a cell with low_sample_flag that still has a
--     base or a window span.
--   'base_not_reproduced' -- field_pace_smoothed_s is not the plain mean of
--     the non-thin trimmed means inside its recorded span. This is what makes
--     the span trustworthy: if the model averaged anything outside the span,
--     or any thin cell inside it, the two would differ.
{{ config(severity='error') }}

WITH neutralised AS (
    SELECT
        race_year,
        race_id,
        lap_number
    FROM {{ ref('int_stint_geometry') }}
    GROUP BY race_year, race_id, lap_number
    HAVING BOOL_OR(
        COALESCE(is_safety_car_lap, FALSE)
        OR COALESCE(is_vsc_lap, FALSE)
        OR COALESCE(is_red_flag_lap, FALSE)
    )
),

cells AS (
    SELECT
        c.race_year,
        c.race_id,
        c.lap_number,
        c.field_pace_trimmed_mean_s,
        c.field_pace_smoothed_s,
        c.low_sample_flag,
        c.smoothing_window_first_lap,
        c.smoothing_window_last_lap,
        n.lap_number IS NOT NULL AS is_neutralised
    FROM {{ ref('int_field_pace_curve') }} AS c
    LEFT JOIN neutralised AS n
        ON
            c.race_year = n.race_year
            AND c.race_id = n.race_id
            AND c.lap_number = n.lap_number
),

crossing AS (
    SELECT DISTINCT
        'window_crosses_neutralisation' AS failure,
        c.race_year,
        c.race_id,
        c.lap_number
    FROM cells AS c
    INNER JOIN neutralised AS n
        ON
            c.race_year = n.race_year
            AND c.race_id = n.race_id
            AND n.lap_number BETWEEN c.smoothing_window_first_lap
            AND c.smoothing_window_last_lap
    WHERE NOT c.is_neutralised
),

not_isolated AS (
    SELECT
        'neutralised_cell_not_isolated' AS failure,
        race_year,
        race_id,
        lap_number
    FROM cells
    WHERE
        is_neutralised
        AND field_pace_smoothed_s IS NOT NULL
        AND (
            smoothing_window_first_lap IS DISTINCT FROM lap_number
            OR smoothing_window_last_lap IS DISTINCT FROM lap_number
        )
),

thin_with_base AS (
    SELECT
        'thin_cell_has_base' AS failure,
        race_year,
        race_id,
        lap_number
    FROM cells
    WHERE
        low_sample_flag
        AND (
            field_pace_smoothed_s IS NOT NULL
            OR smoothing_window_first_lap IS NOT NULL
            OR smoothing_window_last_lap IS NOT NULL
        )
),

recomputed AS (
    SELECT
        c.race_year,
        c.race_id,
        c.lap_number,
        c.field_pace_smoothed_s,
        AVG(d.field_pace_trimmed_mean_s) AS expected_smoothed_s
    FROM cells AS c
    LEFT JOIN cells AS d
        ON
            c.race_year = d.race_year
            AND c.race_id = d.race_id
            AND d.lap_number BETWEEN c.smoothing_window_first_lap
            AND c.smoothing_window_last_lap
            AND NOT d.low_sample_flag
            AND d.field_pace_trimmed_mean_s IS NOT NULL
    WHERE NOT c.low_sample_flag
    GROUP BY c.race_year, c.race_id, c.lap_number, c.field_pace_smoothed_s
),

not_reproduced AS (
    SELECT
        'base_not_reproduced' AS failure,
        race_year,
        race_id,
        lap_number
    FROM recomputed
    WHERE
        (field_pace_smoothed_s IS NULL) != (expected_smoothed_s IS NULL)
        OR ABS(field_pace_smoothed_s - expected_smoothed_s) > 1e-9
)

SELECT * FROM crossing
UNION ALL
SELECT * FROM not_isolated
UNION ALL
SELECT * FROM thin_with_base
UNION ALL
SELECT * FROM not_reproduced
