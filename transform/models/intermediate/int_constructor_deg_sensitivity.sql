-- Transform v0.2 Fix 1: constructor-specific tyre degradation sensitivity.
--
-- DESIGN NOTE (Fix 1.1, 2026-06-11)
-- =================================
-- Purpose: give the ghost-car recombination an interaction term that depends on
-- host identity, so different hosts can produce different driver orders:
--
--   predicted_lap(driver d, host h) =
--       (existing 9 terms inherited from ego driver d)
--     + (deg_slope(h, compound, season) - deg_slope(d, compound, season)) * age_in_stint
--
-- Estimator (chosen formula):
--   Within-stint fixed-effects OLS of the post-decomposition residual on tyre age,
--   per (constructor, compound, season) cell:
--
--     slope_raw = SUM((age - mean_age_stint) * (resid - mean_resid_stint))
--               / SUM((age - mean_age_stint)^2)
--
--   then field-centred per (compound, season) using the precision-weighted mean,
--   then empirical-Bayes shrunk toward 0 with a DerSimonian-Laird tau^2:
--
--     deg_slope = (slope_raw - field_mean) * tau^2 / (tau^2 + se^2)
--
-- Why within-stint demeaning: stint fixed effects absorb driver level skill, race,
-- circuit, and starting tyre condition. Only the within-stint trend identifies the
-- slope, so a level difference between teammates or races cannot bias it.
--
-- Why field-centring: the raw within-stint trend of the residual is uniformly
-- negative (~ -0.08 s/lap on 2024 HARD) a common artifact of residual fuel
-- under-correction surviving the decomposition (see
-- analyses/deg_slope_fuel_deconfounding.sql). The artifact is common across
-- constructors, so centring on the per-(compound, season) field mean cancels it.
-- The recombination term only ever consumes (host - ego), which is invariant to
-- the centring constant, but the centred value is the honest deliverable: it is
-- the constructor's deviation from the field-average compound degradation curve
-- already priced into compound_component_s.
--
-- Why EB shrink toward 0 (not hierarchical): with ~10 constructors x 3 dry
-- compounds per season, a multi-level hierarchy has too few groups per level to
-- estimate in SQL, and the natural prior mean of a *deviation* is exactly 0.
-- DerSimonian-Laird gives a per-(compound, season) between-constructor variance
-- tau^2; thin cells (SOFT, ~30-150 laps) shrink by 10-35%, dense cells (HARD,
-- ~800-1050 laps) keep ~98% of their estimate. 2024 result: tau > 0 on every dry
-- compound, devs span ~±0.02 s/lap on HARD the "slopes shrink to ~0 everywhere"
-- stop criterion does NOT trigger.
--
-- Season boundaries: cells are scoped by race_year, so regulation changes (e.g.
-- 2022) are handled by construction; no cross-season pooling.
--
-- Minimum-cell rules: a cell qualifies when n_laps >= 30 AND n_stints >= 5 AND
-- SUM(dx^2) > 0. Non-qualifying cells are kept (is_low_sample = TRUE) with
-- deg_slope_s_per_lap = 0 (fully shrunk), se NULL, posterior sd = tau (prior sd).
-- Only qualifying cells enter the field mean and tau^2.
--
-- Lap selection: clean laps only (correction_weight = 1.0), dry compounds
-- (SOFT/MEDIUM/HARD), no rain, lap_in_stint > 1 (out-laps), pre-cliff only
-- (cliff_onset_passed = FALSE) the post-cliff nonlinearity is Fix 2's
-- per-constructor break-point shift, not this linear term.
--
-- Known limitation: with two drivers per car and stint FE, car-deg and
-- driver-pair tyre management are not separable; the cell slope is their blend.
-- The Phase 2 teammate-swap harness (gate 4.1) is the designed test for this.
--
-- Deconfounding verdict (Fix 1.4): see analyses/deg_slope_fuel_deconfounding.sql.
-- Slopes are fit on the post-fuel-correction residual; conditioning on fuel_mass_kg
-- (identified across stints: same age at different fuel loads) moves the pooled age
-- slope by only ~11-16% and preserves the constructor ordering and spread, so the
-- slope is not a fuel artifact.
--
-- DESIGN NOTE (Fix 2.2 per-constructor cliff-onset shift, 2026-06-11)
-- ====================================================================
-- The linear slope above is fit on PRE-cliff laps only. Fix 2 adds a second
-- deliverable: how much EARLIER or LATER each constructor's tyre cliff begins
-- relative to the field onset already priced into compound_component_s
-- (dim_compounds_season.compound_cliff_onset_laps). We do NOT re-locate the
-- breakpoint per stint (too noisy on thin post-cliff samples); instead we measure
-- the constructor's EXTRA post-onset degradation as a hinge coefficient and convert
-- it to an equivalent onset shift in laps (the "hinge-coefficient proxy").
--
-- Estimator: bivariate within-stint FE OLS of the post-decomposition residual on
-- (age_in_stint, hinge) per (constructor, compound, season), where
--   hinge = laps_past_cliff = GREATEST(age - field_onset, 0)  (int_compound_cliff_predicted)
-- over clean dry laps INCLUDING post-onset, stint-demeaned so stint level/skill/
-- circuit drop out. The age term absorbs the linear trend (the same quantity Fix 1
-- isolates); the hinge coefficient b_hinge is the EXTRA s/lap that kicks in after
-- the field onset. 2x2 normal equations give b_hinge and b_age in closed form;
-- det = Sxx*Szz - Sxz^2 must be > 0 for identification (a stint fully pre-onset
-- contributes Szz = Sxz = 0, so a cell needs real post-onset variation).
--
-- Like the linear slope, raw b_hinge is uniformly negative (~ -0.8 to -1.3 on 2024
-- residual-fuel / mean-reversion artifact common to all constructors), so we
-- field-centre per (compound, season) and DL-EB shrink the DEVIATION toward 0,
-- reusing the exact pooling machinery above.
--
-- Map deviation -> onset shift. NOTE the field cliff model (int_compound_cliff_predicted)
-- applies severity LINEARLY to laps_past_cliff (penalty = severity*(age-onset)+),
-- so severity has units s/lap and the post-onset ramp is linear, not quadratic.
-- A constructor with extra linear post-onset slope dev_hinge sits, at a reference
-- depth ref_depth laps past the field onset, dev_hinge*ref_depth seconds off the
-- field ramp. Representing that as a shift of the (same-slope) field ramp's onset
-- by delta moves the penalty by severity*delta, so matching at the reference depth:
--   severity * delta = dev_hinge * ref_depth
--   cliff_onset_shift_laps (host_shift) = -dev_hinge * ref_depth / severity
-- ref_depth = per-(compound, season) MEAN laps_past_cliff over post-onset clean laps
-- (HARD ~8, MEDIUM ~5, SOFT ~6 on 2024) the typical depth at which the cliff
-- difference is realised. Sign matches the recombination term, which uses the same
-- LINEAR ramp: severity * [ GREATEST(0, age-onset-host_shift) - GREATEST(0, age-onset-ego_shift) ].
-- A constructor that degrades HARDER post-onset (dev_hinge > 0) gets a NEGATIVE
-- shift = earlier effective onset = slower once past the cliff. severity is the
-- per-(compound, season) median field severity, floored at 0.30 s/lap so a soft
-- cell cannot blow the ratio up; the shift is clipped to +/-5 laps. Min-cell rule:
-- n_post >= 30 AND n_stints >= 5 AND det > 0 AND Szz > 0; non-qualifying cells get
-- cliff_onset_shift_laps = 0 (field-timed cliff), is_low_sample_cliff = TRUE.
-- cliff_onset_shift_se_laps is carried for Fix 3 SE propagation.
--
-- Why an onset shift, not a raw slope-difference term: a slope difference grows
-- unbounded with stint length (a thin-cell outlier slope would dominate a 25-lap
-- post-cliff run), whereas an onset shift's recombination contribution is bounded
-- by severity*shift. The break-point shift is the outlier-robust primitive near a
-- cliff, which is exactly why the roadmap specified an onset shift here.
--
-- Output grain: one row per (race_year, constructor_id, compound).
-- deg_slope_s_per_lap > 0 = degrades faster than the field on that compound.
-- cliff_onset_shift_laps > 0 = cliff arrives LATER than the field (gentler).
-- slope_se / posterior sd / n_laps are carried for Fix 3 (SE propagation).

