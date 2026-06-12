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
--                      + deg_interaction           (transform v0.2 Fix 1, see below)
--                      + cliff_interaction         (transform v0.2 Fix 2, see below)
--
-- deg_interaction_s = (deg_slope(host) - deg_slope(ego)) * age_in_stint, with
-- slopes from int_constructor_deg_sensitivity at the ego lap's (compound, season).
-- This is the only host-dependent term that varies WITHIN a race, so it is what
-- allows different hosts to produce different driver orders (the v0.1 host
-- re-ranking no-op bug). Missing cells (wet compounds, low-sample) resolve to a
-- slope of 0 = field-average degradation.
--
-- cliff_interaction_s (Fix 2) = severity * [ hinge(host) - hinge(ego) ], where
--   hinge(c) = GREATEST(0, age - field_onset - cliff_onset_shift(c))
-- and field_onset/severity are the ego lap's field cliff parameters from
-- int_compound_cliff_predicted (which applies severity LINEARLY to laps_past_cliff).
-- cliff_onset_shift moves each constructor's effective onset earlier (negative) or
-- later (positive). This term only fires once tyres approach/pass the cliff, so it
-- reorders drivers on long stints near the end of their tyre life where the linear
-- deg term is too gentle. Its contribution is bounded by severity * shift.
--
-- Degenerate identity: when ego == host, predicted_lap_time == actual_lap_time.
-- The self-consistency test asserts this holds within 0.0001 s. Both interaction
-- terms preserve it exactly: every lookup hits the same cell, so each difference
-- (deg slope and cliff shift alike) is 0.
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
        lr.compound,
        lr.age_in_stint,
        lr.base_track_pace_s,
        lr.fuel_component_s,
        lr.compound_component_s,
        lr.rubber_component_s,
        lr.ambient_component_s,
        lr.dirty_air_tax_s,
        lr.driver_skill_residual_s,
        lr.lap_time_s                                   AS actual_lap_time_s,
        lr.correction_weight,
        lr.rainfall_flag,
        -- Field hockey-stick parameters for this lap (Fix 2 cliff interaction)
        cp.compound_cliff_onset_laps,
        cp.compound_cliff_severity
    FROM {{ ref('int_lap_residual_decomposed') }} lr
    LEFT JOIN {{ ref('int_compound_cliff_predicted') }} cp
        ON lr.lap_id = cp.lap_id
    WHERE lr.lap_time_s IS NOT NULL
      -- Accept clean (1.0) and soft-down-weighted (0.6 yellow / soft outlier) laps so
      -- partial-race drivers retain a usable sample; the weight feeds lap confidence below.
      AND lr.correction_weight >= 0.6
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

