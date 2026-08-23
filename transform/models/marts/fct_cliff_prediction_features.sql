-- Gold layer: lap-grain feature table for tyre cliff XGBoost model.
-- Grain: lap_id one row per valid race lap.
-- Targets: next_lap_degradation_jump_detrended_s (PRIMARY, detrended) and
--          next_lap_degradation_jump_s (legacy, kept for diff/gate).
--
-- LEAKAGE WARNING: driver_skill_proxy_s and synthetic-teammate features are
-- deliberately
-- excluded they causally encode the label and would contaminate a predictive
-- model.
-- This mart must never reference int_synthetic_teammate.
{{ config(materialized='table') }}

WITH residuals AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        constructor_id,
        lap_number,
        lap_in_stint,
        age_in_stint,
        compound,
        fuel_mass_kg,
        correction_weight,
        driver_skill_residual_s
    FROM {{ ref('int_lap_residual_decomposed') }}
),

anomaly AS (
    SELECT
        lap_id,
        anomaly_class,
        cliff_candidate_flag,
        is_rain_lap
    FROM {{ ref('int_lap_anomaly_flags') }}
),

cliff AS (
    SELECT
        lap_id,
        expected_compound_pace_s,
        expected_degradation_rate_s_per_lap,
        cliff_onset_passed,
        laps_past_cliff,
        ambient_temp_delta
    FROM {{ ref('int_compound_cliff_predicted') }}
),

thermal AS (
    SELECT
        lap_id,
        push_residual,
        cumulative_push_load_surface,
        cumulative_push_load_bulk
    FROM {{ ref('int_lap_thermal_proxy') }}
),

air AS (
    SELECT
        lap_id,
        dirty_air_share_lap,
        dirty_air_thermal_load_surface,
        dirty_air_thermal_load_bulk,
        air_state_dominant
    FROM {{ ref('int_lap_air_state') }}
),

corrections AS (
    SELECT
        lap_id,
        correction_class,
        correction_weight
    FROM {{ ref('int_event_corrections') }}
),

-- C1: per-stint linear drift of driver_skill_residual_s (pre-cliff only).
-- Used to produce next_lap_degradation_jump_detrended_s.
detrend AS (
    SELECT stint_id, drift_s_per_lap
    FROM {{ ref('int_lap_residual_stint_detrend') }}
),

-- C2: empirical survival curve P(stint reaches lap_in_stint) per compound.
-- Numerator = stints with a valid lap at that lap_in_stint; denominator = total
-- stints
-- of that compound. IPW = 1/P clipped to [0.25, 4] to control variance in the
-- tail.
total_per_compound AS (
    SELECT compound, COUNT(DISTINCT stint_id) AS n_total
    FROM {{ ref('int_lap_residual_decomposed') }}
    GROUP BY compound
),

stints_reaching AS (
    SELECT
        d.compound,
        d.lap_in_stint,
        COUNT(DISTINCT d.stint_id) AS n_reaching
    FROM {{ ref('int_lap_residual_decomposed') }} AS d
    GROUP BY d.compound, d.lap_in_stint
),

stint_survival AS (
    SELECT
        sr.compound,
        sr.lap_in_stint,
        sr.n_reaching * 1.0 / tp.n_total AS survival_prob
    FROM stints_reaching AS sr
    INNER JOIN total_per_compound AS tp ON sr.compound = tp.compound
),

-- Per-lap telemetry features: powertrain + within-stint-drift
-- cliff signals.
-- LEFT JOINed → explicit NULL on laps with no telemetry (carried as XGBoost
-- native-NaN).
telemetry AS (
    SELECT
        lap_id,
        n_gear_changes,
        mean_rpm,
        max_rpm,
        pct_full_throttle,
        pct_drs_active,
        short_shift_index,
        mid_corner_speed_loss_kph,
        traction_wheelspin_proxy,
        throttle_trace_decay,
        braking_point_drift_m,
        lift_coast_share
    FROM {{ ref('int_lap_telemetry_aggregates') }}
),

-- Resolve compound cliff parameters from dim_compounds_season.
-- Join on (circuit_key, compound, season) via race_to_track seed.
race_to_track AS (
    SELECT race_id, track_id AS circuit_key
    FROM {{ ref('race_to_track') }}
),

compound_params AS (
    SELECT
        circuit_key,
        compound_code,
        season,
        compound_grip_peak,
        compound_wear_gradient,
        compound_optimal_temp_low,
        compound_optimal_temp_high,
        compound_cliff_onset_laps,
        compound_cliff_severity
    FROM {{ ref('dim_compounds_season') }}
),

