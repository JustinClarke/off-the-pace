-- Driver x race summary ("why was he slow at Monza"). Grain: (driver_id, race_id).
-- rating_s = driver_skill_loro_s (median lap-by-lap gap to teammate, negative =
-- faster). rating_s IS the teammate gap, so teammate_gap_s = rating_s (CO-01/T3:
-- it used to be rating_s minus the teammate's rating_s, i.e. twice the gap).
-- No within-race rank or percentile (CO-01/T4): ordering every driver's gap
-- to his own teammate across the field read as a speed ranking ("22nd of
-- 22") and is not one, so the owner dropped it (2026-10-15). The season mart
-- keeps its teammate_gap_rank. positions_gained is NULL for a pit-lane start
-- (grid_position = 0), which is not a grid slot (CO-01/T5). ci_low/high = rating +/- 1.96 *
-- standard error of clean-lap driver_skill_residual_s (a lap-noise band, not the
-- season Bayesian CI). n_races is 1 by construction and omitted; n_clean_laps
-- is given instead. Components are means over ml_eligible laps.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT * FROM {{ ref('fct_lap_residuals') }}
),

clean AS (
    SELECT
        race_id, driver_id,
        COUNT(*) AS n_clean_laps,
        AVG(lap_time_s) AS avg_lap_time_s,
        AVG(fuel_component_s) AS mean_fuel_component_s,
        AVG(compound_component_s) AS mean_compound_component_s,
        AVG(constructor_component_s) AS mean_constructor_component_s,
        AVG(dirty_air_tax_s) AS mean_dirty_air_tax_s,
        STDDEV(driver_skill_residual_s) / SQRT(NULLIF(COUNT(driver_skill_residual_s), 0)) AS lap_se_s
    FROM laps
    WHERE ml_eligible = TRUE
    GROUP BY race_id, driver_id
),

completed AS (
    SELECT race_id, driver_id, COUNT(*) AS laps_completed
    FROM laps
    GROUP BY race_id, driver_id
),

results AS (
    SELECT
        race_id, driver_id,
        CASE
            WHEN grid_position >= 1 THEN grid_position - finish_position
        END AS positions_gained,
        is_dnf AS has_dnf
    FROM {{ ref('stg_results') }}
),

ratings AS (
    SELECT
        driver_id, race_id, race_year, constructor_id, circuit_key,
        driver_skill_loro_s AS rating_s
    FROM {{ ref('int_driver_race_skill_loro') }}
    WHERE driver_skill_loro_s IS NOT NULL
),

counted AS (
    SELECT
        *,
        COUNT(*) OVER (PARTITION BY race_id) AS n_drivers
    FROM ratings
),

teammates AS (
    SELECT
        a.race_id, a.driver_id, b.driver_id AS teammate_id
    FROM ratings AS a
    INNER JOIN ratings AS b
        ON a.race_id = b.race_id
        AND a.constructor_id = b.constructor_id
        AND a.driver_id <> b.driver_id
    LEFT JOIN clean AS bc ON b.race_id = bc.race_id AND b.driver_id = bc.driver_id
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY a.race_id, a.driver_id
        ORDER BY bc.n_clean_laps DESC NULLS LAST, b.driver_id
    ) = 1
),

constructor_rank AS (
    SELECT
        l.race_id,
        l.constructor_id,
        RANK() OVER (
            PARTITION BY l.race_id ORDER BY AVG(l.constructor_component_s)
        ) AS constructor_rank
    FROM laps AS l
    WHERE l.ml_eligible = TRUE
    GROUP BY l.race_id, l.constructor_id
)

SELECT
    k.driver_id,
    k.race_id,
    k.race_year,
    dc.circuit_id,
    k.rating_s,
    k.n_drivers,
    k.rating_s - 1.96 * c.lap_se_s AS ci_low,
    k.rating_s + 1.96 * c.lap_se_s AS ci_high,
    c.n_clean_laps,
    t.teammate_id,
    CASE WHEN t.teammate_id IS NOT NULL THEN k.rating_s END AS teammate_gap_s,
    k.constructor_id,
    cr.constructor_rank,
    c.mean_fuel_component_s,
    c.mean_compound_component_s,
    c.mean_constructor_component_s,
    c.mean_dirty_air_tax_s,
    c.avg_lap_time_s,
    cp.laps_completed,
    r.positions_gained,
    COALESCE(r.has_dnf, FALSE) AS has_dnf
FROM counted AS k
LEFT JOIN clean AS c ON k.race_id = c.race_id AND k.driver_id = c.driver_id
LEFT JOIN completed AS cp ON k.race_id = cp.race_id AND k.driver_id = cp.driver_id
LEFT JOIN results AS r ON k.race_id = r.race_id AND k.driver_id = r.driver_id
LEFT JOIN teammates AS t ON k.race_id = t.race_id AND k.driver_id = t.driver_id
LEFT JOIN constructor_rank AS cr
    ON k.race_id = cr.race_id AND k.constructor_id = cr.constructor_id
LEFT JOIN {{ ref('dim_circuits') }} AS dc ON k.circuit_key = dc.circuit_key
ORDER BY k.race_year, k.race_id, k.rating_s, k.driver_id
