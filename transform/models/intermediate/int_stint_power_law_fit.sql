-- WI-17: a power-law degradation fit for every stint, y = intercept + alpha *
-- age^beta.
--
-- Grain: stint_id. One row per stint in int_power_law_lap that can be fitted at
-- all (two or more distinct tyre ages and some spread in lap time);
-- fit_eligible marks the spec's stints (>= 8 clean laps and an age span >= 7).
--
-- Method: cross-join the beta grid (0.20-3.00, step 0.05; power_law_beta_grid),
-- fit (intercept, alpha) by OLS at each beta with REGR_SLOPE / REGR_INTERCEPT /
-- REGR_R2 on (age^beta, y), keep the beta with the highest R^2 (smallest beta
-- on a tie).
--
-- Read this as a description of the data, not a target. The WI-17 Step 0 check
-- (ml/src/powerlaw_ceiling.py) found beta on the grid edge for about two stints
-- in three and alpha's reliability ceiling at about zero: over 8-30 laps,
-- lap-time noise is larger than the curve's bend, so alpha and beta trade off
-- against each other. The per-stint R^2 distribution is reported, never gated.
-- The pooled per-cell fit (int_cell_power_law_fit) is the training target.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT
        stint_id,
        race_id,
        race_year,
        driver_id,
        constructor_id,
        compound_label,
        compound_code,
        hardness_era,
        compound_hardness_rank,
        circuit_id,
        CAST(age_in_stint AS DOUBLE) AS age,
        y_s
    FROM {{ ref('int_power_law_lap') }}
),

stints AS (
    SELECT
        stint_id,
        MIN(race_id) AS race_id,
        MIN(race_year) AS race_year,
        MIN(driver_id) AS driver_id,
        MIN(constructor_id) AS constructor_id,
        MIN(compound_label) AS compound_label,
        MIN(compound_code) AS compound_code,
        MIN(hardness_era) AS hardness_era,
        MIN(compound_hardness_rank) AS compound_hardness_rank,
        MIN(circuit_id) AS circuit_id,
        COUNT(*) AS n_laps,
        COUNT(DISTINCT age) AS n_ages,
        MIN(age) AS age_min,
        MAX(age) AS age_max,
        VAR_POP(y_s) AS var_y
    FROM laps
    GROUP BY stint_id
),

fittable AS (
    SELECT * FROM stints
    WHERE n_ages >= 2 AND var_y > 0
),

grid AS ({{ power_law_beta_grid() }}),

fits AS (
    SELECT
        l.stint_id,
        g.beta_k,
        g.beta,
        REGR_SLOPE(l.y_s, POW(l.age, g.beta)) AS alpha_s,
        REGR_INTERCEPT(l.y_s, POW(l.age, g.beta)) AS intercept_s,
        REGR_R2(l.y_s, POW(l.age, g.beta)) AS r2
    FROM laps AS l
    INNER JOIN fittable AS f
        ON l.stint_id = f.stint_id
    CROSS JOIN grid AS g
    GROUP BY l.stint_id, g.beta_k, g.beta
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY stint_id
            ORDER BY r2 DESC, beta_k ASC
        ) AS rn
    FROM fits
),

linear AS (
    SELECT
        stint_id,
        r2 AS r2_linear
    FROM fits
    WHERE beta_k = 20
)

SELECT
    f.stint_id,
    f.race_id,
    f.race_year,
    f.driver_id,
    f.constructor_id,
    f.circuit_id,
    f.compound_label,
    f.compound_code,
    f.hardness_era,
    f.compound_hardness_rank,
    f.n_laps,
    CAST(f.age_min AS INTEGER) AS age_min,
    CAST(f.age_max AS INTEGER) AS age_max,
    r.alpha_s,
    r.beta,
    r.intercept_s,
    r.r2,
    lin.r2_linear,
    r.beta_k IN (4, 60) AS beta_at_grid_edge,
    (f.n_laps >= 8 AND f.age_max - f.age_min >= 7) AS fit_eligible
FROM fittable AS f
INNER JOIN ranked AS r
    ON f.stint_id = r.stint_id AND r.rn = 1
INNER JOIN linear AS lin
    ON f.stint_id = lin.stint_id