{{ config(materialized='table', tags=['causal_decomposition', 'constructor', 'degradation']) }}

WITH clean_laps AS (
    -- age_in_stint, compound, lap_in_stint are carried on int_lap_residual_decomposed
    -- from int_stint_geometry, so no second join is needed.
    SELECT
        race_year,
        stint_id,
        constructor_id,
        compound,
        CAST(age_in_stint AS DOUBLE)        AS age_in_stint,
        driver_skill_residual_s
    FROM {{ ref('int_lap_residual_decomposed') }}
    WHERE correction_weight = 1.0
      AND COALESCE(rainfall_flag, FALSE) = FALSE
      AND compound IN ('SOFT', 'MEDIUM', 'HARD')
      AND lap_in_stint > 1
      AND COALESCE(cliff_onset_passed, FALSE) = FALSE
      AND driver_skill_residual_s IS NOT NULL
      AND age_in_stint IS NOT NULL
),

-- Stint fixed effects via within-stint demeaning
demeaned AS (
    SELECT
        race_year,
        constructor_id,
        compound,
        stint_id,
        age_in_stint            - AVG(age_in_stint)            OVER (PARTITION BY stint_id) AS dx,
        driver_skill_residual_s - AVG(driver_skill_residual_s) OVER (PARTITION BY stint_id) AS dy
    FROM clean_laps
),

