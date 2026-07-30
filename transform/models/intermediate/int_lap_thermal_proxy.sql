-- Layer 03: Push-intensity proxy for tyre thermal load.
-- Baseline pace = rolling median of lap times over the first 60% of each stint
-- (computed as PERCENTILE_CONT(0.5) over an expanding window capped at the
-- 60th-percentile lap_in_stint position). This avoids the cliff distorting the
-- slope see 02_physics_layer.md for rationale.
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
        stint_length_actual,
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
        g.stint_length_actual,
        g.is_valid_lap,
        l.lap_time_s,
        -- 60th percentile cut-off lap position (min 3 to have enough data)
        GREATEST(CEIL(g.stint_length_actual * 0.60), 3) AS baseline_cutoff_lap
    FROM geom AS g
    INNER JOIN laps AS l ON g.lap_id = l.lap_id
),

-- Pre-aggregate median over baseline window (laps ≤ cutoff) per stint.
-- DuckDB does not support FILTER in ordered-set aggregates inside window
-- functions,
-- so we compute one value per stint via a plain GROUP BY first.
-- Baseline is computed from valid laps only (SC/pit laps would drag the
-- median pace down and distort the push-residual signal).
stint_baseline_agg AS (
    SELECT
        stint_id,
        MEDIAN(lap_time_s)
        FILTER (WHERE lap_in_stint <= baseline_cutoff_lap AND is_valid_lap)
            AS stint_baseline_pace
    FROM combined
    GROUP BY stint_id
),

with_baseline AS (
    SELECT
        c.*,
        s.stint_baseline_pace
    FROM combined AS c
    INNER JOIN stint_baseline_agg AS s ON c.stint_id = s.stint_id
),

with_residual AS (
    SELECT
        *,
        -- Positive = faster than baseline = pushing harder
        stint_baseline_pace - lap_time_s AS push_residual
    FROM with_baseline
),

-- Cumulative push load via finite EW sum, partitioned on stint_id
-- Surface: τ≈3 laps → α = 1-exp(-1/3) ≈ 0.283 per lag increment
-- Bulk:    τ≈5 laps → α = 1-exp(-1/5) ≈ 0.181 per lag increment
-- Only positive residuals contribute (pushing, not coasting)
thermal AS (
    SELECT
        *,
        -- Surface load (τ=3): 5-lap lookback, only positive residuals
        ROUND(
            GREATEST(push_residual, 0)
            + 0.717 * GREATEST(COALESCE(LAG(push_residual, 1) OVER w, 0), 0)
            + 0.514 * GREATEST(COALESCE(LAG(push_residual, 2) OVER w, 0), 0)
            + 0.369 * GREATEST(COALESCE(LAG(push_residual, 3) OVER w, 0), 0)
            + 0.264 * GREATEST(COALESCE(LAG(push_residual, 4) OVER w, 0), 0),
            4
        ) AS cumulative_push_load_surface,

        -- Bulk load (τ=5): 8-lap lookback, only positive residuals
        ROUND(
            GREATEST(push_residual, 0)
            + 0.819 * GREATEST(COALESCE(LAG(push_residual, 1) OVER w, 0), 0)
            + 0.670 * GREATEST(COALESCE(LAG(push_residual, 2) OVER w, 0), 0)
            + 0.549 * GREATEST(COALESCE(LAG(push_residual, 3) OVER w, 0), 0)
            + 0.449 * GREATEST(COALESCE(LAG(push_residual, 4) OVER w, 0), 0)
            + 0.368 * GREATEST(COALESCE(LAG(push_residual, 5) OVER w, 0), 0)
            + 0.301 * GREATEST(COALESCE(LAG(push_residual, 6) OVER w, 0), 0)
            + 0.247 * GREATEST(COALESCE(LAG(push_residual, 7) OVER w, 0), 0),
            4
        ) AS cumulative_push_load_bulk

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
    push_residual,
    cumulative_push_load_surface,
    cumulative_push_load_bulk
FROM thermal
-- Deliberately NOT filtered to valid laps here (mirrors int_lap_air_state):
-- downstream consumers key off int_lap_residual_decomposed (valid-only) so
-- the extra SC/pit rows are naturally excluded by their joins, and keeping
-- them here preserves lap_in_stint=1 rows that
-- assert_stint_boundary_integrity depends on to check no cross-stint bleed.
