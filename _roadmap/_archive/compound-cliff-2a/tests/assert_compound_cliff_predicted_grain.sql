{{ config(tags=['intermediate'], severity='error') }}
-- Task 2A. The cell join must not change the grain: int_compound_cliff_predicted
-- is one row per valid lap. A fan-out (a duplicate dim_compounds_season key, or
-- a duplicate race_to_track row) or a drop would show here either as a repeated
-- lap_id or as a row count that differs from the valid laps of
-- int_stint_geometry that have a track slug.
WITH dupes AS (
    SELECT lap_id, COUNT(*) AS n
    FROM {{ ref('int_compound_cliff_predicted') }}
    GROUP BY lap_id
    HAVING COUNT(*) > 1
),

counts AS (
    SELECT
        (SELECT COUNT(*) FROM {{ ref('int_compound_cliff_predicted') }}) AS predicted_rows,
        (
            SELECT COUNT(*)
            FROM {{ ref('int_stint_geometry') }} AS g
            INNER JOIN {{ ref('race_to_track') }} AS rt ON g.race_id = rt.race_id
            WHERE g.is_valid_lap = TRUE
        ) AS expected_rows
)

SELECT lap_id AS offender, n AS value, 'duplicate lap_id' AS reason
FROM dupes
UNION ALL
SELECT 'row_count' AS offender, predicted_rows AS value, 'row count differs from valid-lap spine' AS reason
FROM counts
WHERE predicted_rows <> expected_rows