-- Per-cell within-estimator: slope = Sxy / Sxx on demeaned data
cells AS (
    SELECT
        race_year,
        constructor_id,
        compound,
        COUNT(*)                            AS n_laps,
        COUNT(DISTINCT stint_id)            AS n_stints,
        SUM(dx * dy) / NULLIF(SUM(dx * dx), 0) AS slope_raw,
        SUM(dy * dy)                        AS syy,
        SUM(dx * dy)                        AS sxy,
        SUM(dx * dx)                        AS sxx
    FROM demeaned
    GROUP BY race_year, constructor_id, compound
),

with_se AS (
    SELECT
        race_year,
        constructor_id,
        compound,
        n_laps,
        n_stints,
        slope_raw,
        -- FE-regression SE: dof = n - n_stints (stint means) - 1 (slope).
        -- Floored at 1e-4 s/lap so a degenerate perfect fit cannot produce
        -- an infinite precision weight.
        GREATEST(
            SQRT(
                GREATEST(syy - slope_raw * sxy, 0)
                / GREATEST(n_laps - n_stints - 1, 1)
                / NULLIF(sxx, 0)
            ),
            0.0001
        )                                   AS slope_se,
        (n_laps >= 30 AND n_stints >= 5 AND sxx > 0) AS qualifies
    FROM cells
),

-- Precision-weighted field mean per (compound, season) over qualifying cells
field_mean AS (
    SELECT
        race_year,
        compound,
        SUM(slope_raw / (slope_se * slope_se)) / SUM(1.0 / (slope_se * slope_se))
                                            AS field_mean_slope
    FROM with_se
    WHERE qualifies
    GROUP BY race_year, compound
),

centered AS (
    SELECT
        s.*,
        f.field_mean_slope,
        s.slope_raw - f.field_mean_slope    AS dev,
        1.0 / (s.slope_se * s.slope_se)     AS w
    FROM with_se s
    LEFT JOIN field_mean f USING (race_year, compound)
),

