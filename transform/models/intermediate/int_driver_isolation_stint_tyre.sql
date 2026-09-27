-- Driver isolation, tier 1's stint layer: each stint's pace line. Grain: one
-- row per stint with at least one Ω lap, PK stint_id.
--
-- THE LINE. Fitted on the stint's line laps: Ω laps in tyre_phase early or mid
-- (so no tyre past its cliff), not on the recovery overlay, with a car term
-- (p NOT NULL):
--   line_slope_s_per_lap2  beta_s = REGR_SLOPE(p, age_in_stint), s/lap per lap
--                          of tyre age; > 0 = his isolated pace RISES through
--                          the stint
--   line_mean_pace_gain_s  p_bar = AVG(p);  line_mean_age_laps = AVG(age)
--   line_ref_age_laps      age_ref = MIN(age), the first clean lap.
-- The slope needs n_line_laps >= var('isolation_min_stint_laps') and Sxx > 0,
-- else it is NULL. DuckDB's REGR_SLOPE returns NaN, not NULL, when n < 2 or
-- Sxx = 0, so the guard is a CASE on the counts, never a COALESCE (WI-02a's
-- T29 is about exactly this class).
--
-- NOISE, PER SEASON (a CTE, not hard-coded). season_sigma_w_s is the pooled SD
-- of p around its stint line (sum of squared line residuals over sum of
-- n - 2); season_rho1 the pooled lag-1 autocorrelation of those residuals over
-- adjacent laps; season_neff_factor f = (1 - rho+)/(1 + rho+) with
-- rho+ = GREATEST(rho1, 0), the effective-sample factor every downstream SE
-- uses (floored at rho = 0 so negative autocorrelation is never read as more
-- information than independent laps).
--   line_slope_se_s_per_lap2       sigma_w / SQRT(Sxx * f)
--
-- Sign: every *_gain_s here is seconds, positive = faster. Slopes are s/lap^2
-- as named. Leakage: a function of the residual trajectory. No ML-contract
-- mart may depend on it (T48).

{{ config(materialized='table', tags=['driver_isolation']) }}

{%- set min_peer_cliff_laps = 10 %}

WITH laps AS (
    SELECT * FROM {{ ref('int_driver_isolation_lap_pace') }}
),

stints AS (
    -- Every attribute here is constant within a stint, so it is grouped on
    -- rather than picked with ANY_VALUE: a stint that ever carried two values
    -- would duplicate here and fail the stint_id unique test instead of
    -- silently keeping one (the F16 lesson).
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        constructor_id,
        stint_number,
        compound,
        era,
        COUNT(*) AS n_omega_laps,
        COUNT(*) FILTER (WHERE tyre_phase = 'cliff') AS n_cliff_laps,
        COUNT(pace_isolated_gain_s) AS n_pace_laps
    FROM laps
    GROUP BY
        stint_id,
        race_year,
        race_id,
        driver_id,
        constructor_id,
        stint_number,
        compound,
        era
),

line_laps AS (
    SELECT *
    FROM laps
    WHERE
        tyre_phase IN ('early', 'mid')
        AND NOT is_recovery
        AND pace_isolated_gain_s IS NOT NULL
),

line_fit AS (
    SELECT
        stint_id,
        COUNT(*) AS n_line_laps,
        AVG(pace_isolated_gain_s) AS line_mean_pace_gain_s,
        AVG(age_in_stint) AS line_mean_age_laps,
        MIN(age_in_stint) AS line_ref_age_laps,
        REGR_SXX(pace_isolated_gain_s, age_in_stint) AS line_age_sxx,
        REGR_SYY(pace_isolated_gain_s, age_in_stint) AS line_pace_syy,
        REGR_SXY(pace_isolated_gain_s, age_in_stint) AS line_sxy,
        REGR_SLOPE(pace_isolated_gain_s, age_in_stint) AS slope_unguarded
    FROM line_laps
    GROUP BY stint_id
),

