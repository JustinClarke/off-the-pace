-- mart_build_provenance · marts · grain: exactly one row per build (TX-05).
-- Which label, coefficients, data window and dbt run produced this
-- warehouse, so every published number can name its provenance. Values come
-- from the dbt_project.yml vars, the data (fct_lap_residuals, race_to_track)
-- and the dbt invocation. dbt cannot read git: the app export adds git_sha
-- and git_dirty. built_at and dbt_invocation_id change on every build; the
-- byte oracle excludes them (VOLATILE_COLS, scripts/snapshot_model_hashes.py).
{{ config(materialized='table') }}

WITH lap_window AS (
    SELECT
        MIN(race_year) AS data_season_min,
        MAX(race_year) AS data_season_max,
        COUNT(DISTINCT race_id) AS n_races
    FROM {{ ref('fct_lap_residuals') }}
),

scheduled AS (
    SELECT COUNT(DISTINCT race_id) AS n_races_scheduled
    FROM {{ ref('race_to_track') }}
)

SELECT
    CAST('{{ var("label_version") }}' AS VARCHAR) AS label_version,
    CAST('{{ var("label_sealed_on") }}' AS DATE) AS label_sealed_on,
    CAST({{ var('theta_air_label_value') }} AS DOUBLE) AS theta_air_label_value,
    CAST({{ var('theta_air_fit_season_max') }} AS INTEGER)
        AS theta_air_fit_season_max,
    CAST('{{ var("dirty_air_method") }}' AS VARCHAR) AS dirty_air_method,
    CAST({{ var('era_boundary') }} AS INTEGER) AS era_boundary,
    CAST({{ var('holdout_season') }} AS INTEGER) AS holdout_season,
    CAST(lw.data_season_min AS INTEGER) AS data_season_min,
    CAST(lw.data_season_max AS INTEGER) AS data_season_max,
    CAST(lw.n_races AS INTEGER) AS n_races,
    CAST(s.n_races_scheduled AS INTEGER) AS n_races_scheduled,
    -- No promoted ML model yet (XM); v17 per D11 / HD8 once one is promoted.
    CAST(NULL AS VARCHAR) AS model_version,
    CAST('{{ invocation_id }}' AS VARCHAR) AS dbt_invocation_id,
    CAST('{{ run_started_at }}' AS TIMESTAMPTZ) AS built_at,
    CAST('{{ dbt_version }}' AS VARCHAR) AS dbt_version
FROM lap_window AS lw
CROSS JOIN scheduled AS s
