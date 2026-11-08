-- TX-08. The count columns of the three AI marts are recounted from their
-- sources. This replaces range tests that could not fail (n_drivers >= 1
-- against a minimum of 20, sample_size >= 1 against 13,501, laps_completed
-- >= 0 against 1). Each check is an identity with the source, so it fails
-- on any drift, not only on a negative count.
--
--   race: n_drivers = rows of the mart for that race, and >= 2 (a race
--     rating is a paired gap to a same-car teammate); laps_completed =
--     fct_lap_residuals laps of the driver in the race; n_clean_laps = its
--     ml_eligible laps, NULL (not 0) when there are none
--     (residual_unavailable_reason says why), never above laps_completed.
--   season: n_drivers = rows of the mart for that season, and >= 2 (same
--     reason); teammate_gap_rank <= n_drivers; 1 <= n_races <= the races
--     the driver has laps for in fct_lap_residuals that season.
--   benchmark: every (metric, season) of fct_lap_residuals has a row, and
--     sample_size is the non-NULL count of that metric over the season's
--     ml_eligible laps. dirty_air_tax_s is recounted by
--     assert_dirty_air_mean_excludes_unmeasured (its row counts measured
--     laps only), so it is left out here.
-- Fails per offending row, and once if any of the three marts is empty.
-- No race id is required (CI fixture safe).
WITH race_mart AS (
    SELECT * FROM {{ ref('mart_race_driver_summary') }}
),

season_mart AS (
    SELECT * FROM {{ ref('mart_driver_season_summary') }}
),

bench AS (
    SELECT * FROM {{ ref('mart_metric_benchmark') }}
),

laps AS (
    SELECT * FROM {{ ref('fct_lap_residuals') }}
),

clean_laps AS (
    SELECT * FROM laps
    WHERE ml_eligible = TRUE
),

race_laps AS (
    SELECT
        race_id,
        driver_id,
        COUNT(*) AS n_laps,
        COUNT(*) FILTER (WHERE ml_eligible) AS n_ml
    FROM laps
    GROUP BY race_id, driver_id
),

season_races AS (
    SELECT
        race_year,
        driver_id,
        COUNT(DISTINCT race_id) AS n_lap_races
    FROM laps
    GROUP BY race_year, driver_id
),

bench_ref AS (
    SELECT
        race_year,
        'driver_skill_residual_s' AS metric_name,
        COUNT(driver_skill_residual_s) AS n
    FROM clean_laps
    GROUP BY race_year
    UNION ALL
    SELECT
        race_year,
        'fuel_component_s' AS metric_name,
        COUNT(fuel_component_s) AS n
    FROM clean_laps
    GROUP BY race_year
    UNION ALL
    SELECT
        race_year,
        'compound_component_s' AS metric_name,
        COUNT(compound_component_s) AS n
    FROM clean_laps
    GROUP BY race_year
    UNION ALL
    SELECT
        race_year,
        'constructor_component_s' AS metric_name,
        COUNT(constructor_component_s) AS n
    FROM clean_laps
    GROUP BY race_year
    UNION ALL
    SELECT
        race_year,
        'lap_time_s' AS metric_name,
        COUNT(lap_time_s) AS n
    FROM clean_laps
    GROUP BY race_year
),

race_rows AS (
    SELECT
        m.race_id,
        m.driver_id,
        m.n_drivers,
        m.laps_completed,
        m.n_clean_laps,
        rl.n_laps,
        rl.n_ml,
        COUNT(*) OVER (PARTITION BY m.race_id) AS rows_in_race
    FROM race_mart AS m
    LEFT JOIN race_laps AS rl
        ON m.race_id = rl.race_id AND m.driver_id = rl.driver_id
),

season_rows AS (
    SELECT
        m.race_year,
        m.driver_id,
        m.n_drivers,
        m.n_races,
        m.teammate_gap_rank,
        sr.n_lap_races,
        COUNT(*) OVER (PARTITION BY m.race_year) AS rows_in_season
    FROM season_mart AS m
    LEFT JOIN season_races AS sr
        ON m.race_year = sr.race_year AND m.driver_id = sr.driver_id
),

mart_sizes AS (
    SELECT
        'mart_race_driver_summary' AS mart_name,
        (SELECT COUNT(*) FROM race_mart) AS n_rows
    UNION ALL
    SELECT
        'mart_driver_season_summary' AS mart_name,
        (SELECT COUNT(*) FROM season_mart) AS n_rows
    UNION ALL
    SELECT
        'mart_metric_benchmark' AS mart_name,
        (SELECT COUNT(*) FROM bench) AS n_rows
)

SELECT
    'race_n_drivers' AS failure,
    race_id AS unit_id,
    driver_id AS item,
    n_drivers AS got,
    rows_in_race AS expected
FROM race_rows
WHERE n_drivers IS DISTINCT FROM rows_in_race OR n_drivers < 2

UNION ALL

SELECT
    'race_laps_completed' AS failure,
    race_id AS unit_id,
    driver_id AS item,
    laps_completed AS got,
    n_laps AS expected
FROM race_rows
WHERE laps_completed IS DISTINCT FROM n_laps

UNION ALL

SELECT
    'race_n_clean_laps' AS failure,
    race_id AS unit_id,
    driver_id AS item,
    n_clean_laps AS got,
    n_ml AS expected
FROM race_rows
WHERE
    n_clean_laps IS DISTINCT FROM NULLIF(n_ml, 0)
    OR n_clean_laps > laps_completed

UNION ALL

SELECT
    'season_n_drivers' AS failure,
    CAST(race_year AS VARCHAR) AS unit_id,
    driver_id AS item,
    n_drivers AS got,
    rows_in_season AS expected
FROM season_rows
WHERE n_drivers IS DISTINCT FROM rows_in_season OR n_drivers < 2

UNION ALL

SELECT
    'season_rank_above_n_drivers' AS failure,
    CAST(race_year AS VARCHAR) AS unit_id,
    driver_id AS item,
    teammate_gap_rank AS got,
    n_drivers AS expected
FROM season_rows
WHERE teammate_gap_rank > n_drivers

UNION ALL

SELECT
    'season_n_races' AS failure,
    CAST(race_year AS VARCHAR) AS unit_id,
    driver_id AS item,
    n_races AS got,
    n_lap_races AS expected
FROM season_rows
WHERE n_races < 1 OR n_lap_races IS NULL OR n_races > n_lap_races

UNION ALL

SELECT
    'benchmark_sample_size' AS failure,
    CAST(br.race_year AS VARCHAR) AS unit_id,
    br.metric_name AS item,
    b.sample_size AS got,
    br.n AS expected
FROM bench_ref AS br
LEFT JOIN bench AS b
    ON br.race_year = b.race_year AND br.metric_name = b.metric_name
WHERE b.sample_size IS DISTINCT FROM br.n

UNION ALL

SELECT
    'empty_mart' AS failure,
    mart_name AS unit_id,
    NULL AS item,
    NULL AS got,
    NULL AS expected
FROM mart_sizes
WHERE n_rows = 0
