-- TX-05: mart_build_provenance has exactly one row, and its var-sourced columns match
-- dbt_project.yml. Returns a row per failed check.
WITH p AS (
    SELECT * FROM {{ ref('mart_build_provenance') }}
),

n AS (
    SELECT COUNT(*) AS n_rows FROM p
)

SELECT
    'row_count' AS check_name,
    CAST(n_rows AS VARCHAR) AS detail
FROM n
WHERE n_rows <> 1

UNION ALL

SELECT
    'vars_mismatch' AS check_name,
    label_version AS detail
FROM p
WHERE
    label_version IS DISTINCT FROM '{{ var("label_version") }}'
    OR label_sealed_on IS DISTINCT FROM CAST('{{ var("label_sealed_on") }}' AS DATE)
    OR theta_air_label_value IS DISTINCT FROM CAST({{ var('theta_air_label_value') }} AS DOUBLE)
    OR theta_air_fit_season_max IS DISTINCT FROM {{ var('theta_air_fit_season_max') }}
    OR dirty_air_method IS DISTINCT FROM '{{ var("dirty_air_method") }}'
    OR era_boundary IS DISTINCT FROM {{ var('era_boundary') }}
    OR holdout_season IS DISTINCT FROM {{ var('holdout_season') }}
