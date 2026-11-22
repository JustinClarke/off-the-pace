-- mart_metric_benchmark's constructor_component_s row counts measured laps
-- only: sample_size equals the ml_eligible laps with NOT
-- constructor_pace_is_filled per race_year, and the mean matches within 1e-9.
-- Returns violating rows.
WITH ref AS (
    SELECT
        race_year,
        COUNT(*) AS n,
        AVG(constructor_component_s) AS mean_s
    FROM {{ ref('fct_lap_residuals') }}
    WHERE ml_eligible = TRUE AND NOT constructor_pace_is_filled
    GROUP BY race_year
)

SELECT
    COALESCE(b.race_year, r.race_year) AS race_year,
    b.sample_size AS got_n,
    r.n AS ref_n,
    b.mean AS got_mean,
    r.mean_s AS ref_mean
FROM (
    SELECT * FROM {{ ref('mart_metric_benchmark') }}
    WHERE metric_name = 'constructor_component_s'
) AS b
FULL OUTER JOIN ref AS r ON b.race_year = r.race_year
WHERE
    b.sample_size IS DISTINCT FROM r.n
    OR ABS(b.mean - r.mean_s) > 1e-9