dim_circuits AS (
    SELECT
        circuit_key,
        track_energy_index,
        abrasiveness_index
    FROM {{ ref('dim_circuits') }}
),

-- Assemble lap-grain base before window functions
base AS (
    SELECT
        r.lap_id,
        r.stint_id,
        r.race_year,
        r.race_id,
        rtt.circuit_key,
        r.driver_id,
        r.constructor_id,
        r.lap_number,
        r.lap_in_stint,
        r.age_in_stint,
        r.compound,
        r.fuel_mass_kg,
        r.driver_skill_residual_s,

        -- Anomaly metadata
        a.anomaly_class,
        a.cliff_candidate_flag,
        a.is_rain_lap,

        -- Cliff prediction
        c.expected_compound_pace_s,
        c.expected_degradation_rate_s_per_lap,
        c.cliff_onset_passed,
        c.laps_past_cliff,
        c.ambient_temp_delta,

        -- Thermal predictors
        th.push_residual,
        th.cumulative_push_load_surface,
        th.cumulative_push_load_bulk,

        -- Dirty air predictors
        COALESCE(ai.dirty_air_share_lap, 0.0) AS dirty_air_share_lap,
        COALESCE(ai.dirty_air_thermal_load_surface, 0.0)
            AS dirty_air_thermal_load_surface,
        COALESCE(ai.dirty_air_thermal_load_bulk, 0.0)
            AS dirty_air_thermal_load_bulk,
        COALESCE(ai.air_state_dominant, 'free_air') AS air_state_dominant,

        -- Event flag: any event contamination on this lap
        COALESCE(cor.correction_weight < 1.0, FALSE) AS event_flag_any,

        -- Compound continuous features (from dim_compounds_season)
        cp.compound_grip_peak,
        cp.compound_wear_gradient,
        cp.compound_optimal_temp_low,
        cp.compound_optimal_temp_high,
        cp.compound_cliff_onset_laps,
        cp.compound_cliff_severity,

        -- Track context
        dc.track_energy_index,
        dc.abrasiveness_index AS circuit_abrasiveness_index,

        -- Telemetry features (powertrain + within-stint-drift cliff signals)
        tel.n_gear_changes,
        tel.mean_rpm,
        tel.max_rpm,
        tel.pct_full_throttle,
        tel.pct_drs_active,
        tel.short_shift_index,
        tel.mid_corner_speed_loss_kph,
        tel.traction_wheelspin_proxy,
        tel.throttle_trace_decay,
        tel.braking_point_drift_m,
        tel.lift_coast_share,

        -- C1: per-stint drift slope (s/lap), used to compute detrended jump
        -- target.
        COALESCE(det.drift_s_per_lap, 0.0) AS drift_s_per_lap,

        -- C2: IPW survival weight 1/P(stint reaches this lap) per compound,
        -- clipped [0.25, 4].
        COALESCE(
            GREATEST(0.25, LEAST(4.0, 1.0 / NULLIF(ss.survival_prob, 0.0))),
            1.0
        ) AS survival_weight,

        -- C3: surface/total thermal load ratio warm-up attribution feature.
        COALESCE(th.cumulative_push_load_surface, 0.0)
        / NULLIF(
            COALESCE(th.cumulative_push_load_surface, 0.0)
            + COALESCE(th.cumulative_push_load_bulk, 0.0),
            0.0
        ) AS surface_bulk_ratio

    FROM residuals AS r
    LEFT JOIN anomaly AS a ON r.lap_id = a.lap_id
    LEFT JOIN cliff AS c ON r.lap_id = c.lap_id
    LEFT JOIN thermal AS th ON r.lap_id = th.lap_id
    LEFT JOIN air AS ai ON r.lap_id = ai.lap_id
    LEFT JOIN corrections AS cor ON r.lap_id = cor.lap_id
    LEFT JOIN telemetry AS tel ON r.lap_id = tel.lap_id
    LEFT JOIN race_to_track AS rtt ON r.race_id = rtt.race_id
    LEFT JOIN dim_circuits AS dc ON rtt.circuit_key = dc.circuit_key
    LEFT JOIN compound_params AS cp
        ON
            rtt.circuit_key = cp.circuit_key
            AND r.compound = cp.compound_code
            AND r.race_year = cp.season
    LEFT JOIN detrend AS det ON r.stint_id = det.stint_id
    LEFT JOIN
        stint_survival AS ss
        ON r.compound = ss.compound AND r.lap_in_stint = ss.lap_in_stint
),

