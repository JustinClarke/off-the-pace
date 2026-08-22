-- dim_corners window contract.
-- The catalogue is derived from FastF1 geometry rather than hand-maintained, so
-- these five checks stand in for the review a curated seed used to get: the
-- window has to contain its own apex, stay inside its neighbours, respect the
-- configured margins, and never take geometry from another venue.

WITH neighbours AS (
    SELECT
        corner_key,
        start_distance_m,
        end_distance_m,
        LAG(apex_distance_m) OVER w AS prev_apex_m,
        LEAD(apex_distance_m) OVER w AS next_apex_m
    FROM {{ ref('dim_corners') }}
    WINDOW w AS (PARTITION BY race_id ORDER BY apex_distance_m)
),

catalogue_counts AS (
    SELECT
        race_id,
        ANY_VALUE(geometry_race_id) AS geometry_race_id,
        COUNT(*) AS n_corners
    FROM {{ ref('dim_corners') }}
    GROUP BY race_id
),

source_counts AS (
    SELECT
        race_id,
        COUNT(*) AS n_corners
    FROM {{ ref('stg_circuit_info') }}
    GROUP BY race_id
)

-- 1. The window contains its apex and is non-empty.
SELECT
    'apex_inside_window' AS check_name,
    corner_key,
    CAST(apex_distance_m AS VARCHAR) AS detail
FROM {{ ref('dim_corners') }}
WHERE
    start_distance_m >= end_distance_m
    OR apex_distance_m < start_distance_m
    OR apex_distance_m > end_distance_m

UNION ALL

-- 2. A corner never reaches past its neighbours: the window starts at or after
--    the previous apex and ends at or before the next one, within a race.
SELECT
    'window_within_neighbours' AS check_name,
    corner_key,
    CAST(start_distance_m AS VARCHAR) AS detail
FROM neighbours
WHERE
    start_distance_m < prev_apex_m
    OR end_distance_m > next_apex_m

UNION ALL

-- 3. Margins are the configured ones, not something wider.
SELECT
    'margins_respected' AS check_name,
    corner_key,
    CAST(end_distance_m - apex_distance_m AS VARCHAR) AS detail
FROM {{ ref('dim_corners') }}
WHERE
    start_distance_m < apex_distance_m - {{ var('corner_entry_margin_m') }}
    OR end_distance_m > apex_distance_m + {{ var('corner_exit_margin_m') }}

UNION ALL

-- 4. Borrowed geometry stays inside the event slug. A race missing its own
--    corner table takes the nearest season of the same slug; taking it from a
--    different one would re-import the venue-identity bug the rest of the layer
--    was cleared of.
SELECT
    'borrowed_geometry_same_slug' AS check_name,
    c.corner_key,
    c.geometry_race_id AS detail
FROM {{ ref('dim_corners') }} AS c
INNER JOIN {{ ref('stg_circuit_info') }} AS g
    ON c.geometry_race_id = g.race_id
WHERE
    c.track_id != g.race_slug
    OR (c.geometry_source = 'session' AND c.geometry_race_id != c.race_id)
    OR (c.geometry_source = 'nearest_season' AND c.geometry_race_id = c.race_id)

UNION ALL

-- 5. Corner count matches the source session exactly: the window build neither
--    drops a turn nor duplicates one through the fallback join.
SELECT
    'corner_count_matches_source' AS check_name,
    c.race_id AS corner_key,
    CAST(c.n_corners AS VARCHAR) AS detail
FROM catalogue_counts AS c
INNER JOIN source_counts AS g ON c.geometry_race_id = g.race_id
WHERE c.n_corners != g.n_corners
