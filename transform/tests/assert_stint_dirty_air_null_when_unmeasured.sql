-- TX-17: a stint with no measured dirty-air tax on any lap must carry NULL
-- (with a reason), never 0; a stint with a NULL tax must have a reason; a
-- stint with a measured lap must carry a value. Returns offending stints.
WITH measured AS (
    SELECT
        sg.stint_id,
        COUNT(da.dirty_air_tax_s) AS n_measured
    FROM {{ ref('int_stint_geometry') }} AS sg
    LEFT JOIN {{ ref('int_dirty_air_tax_component') }} AS da
        ON sg.lap_id = da.lap_id
    GROUP BY sg.stint_id
)

SELECT
    f.stint_id,
    f.cumulative_dirty_air_tax_s,
    f.dirty_air_unavailable_reason,
    COALESCE(m.n_measured, 0) AS n_measured,
    CASE
        WHEN COALESCE(m.n_measured, 0) = 0 AND f.cumulative_dirty_air_tax_s IS NOT NULL
            THEN 'unmeasured_stint_has_value'
        WHEN f.cumulative_dirty_air_tax_s IS NULL AND f.dirty_air_unavailable_reason IS NULL
            THEN 'null_without_reason'
        WHEN COALESCE(m.n_measured, 0) > 0 AND f.cumulative_dirty_air_tax_s IS NULL
            THEN 'measured_stint_is_null'
        WHEN f.n_dirty_air_measured_laps <> COALESCE(m.n_measured, 0)
            THEN 'measured_count_mismatch'
    END AS failure
FROM {{ ref('fct_stint_features') }} AS f
LEFT JOIN measured AS m ON f.stint_id = m.stint_id
WHERE
    (COALESCE(m.n_measured, 0) = 0 AND f.cumulative_dirty_air_tax_s IS NOT NULL)
    OR (f.cumulative_dirty_air_tax_s IS NULL AND f.dirty_air_unavailable_reason IS NULL)
    OR (COALESCE(m.n_measured, 0) > 0 AND f.cumulative_dirty_air_tax_s IS NULL)
    OR f.n_dirty_air_measured_laps <> COALESCE(m.n_measured, 0)
