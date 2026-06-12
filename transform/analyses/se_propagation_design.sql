-- transform v0.2 Fix 3 SE propagation design note + verification
-- ===========================================================================
-- DELIVERABLE for roadmap step 3.1. The variance algebra is implemented in
-- fct_ghost_race_finish (see its header); this file states it compactly and
-- gives queries that empirically check the two design decisions that matter.
--
-- ── Variance model ─────────────────────────────────────────────────────────
-- Predicted mean pace for driver d in host h:
--   mu_d = mean_l [ deterministic recombination terms ]
-- Uncertain coefficients, each with an SE already carried in fct_ghost_car_pace:
--   se_pace_h   host structural pace        (multiplier 1; SHARED across drivers)
--   sd_slope_h  host deg slope posterior sd (× mean tyre age; SHARED coefficient)
--   sd_slope_d  ego deg slope posterior sd  (× mean tyre age; driver-specific)
--   se_shift_h  host cliff-onset shift SE   (× severity × frac-past-cliff; SHARED)
--   se_shift_d  ego cliff-onset shift SE    (× severity × frac-past-cliff; driver-spec)
--   lap_pace_sd/sqrt(L)  finite-sample SE of the mean (driver-specific)
--
-- Marginal:  Var(mu_d) = var_self_d + se_pace_h^2 + (sd_slope_h*age_d)^2
--                                                  + (se_shift_h*sev*frac_h_d)^2
--   where var_self_d = (sd_slope_d*age_d)^2 + (se_shift_d*sev*frac_e_d)^2
--                      + lap_pace_sd^2 / L_d
--
-- ── Correlation decision (the subtle part) ─────────────────────────────────
-- Within a scenario every driver inherits the SAME host car. The host pace,
-- host slope, and host cliff coefficients are therefore COMMON-MODE: perfectly
-- correlated across drivers. In a pairwise difference mu_i - mu_j the common
-- coefficient times the SAME multiplier cancels. The host structural pace has
-- multiplier 1 for everyone, so it cancels EXACTLY. The host slope/cliff have
-- driver-specific exposures (age, frac-past-cliff), so only the differential
-- survives:
--   Var(mu_i - mu_j) = var_self_i + var_self_j
--                    + (sd_slope_h)^2 (age_i - age_j)^2
--                    + (se_shift_h*sev)^2 (frac_i - frac_j)^2
-- Treating these as independent (naive) would add 2*se_pace_h^2 + ... and
-- massively overstate order uncertainty. P(i ahead of j) = Phi((mu_j-mu_i)/sd).
--
-- Pairwise events are then treated as independent for the Poisson-binomial
-- finish_pos_se = sqrt(sum_k p_k(1-p_k)); residual correlation from shared host
-- slope/cliff is second-order and left for the §4 calibration gate to measure.
-- ===========================================================================

-- CHECK 1: quantify what the cancellation is worth. Host structural pace is the
-- single largest marginal SE component, but it has multiplier 1 for every driver in
-- the scenario, so it drops out of every pairwise comparison. We measure (a) how much
-- of the marginal predicted-pace SE is host pace, and (b) how that compares to typical
-- adjacent pace gaps i.e. the variance that would, if NOT cancelled, swamp the gap.
WITH pace_se AS (   -- host pace SE per driver-scenario (constant across that driver's laps)
    SELECT race_year, race_id, host_constructor_id, ego_driver_id,
           AVG(host_constructor_pace_se_s) AS host_pace_se
    FROM {{ ref('fct_ghost_car_pace') }}
    WHERE recombination_confidence >= 0.3
    GROUP BY 1, 2, 3, 4
),
adjacent_gaps AS (  -- predicted pace gap to the next-ranked driver, per scenario
    SELECT
        i.predicted_mean_lap_se_s,
        p.host_pace_se,
        (j.predicted_mean_lap_s - i.predicted_mean_lap_s) AS gap_to_next
    FROM {{ ref('fct_ghost_race_finish') }} i
    JOIN {{ ref('fct_ghost_race_finish') }} j
      ON  i.race_year = j.race_year AND i.race_id = j.race_id
      AND i.host_constructor_id = j.host_constructor_id
      AND j.predicted_finish_position = i.predicted_finish_position + 1
    JOIN pace_se p
      ON  p.race_year = i.race_year AND p.race_id = i.race_id
      AND p.host_constructor_id = i.host_constructor_id
      AND p.ego_driver_id = i.ego_driver_id
)
SELECT
    COUNT(*)                                                      AS adjacent_pairs,
    ROUND(AVG(host_pace_se), 4)                                   AS mean_host_pace_se,
    ROUND(AVG(predicted_mean_lap_se_s), 4)                        AS mean_marginal_se,
    -- share of marginal variance that is the (cancelled) host-pace term
    ROUND(AVG(POWER(host_pace_se, 2))
          / AVG(POWER(predicted_mean_lap_se_s, 2)), 3)            AS host_pace_var_share,
    ROUND(AVG(gap_to_next), 4)                                    AS mean_gap_to_next,
    -- if host pace did NOT cancel it would add sqrt2*se to each pairwise sd; compare
    -- that injected noise to the gap it would have to overcome.
    ROUND(AVG(SQRT(2.0) * host_pace_se)
          / NULLIF(AVG(gap_to_next), 0), 2)                       AS cancelled_noise_per_gap
FROM adjacent_gaps

-- Observed (2024 dev build): host_pace_var_share ~0.14, and cancelled_noise_per_gap
-- ~1.23 the host-pace noise that would be injected if NOT cancelled already exceeds
-- the average adjacent pace gap, so keeping it would push order probabilities toward
-- 0.5 (worse for the tighter pairs, where the ratio is several-fold). Cancelling the
-- shared host term is what lets p_beats_next carry real ordering signal.

-- CHECK 2 (run manually): the old heuristic capped confidence ~0.6; p_beats_next
-- should now span up to ~1.0 for well-separated drivers:
--   SELECT MIN(p_beats_next), MAX(p_beats_next),
--          COUNT(*) FILTER (WHERE p_beats_next >= 0.9) AS confident_pairs
--   FROM fct_ghost_race_finish WHERE p_beats_next IS NOT NULL;
