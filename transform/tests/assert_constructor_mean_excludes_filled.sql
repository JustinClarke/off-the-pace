-- No aggregate averages the 0.0 that fct_lap_residuals writes on laps whose
-- car term is unmeasured. Recomputes the mean over ml_eligible laps with
-- NOT constructor_pace_is_filled per (race_id, driver_id) and
-- (race_year, driver_id) and compares mart_race_driver_summary and
-- mart_driver_season_summary mean_constructor_component_s within 1e-9. A
-- driver-race or season with no measured lap must have a NULL mean, and a
-- NULL mean must have no measured lap. Also recomputes the constructor-level
-- constructor_measured_laps_n. Returns violating rows.
WITH measured AS (
    SELECT race_year, race_id, driver_id, constructor_component_s
    FROM {{ ref('fct_lap_residuals') }}
    WHERE ml_eligible = TRUE AND NOT constructor_pace_is_filled
),

race_ref AS (
    SELECT race_id, driver_id, COUNT(*) AS n, AVG(constructor_component_s) AS mean_s
    FROM measured
    GROUP BY race_id, driver_id
),

season_ref AS (
    SELECT race_year, driver_id, COUNT(*) AS n, AVG(constructor_component_s) AS mean_s
    FROM measured
    GROUP BY race_year, driver_id
),

rows_all AS (
    SELECT
        'race' AS grain,
        m.race_id AS unit_id,
        m.driver_id,
        m.mean_constructor_component_s AS got_mean,
        r.mean_s AS ref_mean,
        COALESCE(r.n, 0) AS ref_n
    FROM {{ ref('mart_race_driver_summary') }} AS m
    LEFT JOIN race_ref AS r
        ON m.race_id = r.race_id AND m.driver_id = r.driver_id
    UNION ALL
    SELECT
        'season' AS grain,
        CAST(m.race_year AS VARCHAR) AS unit_id,
        m.driver_id,
        m.mean_constructor_component_s AS got_mean,
        r.mean_s AS ref_mean,
        COALESCE(r.n, 0) AS ref_n
    FROM {{ ref('mart_driver_season_summary') }} AS m
    LEFT JOIN season_ref AS r
        ON m.race_year = r.race_year AND m.driver_id = r.driver_id
)

SELECT grain, unit_id, driver_id, got_mean, ref_mean, ref_n
FROM rows_all
WHERE
    (got_mean IS NULL) <> (ref_mean IS NULL)
    OR ABS(got_mean - ref_mean) > 1e-9
    OR (got_mean IS NULL AND ref_n > 0)
    OR (got_mean IS NOT NULL AND ref_n = 0)

UNION ALL

SELECT
    'race_constructor_n' AS grain,
    m.race_id AS unit_id,
    m.driver_id,
    CAST(m.constructor_measured_laps_n AS DOUBLE) AS got_mean,
    CAST(c.n AS DOUBLE) AS ref_mean,
    c.n AS ref_n
FROM {{ ref('mart_race_driver_summary') }} AS m
LEFT JOIN (
    SELECT race_id, constructor_id, COUNT(*) AS n
    FROM {{ ref('fct_lap_residuals') }}
    WHERE ml_eligible = TRUE AND NOT constructor_pace_is_filled
    GROUP BY race_id, constructor_id
) AS c ON m.race_id = c.race_id AND m.constructor_id = c.constructor_id
WHERE m.constructor_measured_laps_n IS DISTINCT FROM COALESCE(c.n, 0)

UNION ALL

SELECT
    'season_constructor_n' AS grain,
    CAST(m.race_year AS VARCHAR) AS unit_id,
    m.driver_id,
    CAST(m.constructor_measured_laps_n AS DOUBLE) AS got_mean,
    CAST(c.n AS DOUBLE) AS ref_mean,
    c.n AS ref_n
FROM {{ ref('mart_driver_season_summary') }} AS m
LEFT JOIN (
    SELECT race_year, constructor_id, COUNT(*) AS n
    FROM {{ ref('fct_lap_residuals') }}
    WHERE ml_eligible = TRUE AND NOT constructor_pace_is_filled
    GROUP BY race_year, constructor_id
) AS c ON m.race_year = c.race_year AND m.constructor_id = c.constructor_id
WHERE m.constructor_measured_laps_n IS DISTINCT FROM COALESCE(c.n, 0)
