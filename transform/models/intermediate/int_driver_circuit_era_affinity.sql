-- Driver × circuit × era affinity: "equal-car track record" by regulation era.
--
-- Same shrinkage framework as int_driver_circuit_affinity, but the (driver,
-- circuit)
-- cell is split on the 2022 ground-effect regulation boundary so a driver's
-- track
-- record is never blended across incomparable car eras. Within each era the
-- residual
-- is car-removed via a de-biased modelled constructor term
-- (driver_skill_field_s
-- from int_driver_race_skill_loro), so ranking drivers by shrunk_affinity_s
-- within
-- one era ≈ "how good is this driver at this circuit in equal machinery".
--
-- Signal: driver_skill_field_s = driver_median_pace_delta_s − car_fe_s, where
-- car_fe_s
-- is the de-biased constructor×race fixed effect (car pace net of driver skill)
-- from
-- int_constructor_car_fe (see int_driver_race_skill_loro). This replaces the
-- LORO
-- teammate-relative baseline used by the broader rating chain, which inflated
-- drivers
-- paired with weak teammates (e.g. Albon/Sargeant at Zandvoort); the old
-- field-anchored
-- variant (subtracting the constructor median) still leaked because that median
-- absorbs
-- the team's driver skill the FE's global driver anchor fixes that.
--
-- Eras (matching int_era_normalized_driver_rating):
--   era_key='pre2022'  → 2018–2021 (last-gen aero regs)
--   era_key='post2022' → 2022–2024 (ground-effect regs)
--
-- For each (driver, circuit, era) the observed per-cell mean is shrunk toward
-- the
-- driver's *within-era* global mean via the normal-normal conjugate posterior
-- (prior_weight = 5 virtual races). Variance components are pooled within each
-- era.
--
-- n_obs=1 cells get no shrunk estimate (NULL shrunk_affinity_s/se/CI): a
-- single race is one data point, not a track record, and the posterior at
-- that n is prior-dominated enough (affinity_confidence ~0.17) to be
-- misleading rather than merely uncertain. raw_affinity_s and
-- affinity_confidence stay populated since they don't claim to be a track
-- record estimate.
--
-- Output grain: (driver_id, circuit_id, era_key). PK: driver_circuit_era_id.
-- circuit_id is the physical-circuit identifier (slug of circuit_name), so
-- renamed events
-- and double-headers at one venue pool into a single track record instead of
-- appearing as
-- separate event-keyed rows.
--
-- Sign convention: negative _s = faster than field (same as
-- driver_skill_residual_s).
-- affinity_confidence = n_obs / (n_obs + prior_weight) ∈ [0, 1].
--   Below ~0.17 (1 race, prior_weight=5) the posterior is prior-dominated.

{{ config(materialized='table', tags=['driver_rating', 'driver_affinity']) }}

{% set era_boundary = 2022 %}