-- DerSimonian-Laird between-constructor variance per (compound, season)
tau AS (
    SELECT
        race_year,
        compound,
        GREATEST(
            COALESCE(
                (SUM(w * dev * dev) - (COUNT(*) - 1))
                / NULLIF(SUM(w) - SUM(w * w) / SUM(w), 0),
                0
            ),
            0
        )                                   AS tau2
    FROM centered
    WHERE qualifies
    GROUP BY race_year, compound
),

-- ============================================================================
-- Fix 2.2: per-constructor cliff-onset shift (hinge-coefficient proxy)
-- ============================================================================

-- Clean dry laps INCLUDING post-onset, carrying the field hinge from
-- int_compound_cliff_predicted (laps_past_cliff = GREATEST(age - field_onset, 0)).
clean_laps_cliff AS (
    SELECT
        lr.race_year,
        lr.stint_id,
        lr.constructor_id,
        lr.compound,
        CAST(lr.age_in_stint AS DOUBLE)         AS age_in_stint,
        cp.laps_past_cliff                      AS hinge,
        (cp.laps_past_cliff > 0)                AS is_post,
        (cp.laps_past_cliff >= 2.0)             AS is_deep,
        lr.driver_skill_residual_s
    FROM {{ ref('int_lap_residual_decomposed') }} lr
    JOIN {{ ref('int_compound_cliff_predicted') }} cp USING (lap_id)
    WHERE lr.correction_weight = 1.0
      AND COALESCE(lr.rainfall_flag, FALSE) = FALSE
      AND lr.compound IN ('SOFT', 'MEDIUM', 'HARD')
      AND lr.lap_in_stint > 1
      AND lr.driver_skill_residual_s IS NOT NULL
      AND lr.age_in_stint IS NOT NULL
      AND cp.laps_past_cliff IS NOT NULL
),

-- Stint fixed effects via within-stint demeaning of (age, hinge, residual)
demeaned_cliff AS (
    SELECT
        race_year,
        constructor_id,
        compound,
        stint_id,
        is_post,
        is_deep,
        age_in_stint            - AVG(age_in_stint)            OVER (PARTITION BY stint_id) AS dx,
        hinge                   - AVG(hinge)                   OVER (PARTITION BY stint_id) AS dz,
        driver_skill_residual_s - AVG(driver_skill_residual_s) OVER (PARTITION BY stint_id) AS dy
    FROM clean_laps_cliff
),

-- Per-cell cross-products for the 2x2 normal equations
cliff_cells AS (
    SELECT
        race_year,
        constructor_id,
        compound,
        COUNT(*)                                 AS n_laps_cliff,
        COUNT(DISTINCT stint_id)                 AS n_stints_cliff,
        SUM(CASE WHEN is_post THEN 1 ELSE 0 END) AS n_post,
        SUM(CASE WHEN is_deep THEN 1 ELSE 0 END) AS n_deep,
        SUM(dx * dx)                             AS sxx,
        SUM(dz * dz)                             AS szz,
        SUM(dx * dz)                             AS sxz,
        SUM(dx * dy)                             AS sxy,
        SUM(dz * dy)                             AS szy,
        SUM(dy * dy)                             AS syy
    FROM demeaned_cliff
    GROUP BY race_year, constructor_id, compound
),

-- Closed-form 2x2 OLS: [Sxx Sxz; Sxz Szz][b_age; b_hinge] = [Sxy; Szy]
cliff_beta AS (
    SELECT
        *,
        (sxx * szz - sxz * sxz)                  AS det,
        CASE WHEN (sxx * szz - sxz * sxz) > 0
             THEN (sxx * szy - sxz * sxy) / (sxx * szz - sxz * sxz) END AS b_hinge_raw,
        CASE WHEN (sxx * szz - sxz * sxz) > 0
             THEN (szz * sxy - sxz * szy) / (sxx * szz - sxz * sxz) END AS b_age_raw
    FROM cliff_cells
),