-- Constructor degradation sensitivity per (season, constructor, compound).
-- Joined twice below: once at the ego cell, once at the host cell.
deg_sensitivity AS (
    SELECT
        race_year,
        constructor_id,
        compound,
        deg_slope_s_per_lap,
        -- Fix 3: posterior sd of the (shrunk) slope and SE of the cliff-onset shift.
        -- These are the per-coefficient uncertainties propagated into predicted-pace
        -- variance downstream in fct_ghost_race_finish.
        deg_slope_posterior_sd_s_per_lap,
        cliff_onset_shift_laps,
        cliff_onset_shift_se_laps
    FROM {{ ref('int_constructor_deg_sensitivity') }}
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
        el.correction_weight,
        COALESCE(hcp.constructor_structural_pace_s, 0.0)     AS host_constructor_pace_s,
        COALESCE(hcp.constructor_structural_pace_se_s, 0.0)  AS host_constructor_pace_se_s,
        COALESCE(hi.circuit_constructor_interaction_s, 0.0)  AS circuit_interaction_s,
        -- Deg interaction (Fix 1): host-vs-ego degradation slope delta × tyre age.
        -- COALESCE both lookups to 0 (field-average) so the ego == host case is an
        -- exact zero and missing cells degrade to "no reordering signal".
        COALESCE(deg_host.deg_slope_s_per_lap, 0.0)          AS host_deg_slope_s_per_lap,
        COALESCE(deg_ego.deg_slope_s_per_lap, 0.0)           AS ego_deg_slope_s_per_lap,
        (
            COALESCE(deg_host.deg_slope_s_per_lap, 0.0)
            - COALESCE(deg_ego.deg_slope_s_per_lap, 0.0)
        ) * COALESCE(el.age_in_stint, 0)                     AS deg_interaction_s,
        COALESCE(deg_host.cliff_onset_shift_laps, 0.0)       AS host_cliff_shift_laps,
        COALESCE(deg_ego.cliff_onset_shift_laps, 0.0)        AS ego_cliff_shift_laps,
        -- Cliff interaction (Fix 2): host-vs-ego difference in the field's LINEAR
        -- post-onset penalty, each constructor's onset moved by its own shift.
        -- severity * [ hinge(host) - hinge(ego) ], hinge(c) = GREATEST(0, age - onset - shift(c)).
        -- ego == host => 0 exactly. Guardrail clip to +/-2.0 s: in the asymmetric zone
        -- (one car past its shifted onset, the other not) the term grows with age, and a
        -- few high-severity circuits (severity up to ~3.3 s/lap) could otherwise let a
        -- cliff-timing refinement dwarf the field pace. +/-2 s keeps it a refinement.
        LEAST(GREATEST(
            COALESCE(el.compound_cliff_severity, 0.0) * (
                GREATEST(
                    CAST(COALESCE(el.age_in_stint, 0) AS DOUBLE)
                    - COALESCE(el.compound_cliff_onset_laps, 999.0)
                    - COALESCE(deg_host.cliff_onset_shift_laps, 0.0), 0.0)
                - GREATEST(
                    CAST(COALESCE(el.age_in_stint, 0) AS DOUBLE)
                    - COALESCE(el.compound_cliff_onset_laps, 999.0)
                    - COALESCE(deg_ego.cliff_onset_shift_laps, 0.0), 0.0)
            ), -2.0), 2.0)                                   AS cliff_interaction_s,
        -- Fix 3 SE-propagation ingredients (per lap; aggregated in fct_ghost_race_finish).
        -- Posterior sds of the deg slopes and SEs of the cliff shifts, plus the per-lap
        -- exposures (tyre age, field severity, and whether each car's hinge is active)
        -- that scale those coefficient uncertainties into the predicted-pace variance.
        COALESCE(deg_host.deg_slope_posterior_sd_s_per_lap, 0.0)  AS host_deg_slope_sd_s_per_lap,
        COALESCE(deg_ego.deg_slope_posterior_sd_s_per_lap, 0.0)   AS ego_deg_slope_sd_s_per_lap,
        COALESCE(deg_host.cliff_onset_shift_se_laps, 0.0)         AS host_cliff_shift_se_laps,
        COALESCE(deg_ego.cliff_onset_shift_se_laps, 0.0)          AS ego_cliff_shift_se_laps,
        CAST(COALESCE(el.age_in_stint, 0) AS DOUBLE)             AS age_in_stint,
        COALESCE(el.compound_cliff_severity, 0.0)                AS compound_cliff_severity,
        -- 1.0 when this car is past its (shifted) cliff onset on this lap, else 0.0.
        -- Averaged downstream = fraction of laps the cliff term is active for the car,
        -- the exposure that scales the cliff-shift SE.
        CASE WHEN CAST(COALESCE(el.age_in_stint, 0) AS DOUBLE)
                  - COALESCE(el.compound_cliff_onset_laps, 999.0)
                  - COALESCE(deg_host.cliff_onset_shift_laps, 0.0) > 0.0
             THEN 1.0 ELSE 0.0 END                               AS host_cliff_active,
        CASE WHEN CAST(COALESCE(el.age_in_stint, 0) AS DOUBLE)
                  - COALESCE(el.compound_cliff_onset_laps, 999.0)
                  - COALESCE(deg_ego.cliff_onset_shift_laps, 0.0) > 0.0
             THEN 1.0 ELSE 0.0 END                               AS ego_cliff_active,
        COALESCE(hcp.panel_observations_n, 0)                AS host_constructor_obs_n,
        COALESCE(hi.interaction_obs_n, 0)                    AS interaction_obs_n,
        -- Recombination confidence (continuous, replaces coarse step buckets):
        --   host_obs_factor : shrinkage on how well the host car's pace is estimated
        --                     panel_obs / (panel_obs + 50) → smoothly 0→1
        --   lap_quality     : the lap's own correction_weight (1.0 clean, 0.6 soft)
        -- Scenario-level coverage weighting is applied downstream in fct_ghost_race_finish.
        (
            CAST(COALESCE(hcp.panel_observations_n, 0) AS DOUBLE)
                / NULLIF(COALESCE(hcp.panel_observations_n, 0) + 50, 0)
        ) * el.correction_weight                             AS recombination_confidence
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
    LEFT JOIN deg_sensitivity deg_host
        ON el.race_year              = deg_host.race_year
        AND hc.host_constructor_id   = deg_host.constructor_id
        AND el.compound              = deg_host.compound
    LEFT JOIN deg_sensitivity deg_ego
        ON el.race_year              = deg_ego.race_year
        AND el.ego_constructor_id    = deg_ego.constructor_id
        AND el.compound              = deg_ego.compound
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
        + COALESCE(ambient_component_s, 0.0)
        + COALESCE(deg_interaction_s, 0.0)
        + COALESCE(cliff_interaction_s, 0.0)               AS predicted_lap_time_s,
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
            + COALESCE(deg_interaction_s, 0.0)
            + COALESCE(cliff_interaction_s, 0.0)
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
    deg_interaction_s,
    cliff_interaction_s,
    host_deg_slope_s_per_lap,
    ego_deg_slope_s_per_lap,
    host_cliff_shift_laps,
    ego_cliff_shift_laps,
    -- Fix 3 SE-propagation ingredients (consumed by fct_ghost_race_finish).
    host_constructor_pace_se_s,
    host_deg_slope_sd_s_per_lap,
    ego_deg_slope_sd_s_per_lap,
    host_cliff_shift_se_laps,
    ego_cliff_shift_se_laps,
    age_in_stint,
    compound_cliff_severity,
    host_cliff_active,
    ego_cliff_active,
    host_constructor_obs_n                                  AS ego_host_regime_overlap_n,
    recombination_confidence
FROM ghost_recombined
WHERE recombination_confidence > 0.0
ORDER BY race_year, race_id, ego_driver_id, host_constructor_id, lap_number
