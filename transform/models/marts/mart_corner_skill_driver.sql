-- Driver corner skill: time-gained vs LORO car baseline (Metric 1 rework).
--
-- Three changes from the old geometry-deviation model:
-- 1. Time-based inputs. Uses int_corner_skill_residuals (braking_loss_s,
--    mid_corner_residual_s, exit_residual_s already "seconds vs field median")
--    instead of raw braking/throttle geometry deviations, which encoded
--    racing-line
--    style differences as unskilled (e.g. Hamilton's earlier braking approach).
-- 2. LORO car baseline. The car's corner effect is the mean residual of the
-- OTHER
--    same-car drivers at the same race and corner (excluding the focal driver).
--    The
--    old model included the focal driver in the car average, so only ~half the
--    edge
--    over a teammate survived.
-- 3. Push-lap filter (clean panel). Applies the correction_weight=1.0 and
--    rainfall_flag=FALSE filters to exclude yellow flags, restarts, and wet
--    laps
--    from the car baseline, matching the clean panel of
--    int_driver_race_skill_loro.
--
-- Output grain: (race_year, driver_id). Sign: negative = faster than the LORO
-- equal-car benchmark (consistent with driver_skill_loro_s upstream).
-- corner_skill_index = sum of three z-scored phase components.

{{ config(materialized='table', tags=['mart']) }}

WITH lap_meta AS (
    SELECT
        lap_id,
        is_accurate,
        is_deleted,
        is_safety_car_lap,
        is_vsc_lap,
        is_pit_lap
    FROM {{ ref('stg_laps') }}
),

corrections AS (
    SELECT lap_id, correction_weight
    FROM {{ ref('int_event_corrections') }}
),

evolution AS (
    SELECT race_year, race_id, lap_number, rainfall_flag
    FROM {{ ref('int_track_evolution') }}
),

-- Corner residuals restricted to push / clean laps (no rain, standard validity
-- flags,
-- no yellow-flag / restart corrections). All residuals already "seconds vs
-- field median".
push_corners AS (
    SELECT
        csr.race_year,
        csr.race_id,
        csr.driver_id,
        csr.constructor_id,
        csr.corner_name,
        csr.lap_number,
        csr.braking_loss_s,
        csr.mid_corner_residual_s,
        csr.exit_residual_s
    FROM {{ ref('int_corner_skill_residuals') }} AS csr
    JOIN lap_meta AS lm USING (lap_id)
    LEFT JOIN corrections AS cor USING (lap_id)
    LEFT JOIN evolution AS e
        ON
            csr.race_year = e.race_year
            AND csr.race_id = e.race_id
            AND csr.lap_number = e.lap_number
    WHERE
        NOT csr.corner_unmapped_flag
        AND lm.is_accurate
        AND NOT lm.is_deleted
        AND NOT lm.is_safety_car_lap
        AND NOT lm.is_vsc_lap
        AND NOT lm.is_pit_lap
        AND COALESCE(cor.correction_weight, 1.0) = 1.0
        AND COALESCE(e.rainfall_flag, FALSE) = FALSE
),

-- Per-(race, constructor, corner): sum and count of residuals across ALL
-- drivers
-- in that car. Used to derive the LORO baseline (sum − focal) / (n − n_focal).
car_agg AS (
    SELECT
        race_id,
        constructor_id,
        corner_name,
        SUM(braking_loss_s) AS sum_braking_s,
        COUNT(CASE WHEN braking_loss_s IS NOT NULL THEN 1 END) AS n_braking,
        SUM(mid_corner_residual_s) AS sum_mid_s,
        COUNT(CASE WHEN mid_corner_residual_s IS NOT NULL THEN 1 END) AS n_mid,
        SUM(exit_residual_s) AS sum_exit_s,
        COUNT(CASE WHEN exit_residual_s IS NOT NULL THEN 1 END) AS n_exit
    FROM push_corners
    GROUP BY race_id, constructor_id, corner_name
),

-- Per-(race, constructor, driver, corner): focal driver's summed residual and
-- count
-- (summed because the driver may have several valid laps at this corner in one
-- race).
driver_corner_agg AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        constructor_id,
        corner_name,
        SUM(braking_loss_s) AS driver_sum_braking_s,
        COUNT(CASE WHEN braking_loss_s IS NOT NULL THEN 1 END) AS n_braking,
        SUM(mid_corner_residual_s) AS driver_sum_mid_s,
        COUNT(CASE WHEN mid_corner_residual_s IS NOT NULL THEN 1 END) AS n_mid,
        SUM(exit_residual_s) AS driver_sum_exit_s,
        COUNT(CASE WHEN exit_residual_s IS NOT NULL THEN 1 END) AS n_exit
    FROM push_corners
    GROUP BY race_year, race_id, driver_id, constructor_id, corner_name
),

