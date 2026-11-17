-- TX-24. Deleted-lap counts per driver, race and session with the laps run
-- (the denominator) in the same row. NOT exported (scratch-only).
-- A season whose Bronze carries no deleted lap in any race or qualifying
-- session (2018: FastF1 has no deletion data) is UNAVAILABLE, not zero: the
-- counts are NULL and deleted_unavailable_reason is SOURCE_HAS_NO_DELETION_DATA.
-- The rule is derived from the data, not a hand list of seasons.
{{ config(materialized='table', tags=['marts', 'new_data']) }}

WITH laps AS (
    SELECT race_year, race_id, 'R' AS session_type, driver_id, constructor_id, is_deleted
    FROM {{ ref('stg_laps') }}
    UNION ALL
    SELECT race_year, race_id, 'Q' AS session_type, driver_id, constructor_id, is_deleted
    FROM {{ ref('stg_laps_qualifying') }}
),

season_has_data AS (
    SELECT race_year, COUNT(*) FILTER (WHERE is_deleted) > 0 AS has_deletion_data
    FROM laps
    GROUP BY race_year
),

per_driver AS (
    SELECT
        race_year, race_id, session_type, driver_id,
        ANY_VALUE(constructor_id ORDER BY constructor_id) AS constructor_id,
        COUNT(*) AS n_laps_run,
        COUNT(*) FILTER (WHERE is_deleted) AS n_deleted
    FROM laps
    GROUP BY race_year, race_id, session_type, driver_id
),

tl AS (
    SELECT
        race_id, session_type, driver_id,
        COUNT(*) FILTER (WHERE is_track_limits) AS n_track_limits,
        COUNT(DISTINCT turn_number) AS n_turns
    FROM {{ ref('fct_track_limits') }}
    GROUP BY race_id, session_type, driver_id
)

SELECT
    CONCAT(p.race_id, '_', p.session_type, '_', p.driver_id) AS driver_session_id,
    p.race_year,
    p.race_id,
    p.session_type,
    p.driver_id,
    p.constructor_id,
    p.n_laps_run,
    CASE WHEN s.has_deletion_data THEN p.n_deleted END AS n_deleted_laps,
    CASE WHEN s.has_deletion_data THEN COALESCE(t.n_track_limits, 0) END
        AS n_track_limits_deletions,
    CASE WHEN s.has_deletion_data THEN COALESCE(t.n_turns, 0) END
        AS n_distinct_turns,
    CASE WHEN NOT s.has_deletion_data THEN 'SOURCE_HAS_NO_DELETION_DATA' END
        AS deleted_unavailable_reason
FROM per_driver AS p
INNER JOIN season_has_data AS s ON p.race_year = s.race_year
LEFT JOIN tl AS t
    ON p.race_id = t.race_id AND p.session_type = t.session_type AND p.driver_id = t.driver_id
ORDER BY p.race_year, p.race_id, p.session_type, p.driver_id
