-- Fourth-iteration intermediate: per-(driver, season) shrunk residual.
--
-- Aggregates race-grain skill residuals to driver-season grain, then applies
-- Bayesian shrinkage toward the season mean (prior_weight = 5 virtual races).
--
-- This is the first era rating iteration of the era normalisation chain. The subsequent era rating offset iteration
-- lives in int_era_normalized_driver_rating, which consumes this model.
--
-- Output grain: (driver_id, race_year). One row per driver per season.
-- PK: driver_season_id (surrogate hash).
--
-- Sign convention: negative residual = faster than field (same as upstream).
-- shrunk_residual_s pulls the observed season mean toward the league average.

{{ config(materialized='table', tags=['driver_rating', 'era_rating']) }}

WITH driver_race AS (
    SELECT
        driver_id,
        race_year,
        race_id,
        driver_residual_mean_s,
        clean_lap_count
    FROM {{ ref('fct_driver_skill_features') }}
    WHERE driver_residual_mean_s IS NOT NULL
),

-- Per (driver, season): aggregate to season grain
driver_season_obs AS (
    SELECT
        driver_id,
        race_year,
        COUNT(*)                                          AS n_races,
        SUM(clean_lap_count)                              AS total_clean_laps_n,
        AVG(driver_residual_mean_s)                       AS raw_residual_mean_s,
        STDDEV(driver_residual_mean_s)                    AS residual_stddev_s,
        COUNT(DISTINCT race_id)                           AS races_completed_n
    FROM driver_race
    GROUP BY driver_id, race_year
),

-- Season mean: league-wide average for the prior (one row per season)
season_means AS (
    SELECT
        race_year,
        AVG(raw_residual_mean_s)       AS season_mean_s,
        STDDEV(raw_residual_mean_s)    AS season_stddev_s,
        COUNT(*)                       AS drivers_in_season_n
    FROM driver_season_obs
    GROUP BY race_year
),

-- Variance components for posterior CI
variance_components AS (
    SELECT
        AVG(POWER(COALESCE(residual_stddev_s, 0), 2)) AS sigma2_residual,
        STDDEV(raw_residual_mean_s)                    AS sigma_prior_approx
    FROM driver_season_obs
),

with_shrinkage AS (
    SELECT
        dso.driver_id,
        dso.race_year,
        dso.n_races,
        dso.total_clean_laps_n,
        dso.raw_residual_mean_s,
        dso.residual_stddev_s,
        dso.races_completed_n,
        sm.season_mean_s,

        -- Posterior mean: shrink toward season mean
        {{ bayesian_shrinkage(
            'dso.n_races',
            'dso.raw_residual_mean_s',
            'sm.season_mean_s',
            '5'
        ) }}                           AS shrunk_residual_s,

        -- Posterior variance for CI
        {{ posterior_variance(
            'dso.n_races',
            'NULLIF(vc.sigma2_residual, 0)',
            'NULLIF(POWER(vc.sigma_prior_approx, 2), 0)'
        ) }}                           AS posterior_var_s2,

        -- Confidence: fraction of posterior from data vs prior
        CAST(dso.n_races AS DOUBLE)
            / NULLIF(dso.n_races + 5, 0)    AS rating_confidence

    FROM driver_season_obs dso
    JOIN season_means      sm   USING (race_year)
    CROSS JOIN variance_components vc
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['driver_id', 'CAST(race_year AS VARCHAR)']) }}
                                            AS driver_season_id,
    driver_id,
    race_year                               AS season,
    n_races,
    total_clean_laps_n,
    races_completed_n,
    raw_residual_mean_s,
    residual_stddev_s,
    season_mean_s,
    shrunk_residual_s,

    SQRT(NULLIF(posterior_var_s2, 0))       AS shrunk_residual_se_s,
    shrunk_residual_s-1.96 * SQRT(NULLIF(posterior_var_s2, 0))
                                            AS shrunk_residual_ci_low_s,
    shrunk_residual_s + 1.96 * SQRT(NULLIF(posterior_var_s2, 0))
                                            AS shrunk_residual_ci_high_s,

    rating_confidence,

    -- Bounds for shrinkage identity test
    LEAST(raw_residual_mean_s, season_mean_s)    AS _shrinkage_lower_bound,
    GREATEST(raw_residual_mean_s, season_mean_s) AS _shrinkage_upper_bound

FROM with_shrinkage
ORDER BY driver_id, season
