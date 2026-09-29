-- WI-17 (functional degradation parametrization): the one lap set every
-- power-law fit, the Step-0 identification check (ml/src/powerlaw_ceiling.py)
-- and the held-out truth in ml/src/powerlaw.py read, so the fits and the
-- grading use the same laps.
--
-- Grain: lap_id. Slick laps only, with mart_degradation_history_envelope's
-- filters (correction_weight = 1, no SC / VSC / red flag, not a major outlier),
-- tyre age 1-50.
--
-- Target: y_s = weight_corrected_lap_time (lap time with the fuel-mass term
-- removed). The WI's pre-flight probe used weight_corrected_lap_time -
-- rubber_component_s. Step 0 settled on the fuel-corrected time alone, for two
-- reasons recorded in the WI's As built:
--   * rubber_component_s is fitted from int_field_pace_curve, which subtracts
--     the compound seed's expected_compound_pace_s from every lap. It is priced
--     from the seed the F2/FD3 guard fences off (T51), one step removed.
--   * The P3 truth (mart_degradation_history_envelope's obs_deg_from_fresh) and
--     the simulator's recomposition (net = ref + fuel + tyre, with no
--     track-evolution term) are both built on weight_corrected_lap_time. A tyre
--     term fitted net of rubber measures a different quantity from the one it
--     is graded against.
--
-- Compound identity (W50): a hardness rank from the compound_hardness_scale
-- seed, never a compound name as a feature.
--   * 2018: the lap's own compound name (SOFT, SUPERSOFT, ...). 2018 laps carry
--     absolute names and compound_code is NULL for all of 2018 by construction
--     (08p). tyre_allocations has no 2018 rows and is never consulted for 2018.
--   * 2019+: compound_code (C1-C5) from int_stint_geometry's tyre_allocations
--     join.
--   * 2025: tyre_allocations stops at 2024 (the unverified 2025 rows were
--     dropped in the W50 rewrite), so compound_code, and with it the rank, is
--     NULL for 2025. Those laps stay in the lap set, and so in the per-stint
--     fits, but no (race, rank) cell can form for them.
--
-- F2/FD3 guard: nothing here reads compound_cliff_params,
-- int_compound_cliff_predicted or any column priced from them
-- (compound_component_s, expected_*, cliff_onset_passed, laps_past_cliff,
-- driver_skill_residual_s, pace_delta_s, ambient_temp_delta). T51
-- (assert_power_law_no_seed_columns.sql) pins the column list.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT
        lap_id,
        stint_id,
        race_id,
        race_year,
        driver_id,
        constructor_id,
        lap_number,
        lap_in_stint,
        age_in_stint,
        compound AS compound_label,
        weight_corrected_lap_time,
        fuel_mass_kg,
        track_temp_c,
        -- int_constructor_structural_pace's per-(race, constructor)
        -- coefficient, carried on every lap. It is the quantity the simulator's
        -- constructor offset is built from.
        constructor_component_s
    FROM {{ ref('int_lap_residual_decomposed') }}
    WHERE
        weight_corrected_lap_time IS NOT NULL
        AND compound IS NOT NULL
        AND compound NOT IN ('INTERMEDIATE', 'WET')
        AND age_in_stint BETWEEN 1 AND 50
        AND COALESCE(correction_weight, 0) = 1
        AND NOT is_safety_car_lap
        AND NOT is_vsc_lap
        AND NOT is_red_flag_lap
        AND NOT is_major_outlier_lap
),

geom AS (
    SELECT
        lap_id,
        compound_code
    FROM {{ ref('int_stint_geometry') }}
),

track AS (
    SELECT
        rt.race_id,
        dc.circuit_key,
        dc.circuit_id,
        dc.track_energy_index,
        dc.abrasiveness_index
    FROM {{ ref('race_to_track') }} AS rt
    INNER JOIN {{ ref('dim_circuits') }} AS dc
        ON rt.track_id = dc.circuit_key
),

keyed AS (
    SELECT
        l.*,
        g.compound_code,
        CASE
            WHEN l.race_year = 2018 THEN '2018'
            WHEN l.race_year BETWEEN 2019 AND 2021 THEN '2019-21'
            ELSE '2022+'
        END AS hardness_era,
        -- 2018 identity is the lap's own name; 2019+ is the C-code. Never the
        -- other way round.
        CASE
            WHEN l.race_year = 2018 THEN l.compound_label
            ELSE g.compound_code
        END AS hardness_identity
    FROM laps AS l
    LEFT JOIN geom AS g
        ON l.lap_id = g.lap_id
)

SELECT
    k.lap_id,
    k.stint_id,
    k.race_id,
    k.race_year,
    k.driver_id,
    k.constructor_id,
    k.lap_number,
    k.lap_in_stint,
    k.age_in_stint,
    k.compound_label,
    k.compound_code,
    k.hardness_era,
    k.hardness_identity,
    hs.hardness_rank AS compound_hardness_rank,
    t.circuit_key,
    t.circuit_id,
    t.track_energy_index,
    t.abrasiveness_index AS circuit_abrasiveness_index,
    k.weight_corrected_lap_time AS y_s,
    k.fuel_mass_kg,
    k.track_temp_c,
    k.constructor_component_s AS constructor_pace_s
FROM keyed AS k
LEFT JOIN {{ ref('compound_hardness_scale') }} AS hs
    ON
        k.hardness_identity = hs.compound_code
        AND k.hardness_era = hs.era
LEFT JOIN track AS t
    ON k.race_id = t.race_id
