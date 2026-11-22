-- Where base_pace_status is not MEASURED (THIN_CELL or NO_CELL) there is no
-- pace base, so base_track_pace_s and pace_delta_s are NULL. driver_skill_residual_s
-- is expected to be NULL as well: in int_lap_residual_decomposed it is
-- (lap_time_s - base_track_pace_s) - fuel - compound - constructor - dirty_air,
-- and a NULL base propagates through it (the code does not fill it). Returns
-- the offending rows. rain_state is deliberately not checked: it is not gated
-- by base_pace_status.
{{ config(severity='error') }}

SELECT
    lap_id,
    race_id,
    lap_number,
    base_pace_status,
    base_track_pace_s,
    pace_delta_s,
    driver_skill_residual_s
FROM {{ ref('int_lap_residual_decomposed') }}
WHERE
    base_pace_status <> 'MEASURED'
    AND (
        base_track_pace_s IS NOT NULL
        OR pace_delta_s IS NOT NULL
        OR driver_skill_residual_s IS NOT NULL
    )
