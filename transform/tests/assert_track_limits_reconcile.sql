-- TX-24: fct_track_limits reconciles with the Bronze Deleted totals per
-- session (every deleted lap in stg_laps / stg_laps_qualifying has a row,
-- and no row exists without one), and fct_track_limits_driver_session counts
-- the same laps. A season with no deletion data is NULL with a reason, not 0.
WITH bronze AS (
    SELECT race_id, 'R' AS session_type, COUNT(*) FILTER (WHERE is_deleted) AS n
    FROM {{ ref('stg_laps') }} GROUP BY race_id
    UNION ALL
    SELECT race_id, 'Q', COUNT(*) FILTER (WHERE is_deleted)
    FROM {{ ref('stg_laps_qualifying') }} GROUP BY race_id
),

fct AS (
    SELECT race_id, session_type, COUNT(*) AS n
    FROM {{ ref('fct_track_limits') }} GROUP BY race_id, session_type
),

ds AS (
    SELECT race_id, session_type, SUM(n_deleted_laps) AS n,
        COUNT(*) FILTER (WHERE n_deleted_laps IS NULL AND deleted_unavailable_reason IS NULL)
            AS n_null_without_reason,
        COUNT(*) FILTER (WHERE n_deleted_laps = 0 AND deleted_unavailable_reason IS NOT NULL)
            AS n_zero_with_reason
    FROM {{ ref('fct_track_limits_driver_session') }} GROUP BY race_id, session_type
)

SELECT b.race_id, b.session_type, b.n AS bronze_n, f.n AS fct_n, d.n AS driver_session_n
FROM bronze AS b
LEFT JOIN fct AS f ON b.race_id = f.race_id AND b.session_type = f.session_type
LEFT JOIN ds AS d ON b.race_id = d.race_id AND b.session_type = d.session_type
WHERE
    b.n <> COALESCE(f.n, 0)
    OR (d.n IS NOT NULL AND d.n <> b.n)
    OR d.n_null_without_reason > 0
    OR d.n_zero_with_reason > 0
