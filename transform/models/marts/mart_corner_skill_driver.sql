-- Driver corner skill: time-gained vs LORO car baseline.
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
--
-- 4. Cell winsorization. Each (driver, race, corner) cell is clipped to
--    +/-1.0s before the season AVG, so one thin/outlier cell (e.g. a corner
--    with a handful of laps and a bad LORO baseline) can't dominate a whole
--    season. Guarantees |braking_skill_s| <= 1.0 by convexity.
-- 5. Per-phase cell floor. braking_cells_n / mid_cells_n / exit_cells_n count
--    the winsorized cells behind each phase mean. A phase's z-score (and
--    therefore corner_skill_index, their sum) is only populated once its own
--    cell count clears PHASE_MIN_CELLS=30 -- the mean/SE stay published below
--    that floor (still informative), only the standardized/composite score
--    is withheld. Phases differ in coverage because not every corner has a
--    discrete braking zone or a clean exit-measurement point, even though
--    every corner has a mid-apex.

{% set phase_min_cells = 30 %}

{{ config(materialized='table', tags=['mart']) }}

WITH lap_meta AS (
    SELECT
        lap_id,
        is_accurate,
        is_deleted,
        is_safety_car_lap,
        is_vsc_lap,
        is_red_flag_lap,
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
    INNER JOIN lap_meta AS lm ON csr.lap_id = lm.lap_id
    LEFT JOIN corrections AS cor ON csr.lap_id = cor.lap_id
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
        AND NOT lm.is_red_flag_lap
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
    INNER JOIN car_agg AS ca
        ON
            dca.race_id = ca.race_id
            AND dca.constructor_id = ca.constructor_id
            AND dca.corner_name = ca.corner_name
),

-- LORO-adjusted skill per driver-race-corner, winsorized to +/-1.0s (see
-- header point 4): a single cell's deviation from the car baseline cannot
-- contribute more than +/-1.0s to the season mean.
-- Negative = driver faster than the equal-car (LORO) benchmark.
--
-- The IS NOT NULL guards are load-bearing, not defensive: DuckDB's GREATEST and
-- LEAST ignore NULL arguments rather than propagating them, so a bare
-- LEAST(1.0, NULL) returns 1.0 and a phase with no measurement would enter the
-- season mean as the maximum possible penalty. A corner with no discrete
-- braking zone, or none where full throttle returns before the next apex, has
-- no value for that phase and must stay NULL so the phase's cell count and
-- mean both exclude it.
deconf_corner AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        constructor_id,
        corner_name,
        CASE
            WHEN
                driver_mean_braking_s IS NOT NULL AND loro_braking_s IS NOT NULL
                THEN GREATEST(
                    -1.0, LEAST(1.0, driver_mean_braking_s - loro_braking_s)
                )
        END AS deconf_braking_s,
        CASE
            WHEN driver_mean_mid_s IS NOT NULL AND loro_mid_s IS NOT NULL
                THEN GREATEST(
                    -1.0, LEAST(1.0, driver_mean_mid_s - loro_mid_s)
                )
        END AS deconf_mid_s,
        CASE
            WHEN driver_mean_exit_s IS NOT NULL AND loro_exit_s IS NOT NULL
                THEN GREATEST(
                    -1.0, LEAST(1.0, driver_mean_exit_s - loro_exit_s)
                )
        END AS deconf_exit_s
    FROM loro_corner
    WHERE
        loro_braking_s IS NOT NULL
        OR loro_mid_s IS NOT NULL
        OR loro_exit_s IS NOT NULL
),

-- Season-driver aggregates: mean LORO-adjusted skill (of winsorized cells)
-- across all corners and races, plus per-phase cell counts and standard
-- errors. Require ≥ 100 mapped corners for reliability (same guard as the
-- original model). mapped_corners tracks mid_cells_n: every corner has a
-- mid-apex, so it's the most complete of the three phases.
driver_season AS (
    SELECT
        race_year,
        driver_id,
        ANY_VALUE(constructor_id) AS constructor_id,
        AVG(deconf_braking_s) AS braking_skill_s,
        AVG(deconf_mid_s) AS mid_corner_skill_s,
        AVG(deconf_exit_s) AS exit_skill_s,
        STDDEV(deconf_braking_s)
        / SQRT(NULLIF(COUNT(deconf_braking_s), 0)) AS braking_skill_se_s,
        STDDEV(deconf_mid_s)
        / SQRT(NULLIF(COUNT(deconf_mid_s), 0)) AS mid_corner_skill_se_s,
        STDDEV(deconf_exit_s)
        / SQRT(NULLIF(COUNT(deconf_exit_s), 0)) AS exit_skill_se_s,
        COUNT(deconf_braking_s) AS braking_cells_n,
        COUNT(deconf_mid_s) AS mid_cells_n,
        COUNT(deconf_exit_s) AS exit_cells_n,
        COUNT(*) AS mapped_corners
    FROM deconf_corner
    GROUP BY race_year, driver_id
    HAVING COUNT(*) >= 100
),

-- Per-phase z-scores within each season so all three phases contribute equally
-- to
-- corner_skill_index and the exit phase does not dominate (unchanged from old
-- model). Each z is withheld below PHASE_MIN_CELLS=30 cells (header point 5);
-- corner_skill_index is their sum, so it goes NULL automatically once any
-- one phase is withheld.
standardized AS (
    SELECT
        race_year,
        driver_id,
        constructor_id,
        braking_skill_s,
        mid_corner_skill_s,
        exit_skill_s,
        braking_skill_se_s,
        mid_corner_skill_se_s,
        exit_skill_se_s,
        braking_cells_n,
        mid_cells_n,
        exit_cells_n,
        mapped_corners,
        CASE
            WHEN braking_cells_n >= {{ phase_min_cells }}
                THEN braking_skill_s
                / NULLIF(STDDEV(braking_skill_s) OVER (PARTITION BY race_year), 0)
        END AS braking_skill_z,
        CASE
            WHEN mid_cells_n >= {{ phase_min_cells }}
                THEN mid_corner_skill_s
                / NULLIF(STDDEV(mid_corner_skill_s) OVER (PARTITION BY race_year), 0)
        END AS mid_corner_skill_z,
        CASE
            WHEN exit_cells_n >= {{ phase_min_cells }}
                THEN exit_skill_s
                / NULLIF(STDDEV(exit_skill_s) OVER (PARTITION BY race_year), 0)
        END AS exit_skill_z
    FROM driver_season
)

SELECT
    race_year,
    driver_id,
    constructor_id,
    ROUND(braking_skill_s, 4) AS braking_skill_s,
    ROUND(mid_corner_skill_s, 4) AS mid_corner_skill_s,
    ROUND(exit_skill_s, 4) AS exit_skill_s,
    ROUND(braking_skill_se_s, 4) AS braking_skill_se_s,
    ROUND(mid_corner_skill_se_s, 4) AS mid_corner_skill_se_s,
    ROUND(exit_skill_se_s, 4) AS exit_skill_se_s,
    ROUND(braking_skill_z, 2) AS braking_skill_z,
    ROUND(mid_corner_skill_z, 2) AS mid_corner_skill_z,
    ROUND(exit_skill_z, 2) AS exit_skill_z,
    ROUND(braking_skill_z + mid_corner_skill_z + exit_skill_z, 2)
        AS corner_skill_index,
    braking_cells_n,
    mid_cells_n,
    exit_cells_n,
    mapped_corners
FROM standardized
ORDER BY race_year ASC, corner_skill_index ASC
