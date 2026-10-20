-- dim_driver_seasons.sql · reference · grain: one row per season × driver code
-- The three-letter code is reused across seasons and names vary by season (ALB
-- has two driver IDs over 2019-2025; ANT has two name variants in 2025), so the
-- season is part of the key. driver_id is FastF1's stable DriverId, and the
-- names are the official ones for that season. Built from bronze race results
-- only, so no new source is needed.
{{ config(materialized='table') }}

WITH results AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_results') }}
    WHERE abbreviation IS NOT NULL
)

SELECT
    CAST(season AS INTEGER) AS season,
    abbreviation AS driver_code,
    -- A DriverId conflict must fail, not be hidden: MIN is safe only
    -- because assert_dim_driver_seasons_single_driver_id guarantees one
    -- DriverId per group.
    MIN(driverid) AS driver_id,
    -- Name spellings can differ within a group (ANT 2025); MIN picks one
    -- arbitrarily (alphabetically first), fine for a display name.
    MIN(fullname) AS full_name,
    MIN(firstname) AS first_name,
    MIN(lastname) AS last_name,
    MODE(teamname) AS team_name
FROM results
GROUP BY CAST(season AS INTEGER), abbreviation
ORDER BY season, driver_code
