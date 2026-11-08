-- Per-metric distribution by season over clean (ml_eligible) laps, so an LLM
-- can say what is typical. Grain: (metric_name, race_year).
-- TX-03: the dirty_air_tax_s row is over laps with a MEASURED dirty-air tax
-- only (a row in int_dirty_air_tax_component with a non-NULL tax).
-- fct_lap_residuals writes 0.0 on laps with no such row; counting those as
-- clean air pulled the mean down. The other five metrics are unchanged.
{{ config(materialized='table') }}

WITH clean AS (
    SELECT * FROM {{ ref('fct_lap_residuals') }}
    WHERE ml_eligible = TRUE
),

long AS (
    SELECT
        race_year,
        'driver_skill_residual_s' AS metric_name,
        driver_skill_residual_s AS v
    FROM clean
    UNION ALL
    SELECT
        race_year,
        'fuel_component_s' AS metric_name,
        fuel_component_s AS v
    FROM clean
    UNION ALL
    SELECT
        race_year,
        'compound_component_s' AS metric_name,
        compound_component_s AS v
    FROM clean
    UNION ALL
    SELECT
        race_year,
        'constructor_component_s' AS metric_name,
        constructor_component_s AS v
    FROM clean
    UNION ALL
    SELECT
        c.race_year,
        'dirty_air_tax_s' AS metric_name,
        c.dirty_air_tax_s AS v
    FROM clean AS c
    INNER JOIN {{ ref('int_dirty_air_tax_component') }} AS da
        ON c.lap_id = da.lap_id
    WHERE da.dirty_air_tax_s IS NOT NULL
    UNION ALL
    SELECT
        race_year,
        'lap_time_s' AS metric_name,
        lap_time_s AS v
    FROM clean
)

SELECT
    metric_name,
    race_year,
    QUANTILE_CONT(v, 0.05) AS p05,
    QUANTILE_CONT(v, 0.50) AS p50,
    QUANTILE_CONT(v, 0.95) AS p95,
    AVG(v) AS mean,
    STDDEV(v) AS sd,
    's' AS unit,
    COUNT(v) AS sample_size
FROM long
WHERE v IS NOT NULL
GROUP BY metric_name, race_year
ORDER BY metric_name, race_year
