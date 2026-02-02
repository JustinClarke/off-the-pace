-- Ghost car model: Ghost car pace counterfactual lap time reconstruction.
-- For each (ego_driver, host_constructor, race, lap) combination, predicts
-- the lap time if ego_driver had been in host_constructor's car.
--
-- The recombination formula:
--   predicted_lap_time = base_track_pace
--                      + fuel_component          (circuit/race, not driver-specific)
--                      + driver_skill_residual    (ego driver's actual residual)
--                      + constructor_pace(host)   (host constructor coefficient)
--                      + circuit_x_constructor(host)
--                      + dirty_air_tax             (inherited from ego position)
--                      + compound_component        (inherited from ego strategy)
--                      + rubber_component
--                      + ambient_component
--
-- Degenerate identity: when ego == host, predicted_lap_time == actual_lap_time.
-- The self-consistency test asserts this holds within 0.0001 s.
--
-- Grain: (ego_driver_id, host_constructor_id, race_id, lap_number).
-- PK: ghost_id = hash(ego_driver_id, host_constructor_id, race_id, lap_number).
--
-- Filtered to: host constructors that actually raced in the same race_year
-- as the ego driver lap. Rows where recombination_confidence < 0.05 are excluded.

{{ config(materialized='table', tags=['marts', 'simulation', 'ghost_car']) }}

WITH ego_laps AS (
    -- All ego driver-race-lap combinations with their physics components
    SELECT
        lr.lap_id,
        lr.race_year,
        lr.race_id,
        lr.driver_id                                    AS ego_driver_id,
        lr.constructor_id                               AS ego_constructor_id,
        lr.lap_number,
        lr.base_track_pace_s,
        lr.fuel_component_s,
        lr.compound_component_s,
        lr.rubber_component_s,
        lr.ambient_component_s,
        lr.dirty_air_tax_s,
        lr.driver_skill_residual_s,
        lr.lap_time_s                                   AS actual_lap_time_s,
        lr.correction_weight,
        lr.rainfall_flag
    FROM {{ ref('int_lap_residual_decomposed') }} lr
    WHERE lr.lap_time_s IS NOT NULL
      AND lr.correction_weight = 1.0
      AND COALESCE(lr.rainfall_flag, FALSE) = FALSE
),

-- All valid host constructors per race_year (constructors that actually competed)
host_constructors AS (
    SELECT DISTINCT
        race_year,
        race_id,
        constructor_id                                  AS host_constructor_id
    FROM {{ ref('stg_laps') }}
    WHERE is_valid_lap = TRUE
),

-- Constructor structural pace per host
host_constructor_pace AS (
    SELECT
        race_year,
        race_id,
        constructor_id                                  AS host_constructor_id,
        constructor_structural_pace_s,
        constructor_structural_pace_se_s,
        panel_observations_n
    FROM {{ ref('int_constructor_structural_pace') }}
),

-- Circuit × constructor interaction per host
host_interaction AS (
    SELECT
        race_year,
        race_id,
        constructor_id                                  AS host_constructor_id,
        circuit_constructor_interaction_s,
        interaction_obs_n
    FROM {{ ref('int_circuit_x_constructor_interaction') }}
),

-- Cartesian: every (ego_driver_race_lap) × (valid host_constructor in same race)
ghost_recombined AS (
    SELECT
        MD5(CONCAT(
            el.race_year, '_',
            el.race_id, '_',
            el.ego_driver_id, '_',
            hc.host_constructor_id, '_',
            CAST(el.lap_number AS VARCHAR)
        ))                                              AS ghost_id,
        el.race_year,
        el.race_id,
        el.ego_driver_id,
        hc.host_constructor_id,
        el.ego_constructor_id,
        el.lap_number,
        el.base_track_pace_s,
        el.fuel_component_s,
        el.driver_skill_residual_s,
        el.compound_component_s,
        el.rubber_component_s,
        el.ambient_component_s,
        el.dirty_air_tax_s,
        el.actual_lap_time_s,
        COALESCE(hcp.constructor_structural_pace_s, 0.0)     AS host_constructor_pace_s,
        COALESCE(hcp.constructor_structural_pace_se_s, 0.0)  AS host_constructor_pace_se_s,
        COALESCE(hi.circuit_constructor_interaction_s, 0.0)  AS circuit_interaction_s,
        COALESCE(hcp.panel_observations_n, 0)                AS host_constructor_obs_n,
        COALESCE(hi.interaction_obs_n, 0)                    AS interaction_obs_n,
        -- Recombination confidence: degrades when host has few observations
        CASE
            WHEN COALESCE(hcp.panel_observations_n, 0) >= 100 THEN 0.9
            WHEN COALESCE(hcp.panel_observations_n, 0) >= 50  THEN 0.7
            WHEN COALESCE(hcp.panel_observations_n, 0) >= 20  THEN 0.5
            WHEN COALESCE(hcp.panel_observations_n, 0) > 0    THEN 0.3
            ELSE 0.0
        END                                                  AS recombination_confidence
    FROM ego_laps el
    JOIN host_constructors hc
        ON el.race_year = hc.race_year
        AND el.race_id  = hc.race_id
    LEFT JOIN host_constructor_pace hcp
        ON el.race_year              = hcp.race_year
        AND el.race_id               = hcp.race_id
        AND hc.host_constructor_id   = hcp.host_constructor_id
    LEFT JOIN host_interaction hi
        ON el.race_year              = hi.race_year
        AND el.race_id               = hi.race_id
        AND hc.host_constructor_id   = hi.host_constructor_id
)

SELECT
    ghost_id,
    race_year,
    race_id,
    ego_driver_id,
    host_constructor_id,
    ego_constructor_id,
    lap_number,
    -- Recombined lap time: base + all physics + ego skill + host constructor
    COALESCE(base_track_pace_s, actual_lap_time_s)
        + COALESCE(fuel_component_s, 0.0)
        + COALESCE(driver_skill_residual_s, 0.0)
        + COALESCE(host_constructor_pace_s, 0.0)
        + COALESCE(circuit_interaction_s, 0.0)
        + COALESCE(dirty_air_tax_s, 0.0)
        + COALESCE(compound_component_s, 0.0)
        + COALESCE(rubber_component_s, 0.0)
        + COALESCE(ambient_component_s, 0.0)                AS predicted_lap_time_s,
    actual_lap_time_s,
    -- Delta vs actual
    (
        COALESCE(base_track_pace_s, actual_lap_time_s)
            + COALESCE(fuel_component_s, 0.0)
            + COALESCE(driver_skill_residual_s, 0.0)
            + COALESCE(host_constructor_pace_s, 0.0)
            + COALESCE(circuit_interaction_s, 0.0)
            + COALESCE(dirty_air_tax_s, 0.0)
            + COALESCE(compound_component_s, 0.0)
            + COALESCE(rubber_component_s, 0.0)
            + COALESCE(ambient_component_s, 0.0)
    )-actual_lap_time_s                                   AS delta_vs_actual_lap_s,
    -- Component breakdown for explainability
    base_track_pace_s,
    fuel_component_s,
    driver_skill_residual_s,
    host_constructor_pace_s,
    circuit_interaction_s,
    dirty_air_tax_s,
    compound_component_s,
    rubber_component_s,
    ambient_component_s,
    host_constructor_obs_n                                  AS ego_host_regime_overlap_n,
    recombination_confidence
FROM ghost_recombined
WHERE recombination_confidence > 0.0
ORDER BY race_year, race_id, ego_driver_id, host_constructor_id, lap_number
