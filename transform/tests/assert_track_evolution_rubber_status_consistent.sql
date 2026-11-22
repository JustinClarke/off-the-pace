-- int_track_evolution rubber slope observability. Each rubber_status pins the raw,
-- published and component columns:
--   MEASURED          raw IS NOT NULL, raw <= 0, published = raw (a measured zero stays 0.0)
--   CLAMPED_POSITIVE  raw > 0, published = 0.0
--   INSUFFICIENT_LAPS raw, published and rubber_component_s all NULL (fewer than 2 distinct laps)
--   NO_FIELD_BASE     the lap has no field-pace base: track_state_index_s and rubber_component_s NULL
-- rubber_fit_lap_count is one value per race and counts the rows that carry a base.
-- Grain is (race_year, race_id, lap_number) and every row is a non-thin cell of
-- int_field_pace_curve (not padded, not dropped). Returns offending rows; passes when empty.
WITH evo AS (
    SELECT * FROM {{ ref('int_track_evolution') }}
),

race_stats AS (
    SELECT
        race_year,
        race_id,
        COUNT(DISTINCT rubber_fit_lap_count) AS n_counts,
        MAX(rubber_fit_lap_count) AS fit_count,
        COUNT(track_state_index_s) AS n_with_base
    FROM evo
    GROUP BY race_year, race_id
),

status_violations AS (
    SELECT race_year, race_id, lap_number, 'status ' || COALESCE(rubber_status, 'NULL') AS reason
    FROM evo
    WHERE
        rubber_status IS NULL
        OR rubber_status NOT IN ('MEASURED', 'CLAMPED_POSITIVE', 'INSUFFICIENT_LAPS', 'NO_FIELD_BASE')
        OR (rubber_status = 'MEASURED' AND NOT (
            rubber_slope_raw_s_per_lap IS NOT NULL
            AND rubber_slope_raw_s_per_lap <= 0
            AND rubber_slope_s_per_lap = rubber_slope_raw_s_per_lap
            AND rubber_component_s IS NOT NULL))
        OR (rubber_status = 'CLAMPED_POSITIVE' AND NOT (
            rubber_slope_raw_s_per_lap > 0
            AND rubber_slope_s_per_lap = 0.0
            AND rubber_component_s IS NOT NULL))
        OR (rubber_status = 'INSUFFICIENT_LAPS' AND NOT (
            rubber_slope_raw_s_per_lap IS NULL
            AND rubber_slope_s_per_lap IS NULL
            AND rubber_component_s IS NULL))
        OR (rubber_status = 'NO_FIELD_BASE' AND NOT (
            track_state_index_s IS NULL
            AND rubber_component_s IS NULL))
        -- a lap with a base is never NO_FIELD_BASE; a lap without one always is
        OR (rubber_status = 'NO_FIELD_BASE') != (track_state_index_s IS NULL)
),

count_violations AS (
    SELECT race_year, race_id, CAST(NULL AS BIGINT) AS lap_number, 'rubber_fit_lap_count not one value equal to rows with a base' AS reason
    FROM race_stats
    WHERE n_counts != 1 OR fit_count != n_with_base
),

grain_violations AS (
    SELECT race_year, race_id, lap_number, 'duplicate grain' AS reason
    FROM evo
    GROUP BY race_year, race_id, lap_number
    HAVING COUNT(*) > 1
),

pad_violations AS (
    -- every evolution row is a non-thin field-pace cell, and every such cell has a row
    SELECT
        COALESCE(e.race_year, p.race_year) AS race_year,
        COALESCE(e.race_id, p.race_id) AS race_id,
        COALESCE(e.lap_number, p.lap_number) AS lap_number,
        'row set differs from non-thin int_field_pace_curve cells' AS reason
    FROM evo AS e
    FULL OUTER JOIN (
        SELECT race_year, race_id, lap_number
        FROM {{ ref('int_field_pace_curve') }}
        WHERE NOT low_sample_flag
    ) AS p
        ON
            e.race_year = p.race_year
            AND e.race_id = p.race_id
            AND e.lap_number = p.lap_number
    WHERE e.lap_number IS NULL OR p.lap_number IS NULL
)

SELECT race_year, race_id, lap_number, reason FROM status_violations
UNION ALL
SELECT race_year, race_id, lap_number, reason FROM count_violations
UNION ALL
SELECT race_year, race_id, lap_number, reason FROM grain_violations
UNION ALL
SELECT race_year, race_id, lap_number, reason FROM pad_violations
