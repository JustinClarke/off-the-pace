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
        stint_length_actual
    FROM {{ ref('int_stint_geometry') }}
),

laps AS (
    SELECT lap_id, lap_time_s
    FROM {{ ref('stg_laps') }}
    WHERE is_valid_lap = TRUE
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
        l.lap_time_s,
        -- 60th percentile cut-off lap position (min 3 to have enough data)
        GREATEST(CEIL(g.stint_length_actual * 0.60), 3) AS baseline_cutoff_lap
    FROM geom g
    JOIN laps l USING (lap_id)
),

-- Pre-aggregate median over baseline window (laps ≤ cutoff) per stint.
-- DuckDB does not support FILTER in ordered-set aggregates inside window functions,
-- so we compute one value per stint via a plain GROUP BY first.
stint_baseline_agg AS (
    SELECT
        stint_id,
        MEDIAN(lap_time_s) FILTER (WHERE lap_in_stint <= baseline_cutoff_lap)
                                       AS stint_baseline_pace
    FROM combined
    GROUP BY stint_id
),

with_baseline AS (
    SELECT
        c.*,
        s.stint_baseline_pace
    FROM combined c
    JOIN stint_baseline_agg s USING (stint_id)
),

with_residual AS (
    SELECT
        *,
        -- Positive = faster than baseline = pushing harder
        stint_baseline_pace-lap_time_s   AS push_residual
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
        4) AS cumulative_push_load_surface,

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
        4) AS cumulative_push_load_bulk

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
