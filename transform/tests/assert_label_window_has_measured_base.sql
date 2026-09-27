-- T2 (F1, WI-01). Independent re-derivation of the fabricated-base guard at
-- the LABEL level, not the spine level: every mart row whose
-- next_5_lap_cumulative_jump_s is non-null must have a measured
-- int_field_pace_curve row (non-null field_pace_smoothed_s) at every
-- lap_number in its 6-lap window [lap_number .. lap_number + 5].
--
-- Checked against int_field_pace_curve directly, joined fresh on
-- (race_year, race_id, lap_number) here -- not via the mart's own
-- base_track_pace_s or driver_skill_residual_s columns -- so a bug that
-- fabricated the LABEL without fabricating the intermediate columns this
-- test doesn't touch would still be caught.
{{ config(severity='error') }}

WITH labelled AS (
    SELECT race_year, race_id, lap_number
    FROM {{ ref('fct_cliff_prediction_features') }}
    WHERE next_5_lap_cumulative_jump_s IS NOT NULL
),

offsets AS (
    SELECT UNNEST(GENERATE_SERIES(0, 5)) AS offset_n
),

window_laps AS (
    SELECT
        l.race_year,
        l.race_id,
        l.lap_number AS anchor_lap_number,
        l.lap_number + o.offset_n AS window_lap_number
    FROM labelled AS l
    CROSS JOIN offsets AS o
)

SELECT
    w.race_year,
    w.race_id,
    w.anchor_lap_number,
    w.window_lap_number
FROM window_laps AS w
LEFT JOIN {{ ref('int_field_pace_curve') }} AS c
    ON
        w.race_year = c.race_year
        AND w.race_id = c.race_id
        AND w.window_lap_number = c.lap_number
WHERE c.field_pace_smoothed_s IS NULL