-- Forward scan for the cliff bucket class.
-- Scans EVERY remaining lap of the stint at TRUE lap offsets and takes the
-- first crossing of the >1.0s detrended threshold. The previous formulation
-- tested a fixed set of LEAD offsets -- {1,2} -> 0_to_2, {3,5} -> 3_to_5,
-- {6} -> 6_plus -- which had three defects: offset 4 was never tested;
-- nothing past 6 was tested, so `6_plus` meant "exactly 6"; and LEAD steps
-- rows, not laps, so the horizon drifts wherever
-- int_lap_residual_decomposed has dropped a lap (1.7% of steps at horizon 1,
-- 9.0% at horizon 6). A cliff 4 laps out, or 7+ laps out, fell through to
-- 'none_in_stint'.
cliff_horizon AS (
    SELECT
        stint_id,
        MAX(lap_in_stint) AS last_lap_in_stint
    FROM base
    GROUP BY stint_id
),

cliff_scan AS (
    SELECT
        a.lap_id,
        MIN(f.lap_in_stint - a.lap_in_stint) AS laps_until_cliff
    FROM base AS a
    INNER JOIN base AS f
        ON
            a.stint_id = f.stint_id
            AND a.lap_in_stint < f.lap_in_stint
            AND (
                f.driver_skill_residual_s
                - a.driver_skill_residual_s
                - (f.lap_in_stint - a.lap_in_stint) * a.drift_s_per_lap
            ) > 1.0
    GROUP BY a.lap_id
),

-- Compute targets: single-lap and multi-horizon degradation jumps.
with_target AS (
    SELECT
        *,
        -- Single-lap target (legacy, kept alongside detrended for diff/gate).
        CASE
            WHEN LEAD(driver_skill_residual_s, 1) OVER w IS NULL THEN NULL
            ELSE GREATEST(
                LEAST(
                    LEAD(driver_skill_residual_s, 1) OVER w
                    - driver_skill_residual_s,
                    10.0
                ),
                -10.0
            )
        END AS next_lap_degradation_jump_s,

        -- C1 PRIMARY target: detrended single-lap jump with per-stint
        -- fuel/track drift removed.
        -- drift_s_per_lap is the OLS slope of residual ~ lap_in_stint on
        -- pre-cliff laps.
        -- Subtracting it removes the systematic ~-0.07 s/lap leak (Step 0:
        -- median slope).
        -- Bounded [-10, 10] same as legacy target.
        CASE
            WHEN LEAD(driver_skill_residual_s, 1) OVER w IS NULL THEN NULL
            ELSE GREATEST(
                LEAST(
                    LEAD(driver_skill_residual_s, 1) OVER w
                    - driver_skill_residual_s
                    - drift_s_per_lap,
                    10.0
                ),
                -10.0
            )
        END AS next_lap_degradation_jump_detrended_s,

        -- Multi-horizon cumulative targets: the sum of the next k detrended
        -- single-lap jumps, i.e. SUM over i=1..k of
        --   (residual(t+i) - residual(t) - i * drift_s_per_lap)
        -- = SUM(LEAD(residual, i)) - k * residual - drift * k(k+1)/2.
        -- The current residual is subtracted k times, once per horizon step,
        -- and the per-stint drift is removed on the same schedule the
        -- single-lap detrended target uses. Bounded symmetrically at k * 10.0
        -- s, the per-lap bound scaled by the horizon; there is deliberately no
        -- floor at zero, because a cumulative jump is signed -- laps that
        -- recover pace are as real as laps that lose it.
        --
        -- The guard is `LEAD(lap_in_stint, k) = lap_in_stint + k`, not
        -- `IS NOT NULL`: LEAD steps rows, not laps, and 4.1% (k=3) / 5.8%
        -- (k=5) of rows sit on a stint whose lap numbering has a hole. Summing
        -- across one silently measures a longer horizon than the column name
        -- claims. Same defect class as the cliff label repair.
        CASE
            WHEN LEAD(lap_in_stint, 3) OVER w = lap_in_stint + 3
                THEN GREATEST(
                    LEAST(
                        LEAD(driver_skill_residual_s, 1) OVER w
                        + LEAD(driver_skill_residual_s, 2) OVER w
                        + LEAD(driver_skill_residual_s, 3) OVER w
                        - 3 * driver_skill_residual_s
                        - 6 * drift_s_per_lap,
                        30.0
                    ),
                    -30.0
                )
        END AS next_3_lap_cumulative_jump_s,

        CASE
            WHEN LEAD(lap_in_stint, 5) OVER w = lap_in_stint + 5
                THEN GREATEST(
                    LEAST(
                        LEAD(driver_skill_residual_s, 1) OVER w
                        + LEAD(driver_skill_residual_s, 2) OVER w
                        + LEAD(driver_skill_residual_s, 3) OVER w
                        + LEAD(driver_skill_residual_s, 4) OVER w
                        + LEAD(driver_skill_residual_s, 5) OVER w
                        - 5 * driver_skill_residual_s
                        - 15 * drift_s_per_lap,
                        50.0
                    ),
                    -50.0
                )
        END AS next_5_lap_cumulative_jump_s

    FROM base
    WINDOW w AS (PARTITION BY stint_id ORDER BY lap_in_stint)
),

