-- Driver x race summary ("why was he slow at Monza"). Grain: (driver_id, race_id).
-- rating_s = driver_skill_loro_s (median lap-by-lap gap to teammate, negative =
-- faster). rank/percentile are within the race. ci_low/high = rating +/- 1.96 *
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
        grid_position - finish_position AS positions_gained,
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

ranked AS (
    SELECT
        *,
        RANK() OVER (PARTITION BY race_id ORDER BY rating_s) AS rank,
        COUNT(*) OVER (PARTITION BY race_id) AS n_drivers
    FROM ratings
),

teammates AS (
    SELECT
        a.race_id, a.driver_id, b.driver_id AS teammate_id,
        b.rating_s AS teammate_rating_s
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
    k.rank,
    k.n_drivers,
    1.0 - (k.rank - 1.0) / NULLIF(k.n_drivers - 1, 0) AS percentile,
    k.rating_s - 1.96 * c.lap_se_s AS ci_low,
    k.rating_s + 1.96 * c.lap_se_s AS ci_high,
    c.n_clean_laps,
    t.teammate_id,
    k.rating_s - t.teammate_rating_s AS teammate_gap_s,
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
FROM ranked AS k
LEFT JOIN clean AS c ON k.race_id = c.race_id AND k.driver_id = c.driver_id
LEFT JOIN completed AS cp ON k.race_id = cp.race_id AND k.driver_id = cp.driver_id
LEFT JOIN results AS r ON k.race_id = r.race_id AND k.driver_id = r.driver_id
LEFT JOIN teammates AS t ON k.race_id = t.race_id AND k.driver_id = t.driver_id
LEFT JOIN constructor_rank AS cr
    ON k.race_id = cr.race_id AND k.constructor_id = cr.constructor_id
LEFT JOIN {{ ref('dim_circuits') }} AS dc ON k.circuit_key = dc.circuit_key
ORDER BY k.race_year, k.race_id, k.rank
