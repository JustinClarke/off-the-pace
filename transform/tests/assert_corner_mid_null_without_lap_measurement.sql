-- mid_corner_residual_s must be NULL on every corner row that has no lap-corner
-- measurement row in int_corner_lap_measured (no validated observation, no
-- mid-corner term). Also the fence contract: a row flagged 'outlier' has a NULL
-- mid term but keeps its raw value. Returns offending corner rows.
SELECT
    cr.corner_id,
    cr.mid_corner_residual_s,
    cr.mid_corner_residual_raw_s,
    cr.mid_corner_outlier_flag
FROM {{ ref('int_corner_skill_residuals') }} AS cr
LEFT JOIN {{ ref('int_corner_lap_measured') }} AS lq
    ON
        cr.race_id = lq.race_id
        AND cr.driver_id = lq.driver_id
        AND cr.lap_number = lq.lap_number
        AND cr.corner_name = lq.corner_name
WHERE
    (
        lq.race_id IS NULL
        AND (
            cr.mid_corner_residual_s IS NOT NULL
            OR cr.mid_corner_residual_raw_s IS NOT NULL
        )
    )
    OR (
        cr.mid_corner_outlier_flag = 'outlier'
        AND (
            cr.mid_corner_residual_s IS NOT NULL
            OR cr.mid_corner_residual_raw_s IS NULL
        )
    )
