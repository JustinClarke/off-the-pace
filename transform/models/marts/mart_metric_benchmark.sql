-- Per-metric distribution by season over clean (ml_eligible) laps, so an LLM
-- can say what is typical. Grain: (metric_name, race_year).
{{ config(materialized='table') }}

WITH clean AS (
    SELECT * FROM {{ ref('fct_lap_residuals') }} WHERE ml_eligible = TRUE
),

long AS (
    SELECT race_year, 'driver_skill_residual_s' AS metric_name, driver_skill_residual_s AS v FROM clean
    UNION ALL
    SELECT race_year, 'fuel_component_s', fuel_component_s FROM clean
    UNION ALL
    SELECT race_year, 'compound_component_s', compound_component_s FROM clean
    UNION ALL
    SELECT race_year, 'constructor_component_s', constructor_component_s FROM clean
    UNION ALL
    SELECT race_year, 'dirty_air_tax_s', dirty_air_tax_s FROM clean
    UNION ALL
    SELECT race_year, 'lap_time_s', lap_time_s FROM clean
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