-- LORO car baseline per driver-race-corner: mean residual of the OTHER same-car
-- drivers. NULL when the focal driver is the sole source of observations (no
-- equal-car reference → corner drops out of the aggregation, same as NULL
-- residual).
loro_corner AS (
    SELECT
        dca.race_year,
        dca.race_id,
        dca.driver_id,
        dca.constructor_id,
        dca.corner_name,
        CASE
            WHEN ca.n_braking > dca.n_braking
                THEN
                    (ca.sum_braking_s - COALESCE(dca.driver_sum_braking_s, 0))
                    / NULLIF(ca.n_braking - dca.n_braking, 0)
        END AS loro_braking_s,
        CASE
            WHEN ca.n_mid > dca.n_mid
                THEN
                    (ca.sum_mid_s - COALESCE(dca.driver_sum_mid_s, 0))
                    / NULLIF(ca.n_mid - dca.n_mid, 0)
        END AS loro_mid_s,
        CASE
            WHEN ca.n_exit > dca.n_exit
                THEN
                    (ca.sum_exit_s - COALESCE(dca.driver_sum_exit_s, 0))
                    / NULLIF(ca.n_exit - dca.n_exit, 0)
        END AS loro_exit_s,
        dca.driver_sum_braking_s
        / NULLIF(dca.n_braking, 0) AS driver_mean_braking_s,
        dca.driver_sum_mid_s / NULLIF(dca.n_mid, 0) AS driver_mean_mid_s,
        dca.driver_sum_exit_s / NULLIF(dca.n_exit, 0) AS driver_mean_exit_s
    FROM driver_corner_agg AS dca
    JOIN car_agg AS ca
        ON
            dca.race_id = ca.race_id
            AND dca.constructor_id = ca.constructor_id
            AND dca.corner_name = ca.corner_name
),

-- LORO-adjusted skill per driver-race-corner.
-- Negative = driver faster than the equal-car (LORO) benchmark.
deconf_corner AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        constructor_id,
        corner_name,
        driver_mean_braking_s - loro_braking_s AS deconf_braking_s,
        driver_mean_mid_s - loro_mid_s AS deconf_mid_s,
        driver_mean_exit_s - loro_exit_s AS deconf_exit_s
    FROM loro_corner
    WHERE
        loro_braking_s IS NOT NULL
        OR loro_mid_s IS NOT NULL
        OR loro_exit_s IS NOT NULL
),

-- Season-driver aggregates: mean LORO-adjusted skill across all corners and
-- races.
-- Require ≥ 100 mapped corners for reliability (same guard as the original
-- model).
driver_season AS (
    SELECT
        race_year,
        driver_id,
        ANY_VALUE(constructor_id) AS constructor_id,
        AVG(deconf_braking_s) AS braking_skill_s,
        AVG(deconf_mid_s) AS mid_corner_skill_s,
        AVG(deconf_exit_s) AS exit_skill_s,
        COUNT(*) AS mapped_corners
    FROM deconf_corner
    GROUP BY race_year, driver_id
    HAVING COUNT(*) >= 100
),

-- Per-phase z-scores within each season so all three phases contribute equally
-- to
-- corner_skill_index and the exit phase does not dominate (unchanged from old
-- model).
standardized AS (
    SELECT
        race_year,
        driver_id,
        constructor_id,
        braking_skill_s,
        mid_corner_skill_s,
        exit_skill_s,
        mapped_corners,
        braking_skill_s
        / NULLIF(STDDEV(braking_skill_s) OVER (PARTITION BY race_year), 0)
            AS braking_skill_z,
        mid_corner_skill_s
        / NULLIF(STDDEV(mid_corner_skill_s) OVER (PARTITION BY race_year), 0)
            AS mid_corner_skill_z,
        exit_skill_s
        / NULLIF(STDDEV(exit_skill_s) OVER (PARTITION BY race_year), 0)
            AS exit_skill_z
    FROM driver_season
)

SELECT
    race_year,
    driver_id,
    constructor_id,
    ROUND(braking_skill_s, 4) AS braking_skill_s,
    ROUND(mid_corner_skill_s, 4) AS mid_corner_skill_s,
    ROUND(exit_skill_s, 4) AS exit_skill_s,
    ROUND(braking_skill_z, 2) AS braking_skill_z,
    ROUND(mid_corner_skill_z, 2) AS mid_corner_skill_z,
    ROUND(exit_skill_z, 2) AS exit_skill_z,
    ROUND(braking_skill_z + mid_corner_skill_z + exit_skill_z, 2)
        AS corner_skill_index,
    mapped_corners
FROM standardized
ORDER BY race_year ASC, corner_skill_index ASC