line AS (
    SELECT
        s.*,
        COALESCE(f.n_line_laps, 0) AS n_line_laps,
        f.line_mean_pace_gain_s,
        f.line_mean_age_laps,
        f.line_ref_age_laps,
        f.line_age_sxx,
        CASE
            WHEN
                f.n_line_laps >= {{ var('isolation_min_stint_laps') }}
                AND f.line_age_sxx > 0
                THEN f.slope_unguarded
        END AS line_slope_s_per_lap2,
        -- Residual sum of squares around the fitted line (Syy - Sxy^2 / Sxx),
        -- for the pooled sigma_w; GREATEST guards a -1e-15 rounding result.
        CASE
            WHEN
                f.line_pace_syy IS NULL
                OR f.line_sxy IS NULL
                OR f.line_age_sxx IS NULL
                THEN NULL
            WHEN
                f.n_line_laps >= {{ var('isolation_min_stint_laps') }}
                AND f.line_age_sxx > 0
                THEN GREATEST(
                    f.line_pace_syy - f.line_sxy * f.line_sxy / f.line_age_sxx,
                    0.0
                )
        END AS line_ssr
    FROM stints AS s
    LEFT JOIN line_fit AS f
        ON s.stint_id = f.stint_id
),

-- Line residuals on the line laps of stints that have a line, for the
-- per-season lag-1 autocorrelation. Adjacent means lap_number exactly one
-- apart, so a gap left by a lap that failed Ω does not count as a lag-1 pair.
line_resid AS (
    SELECT
        ll.stint_id,
        l.race_year,
        ll.lap_number,
        ll.pace_isolated_gain_s
        - (
            l.line_mean_pace_gain_s
            + l.line_slope_s_per_lap2 * (ll.age_in_stint - l.line_mean_age_laps)
        ) AS e_s
    FROM line_laps AS ll
    INNER JOIN line AS l
        ON ll.stint_id = l.stint_id
    WHERE l.line_slope_s_per_lap2 IS NOT NULL
),

line_resid_lagged AS (
    SELECT
        *,
        LAG(e_s) OVER (PARTITION BY stint_id ORDER BY lap_number) AS e_prev_s,
        LAG(lap_number)
            OVER (PARTITION BY stint_id ORDER BY lap_number)
            AS lap_prev
    FROM line_resid
),

season_rho AS (
    SELECT
        race_year,
        SUM(e_s * e_prev_s)
        / NULLIF(SQRT(SUM(e_s * e_s) * SUM(e_prev_s * e_prev_s)), 0)
            AS season_rho1,
        COUNT(*) AS season_lag1_pairs_n
    FROM line_resid_lagged
    WHERE lap_number - lap_prev = 1
    GROUP BY race_year
),

season_sigma AS (
    SELECT
        race_year,
        SQRT(SUM(line_ssr) / NULLIF(SUM(n_line_laps - 2), 0))
            AS season_sigma_w_s,
        COUNT(*) AS season_line_stints_n
    FROM line
    WHERE line_slope_s_per_lap2 IS NOT NULL
    GROUP BY race_year
),

season_noise AS (
    SELECT
        s.race_year,
        s.season_sigma_w_s,
        s.season_line_stints_n,
        r.season_rho1,
        r.season_lag1_pairs_n,
        -- NULL, not independence, when a season has no adjacent line-lap pair
        -- to measure rho from: every SE built on f is then NULL too.
        CASE
            WHEN r.season_rho1 IS NULL THEN NULL
            ELSE
                (1.0 - GREATEST(r.season_rho1, 0.0))
                / (1.0 + GREATEST(r.season_rho1, 0.0))
        END AS season_neff_factor
    FROM season_sigma AS s
    LEFT JOIN season_rho AS r
        ON s.race_year = r.race_year
),

with_noise AS (
    SELECT
        l.*,
        n.season_sigma_w_s,
        n.season_rho1,
        n.season_neff_factor,
        n.season_sigma_w_s
        / SQRT(l.line_age_sxx * n.season_neff_factor)
            AS line_slope_se_s_per_lap2
    FROM line AS l
    LEFT JOIN season_noise AS n
        ON l.race_year = n.race_year
)

SELECT
    n.stint_id,
    n.race_year,
    n.race_id,
    n.driver_id,
    n.constructor_id,
    n.stint_number,
    n.compound,
    n.era,
    n.n_omega_laps,
    n.n_pace_laps,
    n.n_cliff_laps,

    -- The line.
    n.n_line_laps,
    n.line_mean_pace_gain_s,
    n.line_mean_age_laps,
    n.line_ref_age_laps,
    n.line_age_sxx,
    n.line_slope_s_per_lap2,
    n.line_slope_se_s_per_lap2,

    -- Per-season noise, carried for every downstream SE.
    n.season_sigma_w_s,
    n.season_rho1,
    n.season_neff_factor
FROM with_noise AS n
