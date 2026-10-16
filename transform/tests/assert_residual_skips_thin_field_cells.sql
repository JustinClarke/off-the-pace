-- CO-04 / W44. No residual is measured against a field-base cell built on
-- fewer than 5 cars (int_field_pace_curve.low_sample_flag). The base, the
-- pace delta and the driver-skill residual must all be NULL on such a lap.
-- A thin cell feeding a NEIGHBOUR's smoothing window is checked in
-- assert_field_pace_smoothing_respects_boundaries ('base_not_reproduced').
{{ config(severity='error') }}

SELECT
    r.lap_id,
    r.race_year,
    r.race_id,
    r.lap_number,
    f.eligible_lap_count,
    r.base_track_pace_s,
    r.pace_delta_s,
    r.driver_skill_residual_s
FROM {{ ref('int_lap_residual_decomposed') }} AS r
INNER JOIN {{ ref('int_field_pace_curve') }} AS f
    ON
        r.race_year = f.race_year
        AND r.race_id = f.race_id
        AND r.lap_number = f.lap_number
WHERE
    f.low_sample_flag
    AND (
        r.base_track_pace_s IS NOT NULL
        OR r.pace_delta_s IS NOT NULL
        OR r.driver_skill_residual_s IS NOT NULL
    )