cliff_se AS (
    SELECT
        *,
        -- Var(b_hinge) = sigma^2 * Sxx / det; sigma^2 = RSS / (n - n_stints - 2).
        -- Floored at 1e-4 so a degenerate fit cannot produce infinite precision.
        GREATEST(
            SQRT(
                GREATEST(syy - b_age_raw * sxy - b_hinge_raw * szy, 0)
                / GREATEST(n_laps_cliff - n_stints_cliff - 2, 1)
                * (sxx / NULLIF(det, 0))
            ),
            0.0001
        )                                        AS b_hinge_se,
        -- Require post-onset DEPTH (>= 15 laps that are >= 2 laps past onset), not just
        -- count: a cell of many stints each barely crossing the cliff gives a noisy hinge.
        (n_post >= 30 AND n_deep >= 15 AND n_stints_cliff >= 5 AND det > 0 AND szz > 0) AS cliff_qualifies
    FROM cliff_beta
),

-- Precision-weighted field mean of the hinge coefficient per (compound, season)
cliff_field_mean AS (
    SELECT
        race_year,
        compound,
        SUM(b_hinge_raw / (b_hinge_se * b_hinge_se))
            / SUM(1.0 / (b_hinge_se * b_hinge_se)) AS field_mean_hinge
    FROM cliff_se
    WHERE cliff_qualifies
    GROUP BY race_year, compound
),

cliff_centered AS (
    SELECT
        s.*,
        f.field_mean_hinge,
        s.b_hinge_raw - f.field_mean_hinge       AS hinge_dev,
        1.0 / (s.b_hinge_se * s.b_hinge_se)      AS hw
    FROM cliff_se s
    LEFT JOIN cliff_field_mean f USING (race_year, compound)
),

-- DerSimonian-Laird between-constructor variance of the hinge deviation
cliff_tau AS (
    SELECT
        race_year,
        compound,
        GREATEST(
            COALESCE(
                (SUM(hw * hinge_dev * hinge_dev) - (COUNT(*) - 1))
                / NULLIF(SUM(hw) - SUM(hw * hw) / SUM(hw), 0),
                0
            ),
            0
        )                                        AS htau2
    FROM cliff_centered
    WHERE cliff_qualifies
    GROUP BY race_year, compound
),

-- Median field severity per (compound, season), floored for the mapping
cliff_sev AS (
    SELECT
        season                                   AS race_year,
        compound_code                            AS compound,
        GREATEST(MEDIAN(compound_cliff_severity), 0.30) AS severity_used
    FROM {{ ref('dim_compounds_season') }}
    WHERE compound_code IN ('SOFT', 'MEDIUM', 'HARD')
    GROUP BY season, compound_code
),

-- Reference depth: typical laps past the field onset (mean over post-onset clean
-- laps) per (compound, season). The depth at which the hinge-slope deviation is
-- converted to an equivalent onset shift.
cliff_ref_depth AS (
    SELECT
        race_year,
        compound,
        AVG(hinge)                               AS ref_depth
    FROM clean_laps_cliff
    WHERE is_post
    GROUP BY race_year, compound
),

cliff_shift AS (
    SELECT
        c.race_year,
        c.constructor_id,
        c.compound,
        c.b_hinge_raw,
        c.field_mean_hinge,
        c.b_hinge_se,
        c.n_post,
        c.n_deep,
        c.n_stints_cliff,
        c.cliff_qualifies,
        sv.severity_used,
        rd.ref_depth,
        -- EB-shrunk hinge deviation (0 for non-qualifying cells)
        CASE
            WHEN c.cliff_qualifies
                THEN c.hinge_dev * t.htau2 / NULLIF(t.htau2 + c.b_hinge_se * c.b_hinge_se, 0)
            ELSE 0.0
        END                                      AS hinge_dev_shrunk,
        SQRT(COALESCE(t.htau2, 0))               AS hinge_tau
    FROM cliff_centered c
    LEFT JOIN cliff_tau t USING (race_year, compound)
    LEFT JOIN cliff_sev sv USING (race_year, compound)
    LEFT JOIN cliff_ref_depth rd USING (race_year, compound)
)

