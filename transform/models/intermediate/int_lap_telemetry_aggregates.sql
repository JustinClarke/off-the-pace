-- int_lap_telemetry_aggregates.sql · intermediate · grain: one row per race lap
-- (lap_id)
-- Per-lap telemetry features for the tyre-cliff model. Two
-- families:
--   * powertrain (6): straight per-lap aggregates of the car channels
--   * telemetry-cliff (5): within-stint-drift signals, each measured vs the
--   driver's OWN
--     early-stint baseline so the feature is "how far has this lap drifted",
--     not an absolute
--
-- Design note: the cliff features are computed LAP-INTERNALLY (local speed
-- minima, brake-onset
-- events, sample-level accel) rather than via the dim_corners catalogue. The
-- lap-internal
-- formulation needs no named-corner mapping at all and is faithful to the
-- intent (mid-corner =
-- the lap's slow points); dim_corners now covers 34 of 36 event slugs, so the
-- choice is about
-- what the feature measures, not about coverage. Missingness is explicit (LEFT
-- JOIN, NULLs preserved → XGBoost native).
--
-- Sample stream is filtered to source_channel='car' (the genuine channel
-- cadence); the merged
-- 'pos'/'interpolation' samples are forward-filled duplicates that would
-- double-count events.
{{ config(materialized='table') }}

WITH tel AS (
    SELECT
        race_id,
        driver_id,
        lap_number,
        distance_m,
        session_time_s,
        speed_kph,
        throttle_pct,
        brake_applied,
        rpm,
        n_gear,
        drs_active
    FROM {{ ref('stg_telemetry') }}
    WHERE source_channel = 'car'
),

-- Sample-level derivatives within each lap, distance-ordered with the sample
-- clock as tie-break. distance_m alone is not a total order (see
-- stg_telemetry):
-- ordering on it alone let LAG/LEAD pick an arbitrary neighbour inside a tied
-- block, so two builds of this identical SQL disagreed on ~500 laps -- up to 20
-- gear changes and 355 m of braking-point drift apart.
sample_derived AS (
    SELECT
        race_id,
        driver_id,
        lap_number,
        distance_m,
        speed_kph,
        throttle_pct,
        brake_applied,
        rpm,
        n_gear,
        drs_active,
        speed_kph - LAG(speed_kph) OVER w AS dv_kph,
        distance_m - LAG(distance_m) OVER w AS dx_m,
        LAG(speed_kph) OVER w AS prev_speed_kph,
        LEAD(speed_kph) OVER w AS next_speed_kph,
        LAG(brake_applied) OVER w AS prev_brake,
        LAG(n_gear) OVER w AS prev_gear,
        LAG(rpm) OVER w AS prev_rpm,
        MAX(speed_kph) OVER lap AS lap_max_speed_kph,
        MAX(rpm) OVER lap AS lap_max_rpm
    FROM tel
    WINDOW
        w AS (
            PARTITION BY race_id, driver_id, lap_number
            ORDER BY distance_m, session_time_s
        ),
        lap AS (PARTITION BY race_id, driver_id, lap_number)
),

-- Boolean sample flags for the per-lap aggregates.
sample_flags AS (
    SELECT
        race_id,
        driver_id,
        lap_number,
        rpm,
        throttle_pct,
        drs_active,
        CASE WHEN dx_m > 0 THEN dv_kph / dx_m END AS accel_kph_per_m,

        -- powertrain
        CASE WHEN n_gear <> prev_gear THEN 1 ELSE 0 END AS is_gear_change,
        CASE WHEN n_gear > prev_gear THEN 1 ELSE 0 END AS is_upshift,
        CASE
            WHEN
                n_gear > prev_gear AND prev_rpm < 0.92 * lap_max_rpm
                THEN 1
            ELSE 0
        END AS is_short_upshift,
        CASE WHEN throttle_pct >= 99.5 THEN 1.0 ELSE 0.0 END
            AS is_full_throttle,

        -- mid-corner minima: slower than both neighbours and below 75% of lap
        -- max (a corner apex)
        CASE
            WHEN
                speed_kph <= prev_speed_kph
                AND speed_kph <= next_speed_kph
                AND speed_kph < 0.75 * lap_max_speed_kph
                THEN speed_kph
        END AS local_min_speed_kph,

        -- brake-onset distance: brake engages this sample, was off the previous
        -- one
        CASE
            WHEN
                brake_applied AND NOT COALESCE(prev_brake, FALSE)
                THEN distance_m
        END AS brake_onset_m,

        -- traction/wheelspin: near-full throttle below top speed (corner-exit
        -- region) but not accelerating
        CASE
            WHEN
                throttle_pct >= 98 AND speed_kph < 0.85 * lap_max_speed_kph
                THEN 1
            ELSE 0
        END AS is_exit_full_throttle,
        CASE
            WHEN
                throttle_pct >= 98 AND speed_kph < 0.85 * lap_max_speed_kph
                AND dx_m > 0 AND (dv_kph / dx_m) <= 0
                THEN 1
            ELSE 0
        END AS is_wheelspin,

        -- lift & coast: off throttle, not braking, decelerating (confound: fuel
        -- saving see flag note)
        CASE
            WHEN
                throttle_pct < 20
                AND NOT brake_applied
                AND dx_m > 0
                AND (dv_kph / dx_m) < 0
                THEN 1.0
            ELSE 0.0
        END AS is_lift_coast
    FROM sample_derived
),

lap_agg AS (
    SELECT
        race_id,
        driver_id,
        lap_number,

        -- powertrain (6)
        CAST(SUM(is_gear_change) AS INTEGER) AS n_gear_changes,
        AVG(rpm) AS mean_rpm,
        MAX(rpm) AS max_rpm,
        AVG(is_full_throttle) AS pct_full_throttle,
        AVG(CASE WHEN drs_active THEN 1.0 ELSE 0.0 END) AS pct_drs_active,
        CASE
            WHEN SUM(is_upshift) > 0
                THEN CAST(SUM(is_short_upshift) AS DOUBLE) / SUM(is_upshift)
        END AS short_shift_index,

        -- raw lap measures feeding the within-stint-drift cliff features
        AVG(local_min_speed_kph) AS lap_corner_min_speed_kph,
        AVG(brake_onset_m) AS lap_brake_onset_m,
        CASE
            WHEN SUM(is_exit_full_throttle) > 0
                THEN
                    CAST(SUM(is_wheelspin) AS DOUBLE)
                    / SUM(is_exit_full_throttle)
        END AS traction_wheelspin_proxy,
        AVG(is_lift_coast) AS lift_coast_share
    FROM sample_flags
    GROUP BY 1, 2, 3
),

-- Lap identity + stint structure + masking flags (race-lap universe = the
-- mart's spine).
ident AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        is_out_lap,
        is_in_lap
    FROM {{ ref('int_lap_anomaly_flags') }}
),

joined AS (
    SELECT
        i.lap_id,
        i.stint_id,
        i.race_year,
        i.race_id,
        i.driver_id,
        i.lap_number,
        i.lap_in_stint,
        i.is_out_lap,
        i.is_in_lap,
        la.n_gear_changes,
        la.mean_rpm,
        la.max_rpm,
        la.pct_full_throttle,
        la.pct_drs_active,
        la.short_shift_index,
        la.lap_corner_min_speed_kph,
        la.lap_brake_onset_m,
        la.traction_wheelspin_proxy,
        la.lift_coast_share
    FROM ident AS i
    LEFT JOIN lap_agg AS la
        ON
            i.race_id = la.race_id
            AND i.driver_id = la.driver_id
            AND i.lap_number = la.lap_number
),

-- Early-stint baseline (green laps 2–5, excluding out/in laps) per stint,
-- broadcast to every lap.
with_baseline AS (
    SELECT
        *,
        AVG(CASE
            WHEN
                lap_in_stint BETWEEN 2 AND 5
                AND NOT is_out_lap
                AND NOT is_in_lap
                THEN lap_corner_min_speed_kph
        END) OVER stint AS base_corner_min_speed_kph,
        AVG(CASE
            WHEN
                lap_in_stint BETWEEN 2 AND 5
                AND NOT is_out_lap
                AND NOT is_in_lap
                THEN pct_full_throttle
        END) OVER stint AS base_pct_full_throttle,
        AVG(CASE
            WHEN
                lap_in_stint BETWEEN 2 AND 5
                AND NOT is_out_lap
                AND NOT is_in_lap
                THEN lap_brake_onset_m
        END) OVER stint AS base_brake_onset_m
    FROM joined
    WINDOW stint AS (PARTITION BY stint_id)
)

SELECT
    lap_id,
    stint_id,
    race_year,
    race_id,
    driver_id,
    lap_number,

    -- powertrain group (6)
    n_gear_changes,
    mean_rpm,
    max_rpm,
    pct_full_throttle,
    pct_drs_active,
    short_shift_index,

    -- telemetry-cliff group (5): within-stint drift, positive = fading vs own
    -- early-stint baseline
    base_corner_min_speed_kph
    - lap_corner_min_speed_kph AS mid_corner_speed_loss_kph,
    traction_wheelspin_proxy,
    base_pct_full_throttle - pct_full_throttle AS throttle_trace_decay,
    base_brake_onset_m - lap_brake_onset_m AS braking_point_drift_m,
    -- Off-throttle, non-braking, decelerating share of the lap. Continuous (a
    -- boolean flag
    -- degenerates every lap coasts a little). CONFOUND: fuel-saving
    -- lift-and-coast is
    -- indistinguishable from tyre-managing here; consumed alongside
    -- int_lap_fuel_state's
    -- fuel_delta_vs_expected so the model can separate them never silently
    -- equated with deg.
    lift_coast_share
FROM with_baseline
