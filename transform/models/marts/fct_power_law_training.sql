-- WI-17: training frame for ml/src/powerlaw.py, one row per race x compound
-- hardness rank cell that int_cell_power_law_fit marks fit_eligible.
--
-- Targets come from int_cell_power_law_fit (alpha_s, beta and the curve
-- increments over the age-2 fresh-tyre pace). Features are an ALLOWLIST of what
-- the Degradation Simulator can supply at inference time (W26: a feature the
-- browser cannot fill arrives as NaN, which the model never saw):
--
--   * compound_hardness_rank: compound_hardness_scale seed (2018 from the
--     lap's own name, 2019+ from compound_code); never a compound name.
--   * era_code: 0 = 2018, 1 = 2019-21, 2 = 2022+ (the seed's era column).
--   * track_energy_index, circuit_abrasiveness_index: dim_circuits (the
--     simulator's circuit picker reads the same).
--   * track_temp_c: circuit-season median track temperature, from the lap
--     set's weather (stg_weather via int_lap_residual_decomposed).
--   * stint_start_fuel_kg: mean over the cell's stints of the fuel load on
--     the stint's first lap (int_lap_fuel_state).
--   * dirty_air_share: mean dirty_air_share_lap over the cell's laps
--     (fct_cliff_prediction_features, this one column only).
--   * constructor_pace_s: lap-weighted mean of
--     int_constructor_structural_pace's coefficient over the cell's laps, a
--     team-level proxy. Car setup is not observed anywhere in this warehouse.
--     ⚠️ W51 NOTE: This feature is ONE-STEP-REMOVED from the compound seed
--     because int_constructor_structural_pace reads field_pace_smoothed_s,
--     which subtracts expected_compound_pace_s (priced from int_compound_cliff_predicted,
--     which reads the compound seed). This is acceptable only under FD3 ruling that
--     allows point-in-time refit of the compound seed on the race it scores.
--
-- Deliberately absent (the F2/FD3 guard, T51 pins it): every compound_* seed
-- column, every expected_* column, cliff_onset_passed / laps_past_cliff,
-- compound_component_s and anything net of it. That includes the warehouse's
-- ambient_temp_delta, which the WI's allowlist named:
-- int_compound_cliff_predicted computes it as track temp minus
-- compound_optimal_temp_low, a compound seed column. track_temp_c carries the
-- temperature signal instead, and the simulator's ambient slider maps onto it
-- as a delta over the circuit's median.
{{ config(materialized='table', tags=['marts']) }}

WITH cells AS (
    SELECT * FROM {{ ref('int_cell_power_law_fit') }}
    WHERE fit_eligible
),

laps AS (
    SELECT
        lap_id,
        stint_id,
        race_id,
        race_year,
        circuit_id,
        compound_hardness_rank,
        age_in_stint,
        track_energy_index,
        circuit_abrasiveness_index,
        track_temp_c,
        constructor_pace_s
    FROM {{ ref('int_power_law_lap') }}
    WHERE compound_hardness_rank IS NOT NULL
),

-- The stints the cell fit used: >= 5 laps over >= 2 distinct ages
-- (int_cell_power_law_fit).
qualifying_stints AS (
    SELECT stint_id
    FROM laps
    GROUP BY stint_id
    HAVING COUNT(*) >= 5 AND COUNT(DISTINCT age_in_stint) >= 2
),

cell_laps AS (
    SELECT l.*
    FROM laps AS l
    INNER JOIN qualifying_stints AS q
        ON l.stint_id = q.stint_id
),

dirty_air AS (
    SELECT
        lap_id,
        CAST(dirty_air_share_lap AS DOUBLE) AS dirty_air_share_lap
    FROM {{ ref('fct_cliff_prediction_features') }}
),

stint_start_fuel AS (
    -- Fuel only burns within a stint, so the stint's heaviest lap is its first.
    SELECT
        stint_id,
        MAX(fuel_mass_kg) AS stint_start_fuel_kg
    FROM {{ ref('int_lap_fuel_state') }}
    GROUP BY stint_id
),

circuit_season_temp AS (
    SELECT
        circuit_id,
        race_year,
        MEDIAN(track_temp_c) AS track_temp_c
    FROM laps
    GROUP BY circuit_id, race_year
),

cell_features AS (
    SELECT
        cl.race_id,
        cl.compound_hardness_rank,
        MIN(cl.track_energy_index) AS track_energy_index,
        MIN(cl.circuit_abrasiveness_index) AS circuit_abrasiveness_index,
        AVG(da.dirty_air_share_lap) AS dirty_air_share,
        AVG(cl.constructor_pace_s) AS constructor_pace_s
    FROM cell_laps AS cl
    LEFT JOIN dirty_air AS da
        ON cl.lap_id = da.lap_id
    GROUP BY cl.race_id, cl.compound_hardness_rank
),

cell_fuel AS (
    SELECT
        s.race_id,
        s.compound_hardness_rank,
        AVG(f.stint_start_fuel_kg) AS stint_start_fuel_kg
    FROM (
        SELECT DISTINCT
            race_id,
            compound_hardness_rank,
            stint_id
        FROM cell_laps
    ) AS s
    LEFT JOIN stint_start_fuel AS f
        ON s.stint_id = f.stint_id
    GROUP BY s.race_id, s.compound_hardness_rank
)

SELECT
    c.cell_id,
    c.race_id,
    c.race_year,
    c.circuit_id,
    c.hardness_era,
    c.compound_label,
    c.compound_code,
    -- targets
    c.alpha_s,
    c.beta,
    c.curve_incr_5_s,
    c.curve_incr_10_s,
    c.curve_incr_15_s,
    c.curve_incr_20_s,
    -- fit diagnostics and sample weight
    c.n_laps,
    c.n_stints,
    c.r2_within,
    c.beta_at_grid_edge,
    -- features (the allowlist; ml/src/powerlaw.py FEATURES carries the same
    -- order)
    c.compound_hardness_rank,
    CASE c.hardness_era
        WHEN '2018' THEN 0
        WHEN '2019-21' THEN 1
        ELSE 2
    END AS era_code,
    cf.track_energy_index,
    cf.circuit_abrasiveness_index,
    cst.track_temp_c,
    fu.stint_start_fuel_kg,
    cf.dirty_air_share,
    cf.constructor_pace_s
FROM cells AS c
LEFT JOIN cell_features AS cf
    ON
        c.race_id = cf.race_id
        AND c.compound_hardness_rank = cf.compound_hardness_rank
LEFT JOIN cell_fuel AS fu
    ON
        c.race_id = fu.race_id
        AND c.compound_hardness_rank = fu.compound_hardness_rank
LEFT JOIN circuit_season_temp AS cst
    ON
        c.circuit_id = cst.circuit_id
        AND c.race_year = cst.race_year