{# Map event slug (circuit_key) → physical circuit_id + a canonical #}
{# display name. #}
WITH circuit_map AS (
    SELECT
        circuit_key,
        {{ circuit_id_from_name('circuit_name') }} AS circuit_id,
        circuit_name
    FROM {{ ref('circuit_reference') }}
),

-- One canonical display name per physical circuit (names are identical across
-- the
-- event slugs that share a venue, so MIN is deterministic and lossless).
circuit_name_map AS (
    SELECT circuit_id, MIN(circuit_name) AS circuit_name
    FROM circuit_map
    GROUP BY circuit_id
),

driver_race AS (
    -- Field-anchored equal-car skill: median pace delta minus the de-biased car
    -- FE
    -- (int_driver_race_skill_loro.driver_skill_field_s). Aliased so the
    -- shrinkage
    -- logic below is unchanged. Replaces the LORO teammate-relative baseline to
    -- fix
    -- the weak-teammate inflation confound. See int_driver_race_skill_loro.
    SELECT
        f.driver_id,
        COALESCE(cm.circuit_id, f.circuit_key) AS circuit_id,
        f.race_year,
        f.race_id,
        f.driver_skill_field_s AS driver_residual_mean_s,
        f.clean_lap_count,
        CASE
            WHEN f.race_year < {{ era_boundary }} THEN 'pre2022' ELSE 'post2022'
        END
            AS era_key
    FROM {{ ref('int_driver_race_skill_loro') }} AS f
    LEFT JOIN circuit_map AS cm ON f.circuit_key = cm.circuit_key
    WHERE
        f.driver_skill_field_s IS NOT NULL
        AND f.circuit_key IS NOT NULL
),

-- Per (driver, circuit, era): observed mean and sample count
driver_circuit_obs AS (
    SELECT
        driver_id,
        circuit_id,
        era_key,
        COUNT(*) AS n_obs,
        COUNT(DISTINCT race_year) AS seasons_observed_n,
        AVG(driver_residual_mean_s) AS raw_affinity_s,
        STDDEV(driver_residual_mean_s) AS within_cell_stddev_s,
        SUM(clean_lap_count) AS total_clean_laps
    FROM driver_race
    GROUP BY driver_id, circuit_id, era_key
),

-- Per (driver, era): global mean across all circuits in that era (the prior
-- mean)
driver_global AS (
    SELECT
        driver_id,
        era_key,
        AVG(driver_residual_mean_s) AS global_driver_mean_s,
        STDDEV(driver_residual_mean_s) AS global_driver_stddev_s,
        COUNT(*) AS total_race_n
    FROM driver_race
    GROUP BY driver_id, era_key
),

-- Variance components pooled *within each era*:
-- σ²_residual: within-cell variance (observation noise)
-- σ²_prior:    between-cell variance (prior spread)
variance_components AS (
    SELECT
        era_key,
        AVG(POWER(COALESCE(within_cell_stddev_s, 0), 2)) AS sigma2_residual,
        STDDEV(raw_affinity_s) AS sigma_prior_approx
    FROM driver_circuit_obs
    GROUP BY era_key
),

with_shrinkage AS (
    SELECT
        dco.driver_id,
        dco.circuit_id,
        cnm.circuit_name,
        dco.era_key,
        dco.n_obs,
        dco.seasons_observed_n,
        dco.raw_affinity_s,

        -- Bayesian posterior mean (shrinkage toward the driver's within-era
        -- global mean). Requires >= 2 races at this circuit/era: a single
        -- race isn't a track record.
        CASE
            WHEN dco.n_obs >= 2
                THEN {{ bayesian_shrinkage(
                    'dco.n_obs',
                    'dco.raw_affinity_s',
                    'dg.global_driver_mean_s',
                    '5'
                ) }}
        END                                AS shrunk_affinity_s,

        -- Posterior variance (σ²_residual / n and σ²_prior, per era). Gated
        -- with shrunk_affinity_s so shrunk_affinity_se_s is NULL, not just
        -- the CI bounds, at n_obs < 2.
        CASE
            WHEN dco.n_obs >= 2
                THEN {{ posterior_variance(
                    'dco.n_obs',
                    'NULLIF(vc.sigma2_residual, 0)',
                    'NULLIF(POWER(vc.sigma_prior_approx, 2), 0)'
                ) }}
        END                                AS posterior_var_s2,

        dg.global_driver_mean_s,

        -- Confidence: fraction of posterior mass from data vs prior
        CAST(dco.n_obs AS DOUBLE)
        / NULLIF(dco.n_obs + 5, 0) AS affinity_confidence

    FROM driver_circuit_obs AS dco
    INNER JOIN
        driver_global AS dg
        ON dco.driver_id = dg.driver_id AND dco.era_key = dg.era_key
    INNER JOIN variance_components AS vc ON dco.era_key = vc.era_key
    INNER JOIN circuit_name_map AS cnm ON dco.circuit_id = cnm.circuit_id
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'driver_id', 'circuit_id', 'era_key'
    ]) }}
        AS driver_circuit_era_id,
    driver_id,
    circuit_id,
    circuit_name,
    era_key,
    CASE era_key
        WHEN 'pre2022' THEN '2018–2021'
        WHEN 'post2022' THEN '2022–2024'
    END AS era_label,
    n_obs,
    seasons_observed_n,
    raw_affinity_s,
    shrunk_affinity_s,

    -- Posterior SE and 95% credible interval
    SQRT(NULLIF(posterior_var_s2, 0)) AS shrunk_affinity_se_s,
    shrunk_affinity_s - 1.96 * SQRT(NULLIF(posterior_var_s2, 0))
        AS shrunk_affinity_ci_low_s,
    shrunk_affinity_s + 1.96 * SQRT(NULLIF(posterior_var_s2, 0))
        AS shrunk_affinity_ci_high_s,

    affinity_confidence,

    -- Shrinkage bounds identity check columns (for singular test). NULL
    -- alongside shrunk_affinity_s -- a bound with nothing to check against
    -- is meaningless, not just unused.
    CASE
        WHEN n_obs >= 2 THEN LEAST(raw_affinity_s, global_driver_mean_s)
    END AS _shrinkage_lower_bound,
    CASE
        WHEN n_obs >= 2 THEN GREATEST(raw_affinity_s, global_driver_mean_s)
    END AS _shrinkage_upper_bound

FROM with_shrinkage
ORDER BY era_key, circuit_id, shrunk_affinity_s
