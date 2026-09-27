-- T9 (F5, WI-01). Label-stability monitor: a COMPLETED season's label
-- statistics must not move when a later season is ingested and the build
-- re-runs, unless the label version is deliberately bumped. This bump
-- (WI-01, 2026-09-27) IS that deliberate bump: transform/seeds/
-- label_stability_baseline.csv is the frozen snapshot taken right after it,
-- and is the thing to refresh (with a note in the seed's own header and the
-- label-version doc) on the next intentional label change -- not code to
-- silence a real failure here.
--
-- Two checks, one row per failure:
--   'season_label_stats' -- per-season row count / mean of
--     next_5_lap_cumulative_jump_s against the frozen seed.
--   'theta_air_value' -- the theta_air int_dirty_air_tax_component actually
--     applies equals the declared var('theta_air_label_value') within 1e-9
--     s/lap, and is one value. theta sits inside every dirty-air lap's label.
--     Until W40 (2026-09-27) the model fitted theta in SQL and this compared
--     that fit with the var (1e-4), so a re-fit (a new season inside the fit
--     window, a panel change, a fallback firing) surfaced here. Since W40 the
--     model applies the var directly (the value is 06b's F2 fit, run outside
--     dbt), so this now fails only if the model stops reading the var, e.g. a
--     live fit re-introduced. A panel change that would move the F2 fit
--     usually moves the label too and so shows up in 'season_label_stats';
--     it is not guaranteed to (fixes board watch item W47). The bump
--     procedure in the var's dbt_project.yml comment re-runs the fit.
--     theta is read back as the tax on laps whose lagged dirty-air share is 1
--     (the share is binary, so tax = theta there, inside the [0, 5] clamp).
--
-- Warn, not error (per the audit report's severity for this check): a
-- pooled-across-seasons parameter (theta_air, a compound seed refit, ...)
-- moving because someone deliberately re-fit it is a real, reviewable event
-- that should surface, not fail a build outright.
--
-- The season check excludes the latest ingested season: a season still
-- receiving new races is expected to have moving label statistics as rows are
-- added (more laps, more stints), which is not the F5 defect (a pooled
-- parameter silently recomputed over an ever-growing pool of ALREADY-COMPLETE
-- seasons).
--
-- Statistics are on next_5_lap_cumulative_jump_s (the primary trained
-- target): driver_skill_residual_s itself is an intermediate column, not
-- exposed on this mart.
{{ config(severity='warn') }}

WITH current_stats AS (
    SELECT
        race_year,
        COUNT(*) FILTER (WHERE next_5_lap_cumulative_jump_s IS NOT NULL) AS row_count,
        ROUND(AVG(next_5_lap_cumulative_jump_s), 4) AS mean_next_5_lap_jump_s
    FROM {{ ref('fct_cliff_prediction_features') }}
    WHERE race_year < (SELECT MAX(race_year) FROM {{ ref('fct_cliff_prediction_features') }})
    GROUP BY race_year
),

theta AS (
    SELECT
        MAX(dirty_air_tax_s) AS theta_max,
        MIN(dirty_air_tax_s) AS theta_min
    FROM {{ ref('int_dirty_air_tax_component') }}
    WHERE dirty_air_intensity_lag1 = 1.0
)

SELECT
    'season_label_stats' AS check_name,
    CAST(cs.race_year AS VARCHAR) AS scope,
    cs.row_count AS observed_row_count,
    b.row_count AS expected_row_count,
    cs.mean_next_5_lap_jump_s AS observed_value,
    b.mean_next_5_lap_jump_s AS expected_value
FROM current_stats AS cs
INNER JOIN {{ ref('label_stability_baseline') }} AS b ON cs.race_year = b.race_year
WHERE
    cs.row_count != b.row_count
    OR ABS(cs.mean_next_5_lap_jump_s - b.mean_next_5_lap_jump_s) > 0.001

UNION ALL

SELECT
    'theta_air_value' AS check_name,
    'all' AS scope,
    NULL AS observed_row_count,
    NULL AS expected_row_count,
    t.theta_max AS observed_value,
    {{ var('theta_air_label_value') }} AS expected_value
FROM theta AS t
WHERE
    t.theta_max IS NULL
    OR t.theta_max - t.theta_min > 1e-9
    OR ABS(t.theta_max - {{ var('theta_air_label_value') }}) > 1e-9
