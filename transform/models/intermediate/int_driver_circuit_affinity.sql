-- Driver circuit affinity model: Driver × circuit affinity via Bayesian shrinkage.
--
-- For each (driver, circuit) pair, computes a shrunk residual estimate
-- pulling the observed per-circuit mean toward the driver's global mean
-- using the normal-normal conjugate posterior (prior_weight = 5 virtual races).
--
-- Identification: within-driver, between-circuit variation. Same driver observed
-- at the same circuit across multiple seasons. The shrinkage framework separates
-- systematic circuit affinity from single-race variance.
--
-- Output grain: (driver_id, circuit_key). One row per driver-circuit pair.
-- PK: driver_circuit_id (surrogate hash).
--
-- Sign convention: negative _s = faster than driver's mean (same as driver_skill_residual_s).
-- affinity_confidence: n_obs / (n_obs + prior_weight) in [0, 1].
--   Values below ~0.17 (1 race, prior_weight=5) mean posterior is prior-dominated.

{{ config(materialized='table', tags=['driver_rating', 'driver_affinity']) }}

WITH driver_race AS (
    SELECT
        driver_id,
        circuit_key,
        race_year,
        race_id,
        driver_residual_mean_s,
        clean_lap_count
    FROM {{ ref('fct_driver_skill_features') }}
    WHERE driver_residual_mean_s IS NOT NULL
      AND circuit_key            IS NOT NULL
),

-- Per (driver, circuit): observed mean and sample count
driver_circuit_obs AS (
    SELECT
        driver_id,
        circuit_key,
        COUNT(*)                          AS n_obs,
        COUNT(DISTINCT race_year)         AS seasons_observed_n,
        AVG(driver_residual_mean_s)       AS raw_affinity_s,
        STDDEV(driver_residual_mean_s)    AS within_cell_stddev_s,
        SUM(clean_lap_count)              AS total_clean_laps
    FROM driver_race
    GROUP BY driver_id, circuit_key
),

-- Per driver: global mean across all circuits (the prior mean for each cell)
driver_global AS (
    SELECT
        driver_id,
        AVG(driver_residual_mean_s)    AS global_driver_mean_s,
        STDDEV(driver_residual_mean_s) AS global_driver_stddev_s,
        COUNT(*)                       AS total_race_n
    FROM driver_race
    GROUP BY driver_id
),

-- Global variance components (pooled):
-- σ²_residual: within-cell variance (observation noise)
-- σ²_prior:    between-driver variance (prior spread)
variance_components AS (
    SELECT
        AVG(POWER(COALESCE(within_cell_stddev_s, 0), 2)) AS sigma2_residual,
        STDDEV(raw_affinity_s)                            AS sigma_prior_approx
    FROM driver_circuit_obs
),

with_shrinkage AS (
    SELECT
        dco.driver_id,
        dco.circuit_key,
        dco.n_obs,
        dco.seasons_observed_n,
        dco.raw_affinity_s,

        -- Bayesian posterior mean (shrinkage toward driver global mean)
        {{ bayesian_shrinkage(
            'dco.n_obs',
            'dco.raw_affinity_s',
            'dg.global_driver_mean_s',
            '5'
        ) }}                               AS shrunk_affinity_s,

        -- Posterior variance using macro (σ²_residual / n and σ²_prior)
        {{ posterior_variance(
            'dco.n_obs',
            'NULLIF(vc.sigma2_residual, 0)',
            'NULLIF(POWER(vc.sigma_prior_approx, 2), 0)'
        ) }}                               AS posterior_var_s2,

        dg.global_driver_mean_s,

        -- Confidence: fraction of posterior mass from data vs prior
        CAST(dco.n_obs AS DOUBLE)
            / NULLIF(dco.n_obs + 5, 0)    AS affinity_confidence

    FROM driver_circuit_obs dco
    JOIN driver_global      dg  USING (driver_id)
    CROSS JOIN variance_components vc
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['driver_id', 'circuit_key']) }}
                                        AS driver_circuit_id,
    driver_id,
    circuit_key,
    n_obs,
    seasons_observed_n,
    raw_affinity_s,
    shrunk_affinity_s,

    -- Posterior SE and 95% CI
    SQRT(NULLIF(posterior_var_s2, 0))   AS shrunk_affinity_se_s,
    shrunk_affinity_s-1.96 * SQRT(NULLIF(posterior_var_s2, 0))
                                        AS shrunk_affinity_ci_low_s,
    shrunk_affinity_s + 1.96 * SQRT(NULLIF(posterior_var_s2, 0))
                                        AS shrunk_affinity_ci_high_s,

    affinity_confidence,

    -- Shrinkage bounds identity check columns (for singular test)
    LEAST(raw_affinity_s, global_driver_mean_s)    AS _shrinkage_lower_bound,
    GREATEST(raw_affinity_s, global_driver_mean_s) AS _shrinkage_upper_bound

FROM with_shrinkage
ORDER BY driver_id, circuit_key
