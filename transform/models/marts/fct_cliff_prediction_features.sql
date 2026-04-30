-- Gold layer: lap-grain feature table for tyre cliff XGBoost model.
-- Grain: lap_id one row per valid race lap.
-- Target: next_lap_degradation_jump_s the increase in driver skill residual on the next lap
--         (positive = tyre getting worse). NULL on the last lap of each stint.
--
-- LEAKAGE WARNING: driver_skill_proxy_s and synthetic-teammate features are deliberately
-- excluded they causally encode the label and would contaminate a predictive model.
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
        COALESCE(ai.dirty_air_share_lap, 0.0)           AS dirty_air_share_lap,
        COALESCE(ai.dirty_air_thermal_load_surface, 0.0) AS dirty_air_thermal_load_surface,
        COALESCE(ai.dirty_air_thermal_load_bulk, 0.0)   AS dirty_air_thermal_load_bulk,
        COALESCE(ai.air_state_dominant, 'free_air')     AS air_state_dominant,

        -- Event flag: any event contamination on this lap
        COALESCE(cor.correction_weight < 1.0, FALSE)    AS event_flag_any,

        -- Compound continuous features (from dim_compounds_season)
        cp.compound_grip_peak,
        cp.compound_wear_gradient,
        cp.compound_optimal_temp_low,
        cp.compound_optimal_temp_high,
        cp.compound_cliff_onset_laps,
        cp.compound_cliff_severity,

        -- Track context
        dc.track_energy_index,
        dc.abrasiveness_index                           AS circuit_abrasiveness_index

    FROM residuals r
    LEFT JOIN anomaly a             USING (lap_id)
    LEFT JOIN cliff c               USING (lap_id)
    LEFT JOIN thermal th            USING (lap_id)
    LEFT JOIN air ai                USING (lap_id)
    LEFT JOIN corrections cor       USING (lap_id)
    LEFT JOIN race_to_track rtt     USING (race_id)
    LEFT JOIN dim_circuits dc       USING (circuit_key)
    LEFT JOIN compound_params cp
        ON rtt.circuit_key          = cp.circuit_key
        AND r.compound              = cp.compound_code
        AND r.race_year             = cp.season
),

-- Compute targets: single-lap and multi-horizon degradation jumps.
with_target AS (
    SELECT
        *,
        -- Single-lap target: increase in driver skill residual on the NEXT lap.
        -- Capped at 30s: values above are physically impossible and indicate upstream
        -- anomalies (SC laps mislabelled in stint, sensor glitches, etc.).
        CASE
            WHEN LEAD(driver_skill_residual_s, 1) OVER w IS NULL THEN NULL
            ELSE LEAST(
                GREATEST(
                    LEAD(driver_skill_residual_s, 1) OVER w-driver_skill_residual_s,
                    0),
                30.0)
        END AS next_lap_degradation_jump_s,

        -- 3-lap cumulative target: sum of next 3 laps minus current
        CASE
            WHEN LEAD(lap_in_stint, 3) OVER w IS NOT NULL
            THEN GREATEST(
                LEAD(driver_skill_residual_s, 1) OVER w
                + LEAD(driver_skill_residual_s, 2) OVER w
                + LEAD(driver_skill_residual_s, 3) OVER w
               -driver_skill_residual_s,
                0)
            ELSE NULL
        END AS next_3_lap_cumulative_jump_s,

        -- 5-lap cumulative target: sum of next 5 laps minus current
        CASE
            WHEN LEAD(lap_in_stint, 5) OVER w IS NOT NULL
            THEN GREATEST(
                LEAD(driver_skill_residual_s, 1) OVER w
                + LEAD(driver_skill_residual_s, 2) OVER w
                + LEAD(driver_skill_residual_s, 3) OVER w
                + LEAD(driver_skill_residual_s, 4) OVER w
                + LEAD(driver_skill_residual_s, 5) OVER w
               -driver_skill_residual_s,
                0)
            ELSE NULL
        END AS next_5_lap_cumulative_jump_s,

        -- Cliff bucket class: laps until >1.0s jump, or none in stint
        CASE
            WHEN LEAD(lap_in_stint, 1) OVER w IS NULL
                THEN NULL
            WHEN (LEAD(driver_skill_residual_s, 1) OVER w-driver_skill_residual_s) > 1.0
                THEN '0_to_2'
            WHEN LEAD(lap_in_stint, 2) OVER w IS NOT NULL
                AND (LEAD(driver_skill_residual_s, 2) OVER w-driver_skill_residual_s) > 1.0
                THEN '0_to_2'
            WHEN LEAD(lap_in_stint, 3) OVER w IS NOT NULL
                AND (LEAD(driver_skill_residual_s, 3) OVER w-driver_skill_residual_s) > 1.0
                THEN '3_to_5'
            WHEN LEAD(lap_in_stint, 5) OVER w IS NOT NULL
                AND (LEAD(driver_skill_residual_s, 5) OVER w-driver_skill_residual_s) > 1.0
                THEN '3_to_5'
            WHEN LEAD(lap_in_stint, 6) OVER w IS NOT NULL
                AND (LEAD(driver_skill_residual_s, 6) OVER w-driver_skill_residual_s) > 1.0
                THEN '6_plus'
            WHEN LEAD(lap_in_stint, 1) OVER w IS NOT NULL
                THEN 'none_in_stint'
            ELSE NULL
        END AS laps_until_cliff_class

    FROM base
    WINDOW w AS (PARTITION BY stint_id ORDER BY lap_in_stint)
)

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

    -- Compound continuous features
    compound_grip_peak,
    compound_wear_gradient,
    compound_optimal_temp_low,
    compound_optimal_temp_high,
    compound_cliff_onset_laps,
    compound_cliff_severity,

    -- Thermal predictors
    push_residual,
    cumulative_push_load_surface,
    cumulative_push_load_bulk,

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

    -- Fuel and event
    fuel_mass_kg,
    event_flag_any,

    -- Anomaly metadata
    cliff_candidate_flag,
    anomaly_class,
    is_rain_lap,

    -- Targets: single-lap and multi-horizon
    next_lap_degradation_jump_s,
    next_3_lap_cumulative_jump_s,
    next_5_lap_cumulative_jump_s,
    laps_until_cliff_class,

    -- Training eligibility: exclude early stint warmup and obvious anomalies.
    -- COALESCE guards against NULLs from LEFT JOINs producing NULL boolean.
    COALESCE(
        age_in_stint > 3
        AND COALESCE(anomaly_class, 'normal') NOT IN ('mistake', 'conditions'),
        FALSE
    )                                                   AS is_training_eligible

FROM with_target
ORDER BY race_year, race_id, driver_id, stint_id, lap_in_stint
