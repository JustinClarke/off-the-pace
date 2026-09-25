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
        -- Most recent number (drivers sometimes change numbers): the one
        -- carried in the driver's latest season, or the one raced under most
        -- within it if they carried two. This was MAX(driver_number), a string
        -- maximum, which ranks '33' above '1' and '45' above '21', so VER, DEV
        -- and LAW kept an old number (F17).
        ARG_MAX(driver_number, (race_year, races_in_season)) AS driver_number,
        MIN(race_year) AS debut_year,
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