-- Bucket the first-crossing offset. The buckets partition the horizon exactly
-- as their names read: 6_plus is 6-or-more, not exactly 6, and none_in_stint
-- means no crossing anywhere in the remaining stint. NULL on a stint's last
-- lap, which has no horizon to scan.
with_cliff_class AS (
    SELECT
        wt.*,
        CASE
            WHEN ch.last_lap_in_stint <= wt.lap_in_stint THEN NULL
            WHEN cs.laps_until_cliff <= 2 THEN '0_to_2'
            WHEN cs.laps_until_cliff <= 5 THEN '3_to_5'
            WHEN cs.laps_until_cliff IS NOT NULL THEN '6_plus'
            ELSE 'none_in_stint'
        END AS laps_until_cliff_class
    FROM with_target AS wt
    LEFT JOIN cliff_scan AS cs ON wt.lap_id = cs.lap_id
    LEFT JOIN cliff_horizon AS ch ON wt.stint_id = ch.stint_id
)

SELECT
    lap_id,
    stint_id,
    race_year,
    race_id,
    circuit_key,
    driver_id,
    constructor_id,
    lap_number,
    lap_in_stint,
    age_in_stint,
    compound,

    -- Compound continuous features
    compound_grip_peak,
    compound_wear_gradient,
    compound_optimal_temp_low,
    compound_optimal_temp_high,
    compound_cliff_onset_laps,
    compound_cliff_severity,

    -- Thermal predictors (C3: surface_bulk_ratio added as 42nd feature)
    push_residual,
    cumulative_push_load_surface,
    cumulative_push_load_bulk,
    surface_bulk_ratio,

    -- Dirty air predictors
    dirty_air_share_lap,
    dirty_air_thermal_load_surface,
    dirty_air_thermal_load_bulk,
    air_state_dominant,

    -- Cliff prediction features
    expected_compound_pace_s,
    expected_degradation_rate_s_per_lap,
    cliff_onset_passed,
    laps_past_cliff,
    ambient_temp_delta,

    -- Track context
    track_energy_index,
    circuit_abrasiveness_index,

    -- Telemetry: powertrain group
    n_gear_changes,
    mean_rpm,
    max_rpm,
    pct_full_throttle,
    pct_drs_active,
    short_shift_index,

    -- Telemetry: within-stint-drift cliff signals
    mid_corner_speed_loss_kph,
    traction_wheelspin_proxy,
    throttle_trace_decay,
    braking_point_drift_m,
    lift_coast_share,

    -- Fuel and event
    fuel_mass_kg,
    event_flag_any,

    -- Anomaly metadata
    cliff_candidate_flag,
    anomaly_class,
    is_rain_lap,

    -- Targets: detrended (primary) + legacy + multi-horizon
    next_lap_degradation_jump_detrended_s,
    next_lap_degradation_jump_s,
    next_3_lap_cumulative_jump_s,
    next_5_lap_cumulative_jump_s,
    laps_until_cliff_class,

    -- C2: IPW survival weight (carried as metadata for train.py, not a feature)
    survival_weight,

    -- Training eligibility: exclude early stint warmup and obvious anomalies.
    -- COALESCE guards against NULLs from LEFT JOINs producing NULL boolean.
    COALESCE(
        age_in_stint > 3
        AND COALESCE(anomaly_class, 'normal') NOT IN ('mistake', 'conditions'),
        FALSE
    ) AS is_training_eligible

FROM with_cliff_class
ORDER BY race_year, race_id, driver_id, stint_id, lap_in_stint
