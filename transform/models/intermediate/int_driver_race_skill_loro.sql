-- De-confounded absolute driver skill: leave-one-driver-out (LORO)
-- car baseline.
--
-- Replaces the cruise-and-self-baseline-biased `driver_residual_mean_s` as the
-- input to the
-- equal-car rating chain. Two fixes vs the old metric:
--   1. LORO car baseline. A driver is graded against the *other* same-car
--   drivers that race
--      (2-driver teams → the teammate), so he is never in his own baseline. The
--      old
--      int_constructor_structural_pace baseline was the median of a car's *own*
--      laps (both
--      drivers), so only ~half a driver's edge over a teammate survived.
--   2. Ceiling, not cruise. The race-grain skill is the 20th percentile of the
--   de-confounded
--      lap deltas (best laps = the driver's ceiling), which kills the cruise
--      drag that makes a
--      dominant-car leader's clean laps run below the car's potential.
--
-- Two output signals (both use the same clean-panel P20 numerator):
--   driver_skill_loro_s  teammate LORO baseline; used by the RATING chain
--                          (int_driver_season_ratings,
--                          int_driver_circuit_affinity,
--                          int_driver_circuit_affinity [non-era],
--                          int_era_normalized_driver_rating)
--   driver_skill_field_s field-anchored baseline via int_constructor_car_fe
--   (the
--                          de-biased constructor×race FE, car pace net of
--                          driver skill);
--                          used only by int_driver_circuit_era_affinity (Ghost
--                          Standings leaderboard).
--                          Fixes the weak-teammate inflation bug (e.g.
--                          Albon/Sargeant): the old
--                          constructor median absorbed the team's driver skill,
--                          so subtracting it
--                          handed a weak driver's slowness back as "skill". The
--                          car FE has a global
--                          driver anchor, so it removes the car only.
--
-- Output grain: (race_year, race_id, driver_id). One row per driver per race.
-- PK: driver_race_skill_id (surrogate hash).
--
-- Sign convention: negative = faster than field (both signals).

{{ config(
    materialized='table', tags=['driver_rating', 'causal_decomposition']
) }}

WITH fuel AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s
    FROM {{ ref('int_lap_fuel_state') }}
),

field_pace AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        field_pace_smoothed_s
    FROM {{ ref('int_field_pace_curve') }}
),

laps_meta AS (
    SELECT
        lap_id,
        constructor_id
    FROM {{ ref('stg_laps') }}
),

corrections AS (
    SELECT
        lap_id,
        correction_weight
    FROM {{ ref('int_event_corrections') }}
),

evolution AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        rainfall_flag
    FROM {{ ref('int_track_evolution') }}
),

-- Resolve race_id → circuit_key via race_to_track seed (same source as
-- fct_driver_skill_features, so the affinity consumers get identical
-- circuit_key values).
race_to_track AS (
    SELECT
        race_id,
        track_id AS circuit_key
    FROM {{ ref('race_to_track') }}
),

-- De-biased modelled car pace (constructor×race FE, net of driver skill);
-- used to compute driver_skill_field_s. See int_constructor_car_fe.
car_fe AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        car_fe_s
    FROM {{ ref('int_constructor_car_fe') }}
),

-- Per clean lap: pace delta vs the smoothed field median (vs-field anchor
-- preserved).
clean_panel AS (
    SELECT
        f.race_year,
        f.race_id,
        f.driver_id,
        lm.constructor_id,
        f.lap_time_s
        - COALESCE(fp.field_pace_smoothed_s, f.lap_time_s) AS pace_delta_s
    FROM fuel AS f
    INNER JOIN laps_meta AS lm ON f.lap_id = lm.lap_id
    LEFT JOIN field_pace AS fp
        ON
            f.race_year = fp.race_year
            AND f.race_id = fp.race_id
            AND f.lap_number = fp.lap_number
    LEFT JOIN corrections AS cor ON f.lap_id = cor.lap_id
    LEFT JOIN evolution AS e
        ON
            f.race_year = e.race_year
            AND f.race_id = e.race_id
            AND f.lap_number = e.lap_number
    WHERE
        f.lap_time_s IS NOT NULL
        AND COALESCE(cor.correction_weight, 1.0) = 1.0
        AND COALESCE(e.rainfall_flag, FALSE) = FALSE
),

