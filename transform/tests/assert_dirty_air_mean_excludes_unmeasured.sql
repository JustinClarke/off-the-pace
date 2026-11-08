-- TX-03. No aggregate averages the 0.0 that fct_lap_residuals writes on laps
-- with no dirty-air row. Recomputes, from fct_lap_residuals joined to
-- int_dirty_air_tax_component over ml_eligible laps with a measured tax:
--   mart_race_driver_summary and mart_driver_season_summary
--     mean_dirty_air_tax_s and n_dirty_air_measured_laps;
--   mart_metric_benchmark's dirty_air_tax_s row (mean, sample_size).
-- Fails on any |delta| > 1e-9, a count mismatch, a non-NULL mean with zero
-- measured laps, or a reason that disagrees with the mean being NULL.
-- No race id is required (CI fixture safe).
WITH measured AS (
    SELECT
        f.race_year,
        f.race_id,
        f.driver_id,
        f.dirty_air_tax_s
    FROM {{ ref('fct_lap_residuals') }} AS f
    INNER JOIN {{ ref('int_dirty_air_tax_component') }} AS da
        ON f.lap_id = da.lap_id
    WHERE f.ml_eligible = TRUE AND da.dirty_air_tax_s IS NOT NULL
),

race_ref AS (
    SELECT race_id, driver_id, COUNT(*) AS n, AVG(dirty_air_tax_s) AS mean_s
    FROM measured
    GROUP BY race_id, driver_id
),

season_ref AS (
    SELECT race_year, driver_id, COUNT(*) AS n, AVG(dirty_air_tax_s) AS mean_s
    FROM measured
    GROUP BY race_year, driver_id
),

bench_ref AS (
    SELECT race_year, COUNT(*) AS n, AVG(dirty_air_tax_s) AS mean_s
    FROM measured
    GROUP BY race_year
),

race_rows AS (
    SELECT
        'race' AS grain,
        m.race_id AS unit_id,
        m.driver_id,
        m.mean_dirty_air_tax_s AS got_mean,
        m.n_dirty_air_measured_laps AS got_n,
        m.dirty_air_unavailable_reason AS reason,
        r.mean_s AS ref_mean,
        COALESCE(r.n, 0) AS ref_n
    FROM {{ ref('mart_race_driver_summary') }} AS m
    LEFT JOIN race_ref AS r
        ON m.race_id = r.race_id AND m.driver_id = r.driver_id
),

season_rows AS (
    SELECT
        'season' AS grain,
        CAST(m.race_year AS VARCHAR) AS unit_id,
        m.driver_id,
        m.mean_dirty_air_tax_s AS got_mean,
        m.n_dirty_air_measured_laps AS got_n,
        m.dirty_air_unavailable_reason AS reason,
        r.mean_s AS ref_mean,
        COALESCE(r.n, 0) AS ref_n
    FROM {{ ref('mart_driver_season_summary') }} AS m
    LEFT JOIN season_ref AS r
        ON m.race_year = r.race_year AND m.driver_id = r.driver_id
),

mart_rows AS (
    SELECT * FROM race_rows
    UNION ALL
    SELECT * FROM season_rows
)

SELECT
    grain,
    unit_id,
    driver_id,
    got_mean,
    ref_mean,
    got_n,
    ref_n
FROM mart_rows
WHERE
    got_n IS DISTINCT FROM ref_n
    OR (got_mean IS NULL) <> (ref_mean IS NULL)
    OR ABS(got_mean - ref_mean) > 1e-9
    OR (got_mean IS NOT NULL AND got_n = 0)
    OR (reason IS NULL) <> (got_mean IS NOT NULL)

UNION ALL

SELECT
    'benchmark' AS grain,
    CAST(b.race_year AS VARCHAR) AS unit_id,
    NULL AS driver_id,
    b.mean AS got_mean,
    r.mean_s AS ref_mean,
    b.sample_size AS got_n,
    r.n AS ref_n
FROM {{ ref('mart_metric_benchmark') }} AS b
LEFT JOIN bench_ref AS r ON b.race_year = r.race_year
WHERE
    b.metric_name = 'dirty_air_tax_s'
    AND (
        b.sample_size IS DISTINCT FROM r.n
        OR ABS(b.mean - r.mean_s) > 1e-9
    )
