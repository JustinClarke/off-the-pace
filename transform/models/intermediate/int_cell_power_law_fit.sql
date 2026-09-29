-- WI-17: the pooled power-law degradation fit, one per race x compound hardness
-- rank. This is the training target for ml/src/powerlaw.py (via
-- fct_power_law_training).
--
-- Grain: (race_id, compound_hardness_rank). Every cell with at least one
-- qualifying stint; fit_eligible marks the cells the model trains on (>= 3
-- qualifying stints and >= 40 laps). A qualifying stint has >= 5 laps in
-- int_power_law_lap over >= 2 distinct tyre ages. 2025 forms no cells: its
-- compound_code, and so its hardness rank, is NULL until tyre_allocations
-- carries verified 2025 rows (W50).
--
-- Model: y = c_stint + alpha * age^beta. Each stint keeps its own intercept
-- (driver, car, fuel-model error, stint start), so only the shape within stints
-- identifies the curve. Demeaning within the stint removes c_stint; beta is
-- profiled on the grid (power_law_beta_grid) and alpha is OLS through the
-- origin on the demeaned data: alpha(beta) = sum(xd * yd) / sum(xd^2),
-- SSE(beta) = sum(yd^2) - sum(xd * yd)^2 / sum(xd^2) with the smallest SSE kept
-- (smallest beta on a tie). r2_within = 1 - SSE / sum(yd^2).
-- ml/src/powerlaw_fit.py implements the same arithmetic in numpy for the Step-0
-- bootstrap.
--
-- alpha is not constrained to be >= 0: on y = fuel-corrected lap time, track
-- evolution can outrun tyre wear, and about one cell in five fits a curve that
-- falls with age. The target keeps that, so the model learns the true mean. The
-- simulator clamps the curve at inference
-- (app/src/features/degradation-simulator/powerLaw.ts).
--
-- curve_incr_{a}_s = alpha * (a^beta - 2^beta): seconds over the fresh-tyre
-- pace at age 2, the simulator's anchor (its ref_green_pace_s is the median lap
-- at tyre age <= 2, which is almost always age 2 because the age-1 lap is the
-- out-lap). Step 0 found these far better identified than alpha or beta
-- themselves (reliability ceiling ~0.6-0.75 against alpha ~0).
{{ config(materialized='table') }}

{#- the fresh-tyre anchor age (ml/src/powerlaw_fit.py FRESH_ANCHOR_AGE) -#}
{% set anchor = '2.0' %}

WITH laps AS (
    SELECT
        race_id,
        race_year,
        circuit_id,
        hardness_era,
        compound_hardness_rank,
        compound_label,
        compound_code,
        stint_id,
        CAST(age_in_stint AS DOUBLE) AS age,
        y_s
    FROM {{ ref('int_power_law_lap') }}
    WHERE compound_hardness_rank IS NOT NULL
),

stint_q AS (
    SELECT
        stint_id,
        COUNT(*) AS n_laps,
        COUNT(DISTINCT age) AS n_ages
    FROM laps
    GROUP BY stint_id
),

qual AS (
    SELECT l.*
    FROM laps AS l
    INNER JOIN stint_q AS q
        ON l.stint_id = q.stint_id
    WHERE q.n_laps >= 5 AND q.n_ages >= 2
),

cells AS (
    SELECT
        race_id,
        compound_hardness_rank,
        MIN(race_year) AS race_year,
        MIN(circuit_id) AS circuit_id,
        MIN(hardness_era) AS hardness_era,
        MIN(compound_label) AS compound_label,
        MIN(compound_code) AS compound_code,
        COUNT(DISTINCT compound_label) AS n_compound_labels,
        COUNT(DISTINCT stint_id) AS n_stints,
        COUNT(*) AS n_laps,
        CAST(MIN(age) AS INTEGER) AS age_min,
        CAST(MAX(age) AS INTEGER) AS age_max
    FROM qual
    GROUP BY race_id, compound_hardness_rank
),

grid AS ({{ power_law_beta_grid() }}),

gridded AS (
    SELECT
        q.race_id,
        q.compound_hardness_rank,
        q.stint_id,
        g.beta_k,
        g.beta,
        POW(q.age, g.beta) AS x,
        q.y_s AS y
    FROM qual AS q
    CROSS JOIN grid AS g
),

demeaned AS (
    SELECT
        race_id,
        compound_hardness_rank,
        beta_k,
        beta,
        x - AVG(x) OVER (PARTITION BY stint_id, beta_k) AS xd,
        y - AVG(y) OVER (PARTITION BY stint_id, beta_k) AS yd
    FROM gridded
),

sums AS (
    SELECT
        race_id,
        compound_hardness_rank,
        beta_k,
        beta,
        SUM(xd * xd) AS sxx,
        SUM(xd * yd) AS sxy,
        SUM(yd * yd) AS syy
    FROM demeaned
    GROUP BY race_id, compound_hardness_rank, beta_k, beta
),

fits AS (
    SELECT
        *,
        sxy / sxx AS alpha_s,
        syy - sxy * sxy / sxx AS sse
    FROM sums
    WHERE sxx > 0 AND syy > 0
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY race_id, compound_hardness_rank
            ORDER BY sse ASC, beta_k ASC
        ) AS rn
    FROM fits
)

SELECT
    c.race_id || '_r' || CAST(c.compound_hardness_rank AS VARCHAR) AS cell_id,
    c.race_id,
    c.race_year,
    c.circuit_id,
    c.hardness_era,
    c.compound_hardness_rank,
    c.compound_label,
    c.compound_code,
    c.n_compound_labels,
    c.n_stints,
    c.n_laps,
    c.age_min,
    c.age_max,
    r.alpha_s,
    r.beta,
    1.0 - r.sse / r.syy AS r2_within,
    r.beta_k IN (4, 60) AS beta_at_grid_edge,
    r.alpha_s * (POW(5.0, r.beta) - POW({{ anchor }}, r.beta))
        AS curve_incr_5_s,
    r.alpha_s * (POW(10.0, r.beta) - POW({{ anchor }}, r.beta))
        AS curve_incr_10_s,
    r.alpha_s * (POW(15.0, r.beta) - POW({{ anchor }}, r.beta))
        AS curve_incr_15_s,
    r.alpha_s * (POW(20.0, r.beta) - POW({{ anchor }}, r.beta))
        AS curve_incr_20_s,
    (c.n_stints >= 3 AND c.n_laps >= 40) AS fit_eligible
FROM cells AS c
INNER JOIN ranked AS r
    ON
        c.race_id = r.race_id
        AND c.compound_hardness_rank = r.compound_hardness_rank
        AND r.rn = 1