-- Per (race, constructor, driver): median delta (feeds the teammate baseline)
-- and the
-- 20th-percentile delta (the focal driver's ceiling).
driver_race_agg AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        driver_id,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_delta_s)
            AS driver_median_pace_delta_s,
        PERCENTILE_CONT(0.20) WITHIN GROUP (ORDER BY pace_delta_s)
            AS driver_p20_pace_delta_s,
        COUNT(*) AS clean_lap_count
    FROM clean_panel
    GROUP BY race_year, race_id, constructor_id, driver_id
),

-- Per (race, constructor): sum/count of driver medians, to build the LORO
-- baseline.
car_agg AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        SUM(driver_median_pace_delta_s) AS sum_driver_median_s,
        COUNT(*) AS n_car_drivers
    FROM driver_race_agg
    GROUP BY race_year, race_id, constructor_id
),

deconf AS (
    SELECT
        dra.race_year,
        dra.race_id,
        dra.driver_id,
        dra.constructor_id,
        dra.clean_lap_count,
        ca.n_car_drivers,
        -- LORO car baseline = mean of the OTHER same-car drivers' medians
        -- (excludes the
        -- focal driver). NULL when the driver is the only one with clean laps
        -- in his car
        -- that race (no equal-car reference → race drops out, same as a NULL
        -- residual).
        CASE
            WHEN ca.n_car_drivers > 1
                THEN
                    (ca.sum_driver_median_s - dra.driver_median_pace_delta_s)
                    / (ca.n_car_drivers - 1)
        END AS loro_car_baseline_s,
        dra.driver_median_pace_delta_s,
        dra.driver_p20_pace_delta_s
    FROM driver_race_agg AS dra
    INNER JOIN
        car_agg AS ca
        ON
            dra.race_year = ca.race_year
            AND dra.race_id = ca.race_id
            AND dra.constructor_id = ca.constructor_id
)

SELECT
    {{ dbt_utils.generate_surrogate_key([
        'd.race_year', 'd.race_id', 'd.driver_id'
    ]) }}
        AS driver_race_skill_id,
    d.driver_id,
    d.race_year,
    d.race_id,
    d.constructor_id,
    rtt.circuit_key,
    -- Ceiling skill (P20): used by the RATING chain. P20 = best 20%
    -- of clean
    -- laps, which kills cruise drag so dominant-car leaders are no longer
    -- penalised.
    d.driver_p20_pace_delta_s - d.loro_car_baseline_s AS driver_skill_loro_s,
    -- Field-anchored equal-car skill: median pace minus the de-biased modelled
    -- car
    -- term (int_constructor_car_fe.car_fe_s, the constructor×race FE net of
    -- driver
    -- skill). Uses MEDIAN (not P20) on the same pace_delta panel the FE is fit
    -- from,
    -- so the level is consistent. Subtracting the de-biased car term removes
    -- the car
    -- WITHOUT crediting a weak driver's slowness as skill (the bug when the old
    -- constructor median which absorbs the team's driver skill was subtracted).
    -- NULL when the constructor×race FE is unidentified for this race.
    -- Used ONLY by int_driver_circuit_era_affinity (Ghost Car Standings
    -- leaderboard).
    d.driver_median_pace_delta_s - cfe.car_fe_s AS driver_skill_field_s,
    -- Typical race skill (median): used by the GHOST PACE simulation.
    -- The
    -- median preserves the driver's normal within-race pace without
    -- extrapolating to
    -- their ceiling, which keeps ghost-lap predictions calibrated (P20 causes
    -- systematic overconfidence in fct_ghost_race_finish).
    d.driver_median_pace_delta_s
    - d.loro_car_baseline_s AS driver_skill_loro_mean_s,
    d.loro_car_baseline_s,
    d.n_car_drivers,
    d.clean_lap_count
FROM deconf AS d
LEFT JOIN race_to_track AS rtt ON d.race_id = rtt.race_id
LEFT JOIN car_fe AS cfe
    ON
        d.race_year = cfe.race_year
        AND d.race_id = cfe.race_id
        AND d.constructor_id = cfe.constructor_id
ORDER BY d.race_year DESC, d.race_id ASC, d.driver_id ASC
