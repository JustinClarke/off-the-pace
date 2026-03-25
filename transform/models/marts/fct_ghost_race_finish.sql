-- Third Model Sequence #7 (part 2): Ghost car race finish simulator.
-- For each (host_constructor, race) scenario, computes the projected finish
-- position if every driver had been in the given host constructor's car.
--
-- Method: rank drivers by predicted MEAN lap pace (not cumulative sum). Ranking
-- by cumulative SUM(predicted_lap_time_s) is invalid when drivers ran different
-- numbers of laps DNF / heavily-filtered drivers accumulate a smaller total and
-- would be ranked artificially high. Mean pace is invariant to lap count, so a
-- driver who completed 10 laps is compared fairly against one who ran the full race.
-- Short runs (DNF / partial) are flagged via is_short_run so the app can annotate
-- them rather than silently trusting a small-sample estimate.
-- Ties broken by actual finish position.
--
-- ─────────────────────────────────────────────────────────────────────────────
-- transform v0.2 Fix 3 honest confidence via SE propagation
-- ─────────────────────────────────────────────────────────────────────────────
-- The old confidence was an n/(n+50) shrinkage heuristic structurally capped near
-- 0.6 and blind to how *separated* drivers actually are. Fix 3 propagates the real
-- coefficient uncertainties already carried in fct_ghost_car_pace into a per-driver
-- predicted-mean-pace variance, then turns pairwise pace gaps into order
-- probabilities under a normal approximation.
--
-- Per driver d (in host h), predicted mean pace mu_d carries variance from:
--   * host structural-pace SE        (se_pace_h)        multiplier 1
--   * host deg-slope posterior sd     (sd_slope_h)       × mean tyre age (exposure)
--   * ego deg-slope posterior sd      (sd_slope_d)       × mean tyre age
--   * host cliff-shift SE             (se_shift_h)       × severity × frac laps past cliff
--   * ego cliff-shift SE              (se_shift_d)       × severity × frac laps past cliff
--   * finite-sample SE of the mean    (lap_pace_sd / sqrt(L_d)) replaces n/(n+50)
--
-- CORRELATION (the subtle part): within one scenario every driver inherits the
-- SAME host car, so the host structural-pace term is perfectly correlated (common
-- mode) across drivers and CANCELS in any pairwise pace difference. Treating it as
-- independent would massively overstate order uncertainty. The host deg-slope and
-- cliff-shift coefficients are also shared, but each driver's *exposure* (mean age,
-- frac-past-cliff) differs, so only the differential survives the difference. Ego
-- terms and finite-sample noise are driver-specific (independent). Hence:
--
--   Var(mu_i - mu_j) = var_self_i + var_self_j
--                    + (host_slope_term_i - host_slope_term_j)^2
--                    + (host_cliff_term_i - host_cliff_term_j)^2
--   P(i ahead of j)  = Phi( (mu_j - mu_i) / sqrt(Var(mu_i - mu_j)) )   (lower pace = ahead)
--
-- where var_self_d = (sd_slope_d*age_d)^2 + (se_shift_d*sev*frac_d)^2 + lap_pace_sd^2/L_d.
-- host_pace SE enters the marginal predicted_mean_lap_se_s but drops out of every
-- pairwise comparison. p_beats_next = P(driver beats the one ranked just below it);
-- finish_pos_se = sqrt(sum_k p_k(1-p_k)) (Poisson-binomial sd of #drivers ahead).
-- Independence across the pairwise events is an approximation (shared host coeffs
-- induce mild correlation in the residual terms) honest enough for calibration,
-- documented here rather than hidden.
--
-- avg_recombination_confidence (old heuristic) is retained one release for app diffing.
--
-- Grain: (host_constructor_id, ego_driver_id, race_id) one row per scenario.
-- PK: surrogate hash of the three keys.

{{ config(materialized='table', tags=['marts', 'simulation', 'ghost_car']) }}

WITH ghost_laps AS (
    SELECT
        race_year,
        race_id,
        ego_driver_id,
        ego_constructor_id,
        host_constructor_id,
        lap_number,
        predicted_lap_time_s,
        actual_lap_time_s,
        recombination_confidence,
        -- Fix 3 SE-propagation ingredients (per lap)
        host_constructor_pace_se_s,
        host_deg_slope_sd_s_per_lap,
        ego_deg_slope_sd_s_per_lap,
        host_cliff_shift_se_laps,
        ego_cliff_shift_se_laps,
        age_in_stint,
        compound_cliff_severity,
        host_cliff_active,
        ego_cliff_active
    FROM {{ ref('fct_ghost_car_pace') }}
    WHERE recombination_confidence >= 0.3   -- minimum confidence for position sim
),

-- Race distance reference: the most laps any driver contributes in this race.
-- Used to express each driver's lap coverage as a fraction of a full race.
race_distance AS (
    SELECT
        race_year,
        race_id,
        host_constructor_id,
        MAX(laps_in_scenario) AS race_distance_laps
    FROM (
        SELECT
            race_year,
            race_id,
            host_constructor_id,
            ego_driver_id,
            COUNT(*) AS laps_in_scenario
        FROM ghost_laps
        GROUP BY race_year, race_id, host_constructor_id, ego_driver_id
    )
    GROUP BY race_year, race_id, host_constructor_id
),

-- Actual finish position from stg_laps (last valid lap's position)
actual_finish AS (
    SELECT
        race_year,
        race_id,
        driver_id                               AS ego_driver_id,
        MAX(position) FILTER (WHERE is_valid_lap = TRUE) AS actual_finish_position
    FROM {{ ref('stg_laps') }}
    GROUP BY race_year, race_id, driver_id
),

-- Per (driver, host_constructor, race): mean pace + cumulative totals (informational)
-- and the aggregated exposures / SEs that feed variance propagation.
race_totals AS (
    SELECT
        race_year,
        race_id,
        ego_driver_id,
        host_constructor_id,
        -- self-scenario detection: ego driving their own constructor's car
        MAX(CASE WHEN ego_constructor_id = host_constructor_id THEN 1 ELSE 0 END) = 1
                                                AS is_self_scenario,
        AVG(predicted_lap_time_s)               AS predicted_mean_lap_s,
        AVG(actual_lap_time_s)                  AS actual_mean_lap_s,
        SUM(predicted_lap_time_s)               AS predicted_total_race_time_s,
        SUM(actual_lap_time_s)                  AS actual_total_race_time_s,
        COUNT(*)                                AS laps_counted,
        AVG(recombination_confidence)           AS lap_mean_confidence,
        -- Fix 3 aggregated exposures (constant-ish per scenario averaged over laps)
        AVG(host_constructor_pace_se_s)         AS host_pace_se,
        AVG(host_deg_slope_sd_s_per_lap)        AS host_slope_sd,
        AVG(ego_deg_slope_sd_s_per_lap)         AS ego_slope_sd,
        AVG(host_cliff_shift_se_laps)           AS host_cliff_se,
        AVG(ego_cliff_shift_se_laps)            AS ego_cliff_se,
        AVG(compound_cliff_severity)            AS mean_severity,
        AVG(age_in_stint)                       AS mean_age,
        AVG(host_cliff_active)                  AS frac_host_active,
        AVG(ego_cliff_active)                   AS frac_ego_active,
        -- finite-sample SE of the mean: sd of per-lap predictions / sqrt(laps).
        -- COALESCE handles single-lap scenarios (STDDEV_SAMP is NULL at n=1).
        COALESCE(STDDEV_SAMP(predicted_lap_time_s), 0.0) AS lap_pace_sd
    FROM ghost_laps
    GROUP BY race_year, race_id, ego_driver_id, host_constructor_id
),

with_coverage AS (
    SELECT
        rt.*,
        rd.race_distance_laps,
        CAST(rt.laps_counted AS DOUBLE)
            / NULLIF(rd.race_distance_laps, 0)  AS lap_coverage,
        (CAST(rt.laps_counted AS DOUBLE)
            / NULLIF(rd.race_distance_laps, 0))
            < {{ var('ghost_short_run_threshold', 0.5) }}  AS is_short_run,
        -- Coverage-weighted confidence: a low-lap estimate is less trustworthy than
        -- a full-distance one, so attenuate the lap-mean confidence by sqrt(coverage).
        rt.lap_mean_confidence
            * SQRT(LEAST(1.0, CAST(rt.laps_counted AS DOUBLE)
                / NULLIF(rd.race_distance_laps, 0)))        AS avg_recombination_confidence,
        -- ── Fix 3 variance propagation ──
        -- Shared host coefficient × this driver's exposure (survives only as a
        -- differential between drivers, so kept separate for the pairwise step).
        rt.host_slope_sd * rt.mean_age                      AS host_slope_term,
        rt.host_cliff_se * rt.mean_severity * rt.frac_host_active AS host_cliff_term,
        -- Driver-specific (independent across drivers) variance.
        POWER(rt.ego_slope_sd * rt.mean_age, 2)
            + POWER(rt.ego_cliff_se * rt.mean_severity * rt.frac_ego_active, 2)
            + POWER(rt.lap_pace_sd, 2) / NULLIF(rt.laps_counted, 0) AS var_self
    FROM race_totals rt
    JOIN race_distance rd
        USING (race_year, race_id, host_constructor_id)
),

-- Marginal predicted-mean SE (includes the host pace SE) + within-scenario ranks.
driver_stats AS (
    SELECT
        *,
        SQRT(
            var_self
            + POWER(host_pace_se, 2)
            + POWER(host_slope_term, 2)
            + POWER(host_cliff_term, 2)
        )                                       AS predicted_mean_lap_se_s,
        RANK() OVER (
            PARTITION BY race_year, race_id, host_constructor_id
            ORDER BY predicted_mean_lap_s ASC
        )                                       AS predicted_finish_position,
        RANK() OVER (
            PARTITION BY race_year, race_id, host_constructor_id
            ORDER BY actual_mean_lap_s ASC
        )                                       AS actual_rank_in_scenario
    FROM with_coverage
),

-- Pairwise order probabilities within each scenario. p_i_beats_j = P(mu_i < mu_j).
-- Host structural pace cancels (shared, multiplier 1); only differential host
-- coefficient exposure + driver-specific variance remain in the difference.
pairwise AS (
    SELECT
        i.race_year,
        i.race_id,
        i.host_constructor_id,
        i.ego_driver_id,
        i.predicted_finish_position             AS rank_i,
        j.predicted_finish_position             AS rank_j,
        i.predicted_mean_lap_s                  AS mu_i,
        j.predicted_mean_lap_s                  AS mu_j,
        -- sd of (mu_i - mu_j); floored to avoid 0/0 when both are deterministic.
        GREATEST(SQRT(
            i.var_self + j.var_self
            + POWER(i.host_slope_term - j.host_slope_term, 2)
            + POWER(i.host_cliff_term - j.host_cliff_term, 2)
        ), 1e-6)                                AS sd_diff
    FROM driver_stats i
    JOIN driver_stats j
        ON  i.race_year          = j.race_year
        AND i.race_id            = j.race_id
        AND i.host_constructor_id = j.host_constructor_id
        AND i.ego_driver_id     <> j.ego_driver_id
),

pairwise_prob AS (
    SELECT
        race_year,
        race_id,
        host_constructor_id,
        ego_driver_id,
        rank_i,
        rank_j,
        -- P(i finishes ahead of j) = P(mu_i < mu_j)
        {{ normal_cdf('(mu_j - mu_i) / sd_diff') }} AS p_i_beats_j
    FROM pairwise
),

pairwise_agg AS (
    SELECT
        race_year,
        race_id,
        host_constructor_id,
        ego_driver_id,
        -- finish-position sd: Poisson-binomial sd of the count of drivers ahead.
        -- p(1-p) is symmetric in p, so summing over "i beats j" events is valid.
        SQRT(SUM(p_i_beats_j * (1.0 - p_i_beats_j))) AS finish_pos_se,
        -- probability of beating the driver ranked immediately below.
        MAX(CASE WHEN rank_j = rank_i + 1 THEN p_i_beats_j END) AS p_beats_next
    FROM pairwise_prob
    GROUP BY race_year, race_id, host_constructor_id, ego_driver_id
)

SELECT
    MD5(CONCAT(
        r.race_year, '_',
        r.race_id, '_',
        r.ego_driver_id, '_',
        r.host_constructor_id
    ))                                          AS ghost_race_id,
    r.race_year,
    r.race_id,
    r.ego_driver_id,
    r.host_constructor_id,
    r.is_self_scenario,
    r.predicted_finish_position,
    af.actual_finish_position,
    -- Delta only defined when the driver has a real finishing position. DNFs (NULL
    -- actual) get NULL delta rather than a magic default.
    CASE
        WHEN af.actual_finish_position IS NULL THEN NULL
        ELSE r.predicted_finish_position-af.actual_finish_position
    END                                         AS delta_vs_actual_position,
    r.predicted_mean_lap_s,
    r.actual_mean_lap_s,
    r.predicted_total_race_time_s,
    r.actual_total_race_time_s,
    r.laps_counted,
    r.race_distance_laps,
    r.lap_coverage,
    r.is_short_run,
    r.avg_recombination_confidence,
    -- Fix 3 honest-confidence columns
    r.predicted_mean_lap_se_s,
    pa.p_beats_next,
    COALESCE(pa.finish_pos_se, 0.0)             AS finish_pos_se
FROM driver_stats r
LEFT JOIN actual_finish af
    ON r.race_year     = af.race_year
    AND r.race_id      = af.race_id
    AND r.ego_driver_id = af.ego_driver_id
LEFT JOIN pairwise_agg pa
    ON  r.race_year          = pa.race_year
    AND r.race_id            = pa.race_id
    AND r.host_constructor_id = pa.host_constructor_id
    AND r.ego_driver_id      = pa.ego_driver_id
ORDER BY r.race_year, r.race_id, r.host_constructor_id, r.predicted_finish_position
