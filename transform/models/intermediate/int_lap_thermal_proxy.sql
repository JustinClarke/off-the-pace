-- Layer 03: Push-intensity proxy for tyre thermal load.
-- Baseline pace = expanding median of this stint's valid lap times over laps
-- STRICTLY BEFORE the lap being scored (macro: trailing_median). A lap is
-- therefore measured against pace that was already on the timing screen when it
-- started see 08e in _improvements/work/08-foundations-repair.md.
--
-- It used to be MEDIAN(lap_time_s) FILTER (lap_in_stint <= CEIL(stint_length_actual*0.60))
-- GROUP BY stint_id, which reached forward twice: the median pooled laps the row
-- had not run yet (55.92% of mart rows, mean 4.65 laps), and the cutoff was a
-- function of stint_length_actual == fct_stint_features.stint_length_laps, the
-- stint-life target's own numerator. Measured before the swap: the contamination
-- INVERTS push_residual's sign against two targets, it does not merely add noise.
--
-- Two properties of the rebuild a consumer must know:
--   1. stint_baseline_pace (and so push_residual, and so both loads) is NULL until
--      the stint has one valid prior lap. Lap 1 is an out-lap, so this is usually
--      laps 1-2. Costs 1.41pp of training-eligible coverage.
--   2. Those NULLs are deterministic on baseline_observations_n, which is shipped
--      beside them precisely because it is NOT derivable from the feature contract
--      (it rises with SC and pit disruption). Condition on it, do not impute it.
--
-- push_residual > 0 means the driver is going faster than the stint baseline,
-- implying higher thermal input to the tyres.
-- cumulative_push_load_surface (τ≈3 laps) captures immediate grip consequences.
-- cumulative_push_load_bulk (τ≈5 laps) captures post-stint cliff acceleration.
{{ config(materialized='table') }}

WITH geom AS (
    SELECT
        stint_id,
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        is_valid_lap
    FROM {{ ref('int_stint_geometry') }}
),

-- Full sequence (SC/VSC/pit/invalid laps included): the LAG window below
-- must run over every lap so the push-residual EWMA decays across a gap
-- instead of treating the lap before/after it as adjacent. Invalid laps are
-- much slower than the stint baseline, so their push_residual is clipped to
-- ~0 by the GREATEST(...,0) below and naturally contribute little.
laps AS (
    SELECT lap_id, lap_time_s
    FROM {{ ref('stg_laps') }}
),

combined AS (
    SELECT
        g.stint_id,
        g.lap_id,
        g.race_year,
        g.race_id,
        g.driver_id,
        g.lap_number,
        g.lap_in_stint,
        g.is_valid_lap,
        l.lap_time_s
    FROM geom AS g
    INNER JOIN laps AS l ON g.lap_id = l.lap_id
),

-- Point-in-time stint baseline. EXPANDING, not trailing-N: a stint is short
-- (mean ~20 laps) so the window is local by construction, and the statistic is
-- meant to be "this stint's own pace so far" -- capping it at N laps would make
-- the baseline itself drift with the degradation it is supposed to measure.
-- The floor is 1 valid prior lap; floors of 2/3/5 buy more degradation signal
-- for 3.49/8.82/19.09pp of coverage and that trade has not been through the gate.
-- Baseline is computed from valid laps only (SC/pit laps would drag the
-- median pace down and distort the push-residual signal).
with_baseline AS (
    SELECT
        *,
        {{ trailing_median(
            'lap_time_s', ['stint_id'], ['lap_in_stint'],
            min_observations=1, valid_condition='is_valid_lap') }}
            AS stint_baseline_pace,
        {{ trailing_observation_count(
            'lap_time_s', ['stint_id'], ['lap_in_stint'],
            valid_condition='is_valid_lap') }}
            AS baseline_observations_n
    FROM combined
),

with_residual AS (
    SELECT
        *,
        -- Positive = faster than baseline = pushing harder.
        -- NULL until the stint has a prior valid lap: unknown, not zero.
        stint_baseline_pace - lap_time_s AS push_residual
    FROM with_baseline
),

-- Cumulative push load via finite EW sum, partitioned on stint_id
-- Surface: τ≈3 laps → α = 1-exp(-1/3) ≈ 0.283 per lag increment
-- Bulk:    τ≈5 laps → α = 1-exp(-1/5) ≈ 0.181 per lag increment
-- Only positive residuals contribute (pushing, not coasting).
-- A NULL residual on a PRIOR lap contributes 0, the same convention the window
-- already uses for laps before the stint started. A NULL residual on the CURRENT
-- lap makes the load NULL rather than 0: GREATEST(NULL, 0) is 0 in DuckDB, which
-- would fabricate "no thermal load" for a lap whose load is simply unknown.
thermal AS (
    SELECT
        *,
        -- Surface load (τ=3): 5-lap lookback, only positive residuals
        CASE WHEN push_residual IS NOT NULL THEN ROUND(
            GREATEST(push_residual, 0)
            + 0.717 * GREATEST(COALESCE(LAG(push_residual, 1) OVER w, 0), 0)
            + 0.514 * GREATEST(COALESCE(LAG(push_residual, 2) OVER w, 0), 0)
            + 0.369 * GREATEST(COALESCE(LAG(push_residual, 3) OVER w, 0), 0)
            + 0.264 * GREATEST(COALESCE(LAG(push_residual, 4) OVER w, 0), 0),
            4
        ) END AS cumulative_push_load_surface,

        -- Bulk load (τ=5): 8-lap lookback, only positive residuals
        CASE WHEN push_residual IS NOT NULL THEN ROUND(
            GREATEST(push_residual, 0)
            + 0.819 * GREATEST(COALESCE(LAG(push_residual, 1) OVER w, 0), 0)
            + 0.670 * GREATEST(COALESCE(LAG(push_residual, 2) OVER w, 0), 0)
            + 0.549 * GREATEST(COALESCE(LAG(push_residual, 3) OVER w, 0), 0)
            + 0.449 * GREATEST(COALESCE(LAG(push_residual, 4) OVER w, 0), 0)
            + 0.368 * GREATEST(COALESCE(LAG(push_residual, 5) OVER w, 0), 0)
            + 0.301 * GREATEST(COALESCE(LAG(push_residual, 6) OVER w, 0), 0)
            + 0.247 * GREATEST(COALESCE(LAG(push_residual, 7) OVER w, 0), 0),
            4
        ) END AS cumulative_push_load_bulk

    FROM with_residual
    WINDOW w AS (
        PARTITION BY stint_id
        ORDER BY lap_in_stint
        ROWS BETWEEN 8 PRECEDING AND CURRENT ROW
    )
)

SELECT
    stint_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    lap_in_stint,
    lap_time_s,
    stint_baseline_pace,
    baseline_observations_n,
    push_residual,
    cumulative_push_load_surface,
    cumulative_push_load_bulk
FROM thermal
-- Deliberately NOT filtered to valid laps here (mirrors int_lap_air_state):
-- downstream consumers key off int_lap_residual_decomposed (valid-only) so
-- the extra SC/pit rows are naturally excluded by their joins, and keeping
-- them here preserves lap_in_stint=1 rows that
-- assert_stint_boundary_integrity depends on to check no cross-stint bleed.
