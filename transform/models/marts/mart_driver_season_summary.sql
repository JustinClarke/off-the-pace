-- Driver x season summary for LLM explanations ("22nd of 22").
-- Grain: (driver_id, race_year). Sorted by year, rank.
-- rating_s = era_adjusted_rating (shrunk teammate-relative gap, seconds;
-- negative = faster). rank 1 = most negative. Component means are over
-- ml_eligible laps only (seconds, positive = slower).
-- Primary constructor = the one the driver ran the most clean laps for;
-- teammate = the other driver with the most clean laps for that constructor.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT
        race_year, driver_id, constructor_id, fuel_component_s,
        compound_component_s, constructor_component_s, dirty_air_tax_s
    FROM {{ ref('fct_lap_residuals') }}
    WHERE ml_eligible = TRUE
),

driver_constructor AS (
    SELECT race_year, driver_id, constructor_id, COUNT(*) AS n_laps
    FROM laps
    GROUP BY race_year, driver_id, constructor_id
),

primary_team AS (
    SELECT race_year, driver_id, constructor_id, n_laps
    FROM driver_constructor
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY race_year, driver_id ORDER BY n_laps DESC, constructor_id
    ) = 1
),

components AS (
    SELECT
        race_year,
        driver_id,
        AVG(fuel_component_s) AS mean_fuel_component_s,
        AVG(compound_component_s) AS mean_compound_component_s,
        AVG(constructor_component_s) AS mean_constructor_component_s,
        AVG(dirty_air_tax_s) AS mean_dirty_air_tax_s
    FROM laps
    GROUP BY race_year, driver_id
),

ratings AS (
    SELECT
        r.driver_id,
        r.season AS race_year,
        r.era_adjusted_rating AS rating_s,
        r.era_adjusted_rating_ci_low_s AS ci_low,
        r.era_adjusted_rating_ci_high_s AS ci_high,
        r.n_races
    FROM {{ ref('int_era_normalized_driver_rating') }} AS r
    INNER JOIN primary_team AS p
        ON r.driver_id = p.driver_id AND r.season = p.race_year
),

ranked AS (
    SELECT
        *,
        RANK() OVER (PARTITION BY race_year ORDER BY rating_s) AS rank,
        COUNT(*) OVER (PARTITION BY race_year) AS n_drivers
    FROM ratings
),

teammates AS (
    SELECT
        a.race_year,
        a.driver_id,
        b.driver_id AS teammate_id
    FROM primary_team AS a
    INNER JOIN driver_constructor AS b
        ON a.race_year = b.race_year
        AND a.constructor_id = b.constructor_id
        AND a.driver_id <> b.driver_id
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY a.race_year, a.driver_id ORDER BY b.n_laps DESC, b.driver_id
    ) = 1
),

constructor_rank AS (
    SELECT
        race_year,
        constructor_id,
        RANK() OVER (
            PARTITION BY race_year ORDER BY AVG(constructor_component_s)
        ) AS constructor_rank
    FROM laps
    GROUP BY race_year, constructor_id
)

SELECT
    k.driver_id,
    k.race_year,
    k.rating_s,
    k.rank,
    k.n_drivers,
    1.0 - (k.rank - 1.0) / NULLIF(k.n_drivers - 1, 0) AS percentile,
    k.ci_low,
    k.ci_high,
    k.n_races,
    t.teammate_id,
    k.rating_s - tr.rating_s AS teammate_gap_s,
    p.constructor_id,
    cr.constructor_rank,
    c.mean_fuel_component_s,
    c.mean_compound_component_s,
    c.mean_constructor_component_s,
    c.mean_dirty_air_tax_s
FROM ranked AS k
INNER JOIN primary_team AS p
    ON k.driver_id = p.driver_id AND k.race_year = p.race_year
LEFT JOIN components AS c
    ON k.driver_id = c.driver_id AND k.race_year = c.race_year
LEFT JOIN teammates AS t
    ON k.driver_id = t.driver_id AND k.race_year = t.race_year
LEFT JOIN ratings AS tr
    ON t.teammate_id = tr.driver_id AND t.race_year = tr.race_year
LEFT JOIN constructor_rank AS cr
    ON p.constructor_id = cr.constructor_id AND p.race_year = cr.race_year
ORDER BY k.race_year, k.rank