SELECT
    CONCAT(
        CAST(c.race_year AS VARCHAR), '_',
        c.constructor_id, '_',
        c.compound
    )                                       AS deg_sensitivity_id,
    c.race_year,
    c.constructor_id,
    c.compound,
    -- Production value: EB-shrunk deviation from the field-mean slope.
    -- Positive = this constructor degrades faster than the field on this compound.
    CASE
        WHEN c.qualifies
            THEN c.dev * t.tau2 / NULLIF(t.tau2 + c.slope_se * c.slope_se, 0)
        ELSE 0.0
    END                                     AS deg_slope_s_per_lap,
    c.slope_raw                             AS deg_slope_raw_s_per_lap,
    c.field_mean_slope                      AS field_mean_slope_s_per_lap,
    CASE WHEN c.qualifies THEN c.slope_se END AS deg_slope_se_s_per_lap,
    -- EB posterior sd of the shrunk estimate; prior sd (tau) for low-sample cells.
    CASE
        WHEN NOT c.qualifies                THEN SQRT(COALESCE(t.tau2, 0))
        WHEN COALESCE(t.tau2, 0) <= 0       THEN 0.0
        ELSE SQRT(1.0 / (1.0 / (c.slope_se * c.slope_se) + 1.0 / t.tau2))
    END                                     AS deg_slope_posterior_sd_s_per_lap,
    CASE
        WHEN c.qualifies
            THEN t.tau2 / NULLIF(t.tau2 + c.slope_se * c.slope_se, 0)
        ELSE 0.0
    END                                     AS shrink_factor,
    SQRT(COALESCE(t.tau2, 0))               AS tau_s_per_lap,
    c.n_laps,
    c.n_stints,
    NOT c.qualifies                         AS is_low_sample,
    -- Fix 2.2: per-constructor cliff-onset shift (laps). Positive = cliff arrives
    -- LATER than the field (gentler); negative = earlier (harsher). 0 for cells
    -- without enough post-onset evidence. Clipped to +/-5 laps.
    LEAST(GREATEST(
        -COALESCE(cs.hinge_dev_shrunk, 0.0) * cs.ref_depth
            / NULLIF(cs.severity_used, 0),
        -3.0), 3.0)                         AS cliff_onset_shift_laps,
    -- SE of the shift (delta-method through the same ref_depth/severity map);
    -- carried for Fix 3 SE propagation. NULL for non-qualifying cells.
    CASE WHEN cs.cliff_qualifies
         THEN cs.b_hinge_se * cs.ref_depth / NULLIF(cs.severity_used, 0) END
                                            AS cliff_onset_shift_se_laps,
    cs.b_hinge_raw                          AS cliff_hinge_coef_s_per_lap,
    cs.field_mean_hinge                     AS cliff_hinge_field_mean_s_per_lap,
    cs.severity_used                        AS cliff_severity_used_s_per_lap,
    cs.ref_depth                            AS cliff_ref_depth_laps,
    cs.hinge_tau                            AS cliff_hinge_tau_s_per_lap,
    COALESCE(cs.n_post, 0)                  AS n_post_cliff_laps,
    COALESCE(cs.n_deep, 0)                  AS n_deep_cliff_laps,
    COALESCE(cs.n_stints_cliff, 0)          AS n_stints_cliff,
    NOT COALESCE(cs.cliff_qualifies, FALSE) AS is_low_sample_cliff,
    CAST(CURRENT_TIMESTAMP AS VARCHAR)      AS fit_timestamp
FROM centered c
LEFT JOIN tau t USING (race_year, compound)
LEFT JOIN cliff_shift cs
    ON c.race_year      = cs.race_year
    AND c.constructor_id = cs.constructor_id
    AND c.compound      = cs.compound
ORDER BY c.race_year DESC, c.compound, deg_slope_s_per_lap
