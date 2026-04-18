-- Stable driver reference derived from the laps source.
-- driver_id is the FastF1 three-letter code (e.g. VER, HAM).
-- debut_year and career_races are derived from available data;
-- nationality requires a manual seed or external lookup if needed.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT * FROM {{ ref('stg_laps') }}
),

driver_seasons AS (
    SELECT
        driver_id,
        driver_number,
        constructor_id,
        race_year,
        COUNT(DISTINCT race_id) AS races_in_season
    FROM laps
    GROUP BY driver_id, driver_number, constructor_id, race_year
),

career_summary AS (
    SELECT
        driver_id,
        -- Most recent number (drivers sometimes change numbers)
        MAX(driver_number) AS driver_number,
        MIN(race_year)     AS debut_year,
        SUM(races_in_season) AS career_races_in_dataset
    FROM driver_seasons
    GROUP BY driver_id
)

SELECT
    driver_id,
    driver_number,
    debut_year,
    career_races_in_dataset
FROM career_summary
ORDER BY driver_id
