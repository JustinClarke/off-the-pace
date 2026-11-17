-- TX-27. Jolpica pit stops beside FastF1 (stg_pits) per driver-race, as two
-- separate measured sources; neither overwrites the other. NOT exported
-- (scratch-only until AP-09 / AX-28).
-- Grain: race_id x driver_id (FastF1 abbreviation). A driver-race appears when
-- either source has a stop. Jolpica's Ergast driver id is mapped to the
-- abbreviation through Bronze race results (DriverId -> Abbreviation); an
-- unmapped Jolpica row keeps driver_id NULL with its ergast id.
-- Laps compared are the in-lap: stg_pits.pit_in_lap_number vs Jolpica lap.
-- crosscheck_status: AGREE (same count and laps), COUNT_DIFFERS, LAPS_DIFFER,
-- JOLPICA_RACE_MISSING (Jolpica has no stop for the whole race),
-- FASTF1_RACE_MISSING (FastF1 has no lap for the whole race, e.g. 2018_14).
{{ config(materialized='table', tags=['marts', 'new_data']) }}

WITH id_map AS (
    SELECT DISTINCT
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(driverid AS VARCHAR) AS driver_ergast_id,
        CAST(abbreviation AS VARCHAR) AS driver_id
    FROM {{ source('bronze_f1', 'raw_results') }}
),

jolpica AS (
    SELECT
        j.race_id,
        j.race_year,
        COALESCE(m.driver_id, '?' || j.driver_ergast_id) AS driver_id,
        j.driver_ergast_id,
        COUNT(*) AS jolpica_n_stops,
        STRING_AGG(CAST(j.lap_number AS VARCHAR), ',' ORDER BY j.lap_number) AS jolpica_laps,
        SUM(j.duration_s) AS jolpica_total_duration_s,
        COUNT(j.duration_s) AS jolpica_n_durations
    FROM {{ ref('stg_jolpica_pit_stops') }} AS j
    LEFT JOIN id_map AS m
        ON j.race_id = m.race_id AND j.driver_ergast_id = m.driver_ergast_id
    GROUP BY j.race_id, j.race_year, COALESCE(m.driver_id, '?' || j.driver_ergast_id),
        j.driver_ergast_id
),

fastf1 AS (
    SELECT
        race_id,
        race_year,
        driver_id,
        COUNT(*) AS fastf1_n_stops,
        STRING_AGG(CAST(pit_in_lap_number AS VARCHAR), ',' ORDER BY pit_in_lap_number)
            AS fastf1_laps,
        SUM(pit_duration_s) AS fastf1_total_pit_lane_s
    FROM {{ ref('stg_pits') }}
    GROUP BY race_id, race_year, driver_id
),

jolpica_races AS (SELECT DISTINCT race_id FROM {{ ref('stg_jolpica_pit_stops') }}),
fastf1_races AS (SELECT DISTINCT race_id FROM {{ ref('stg_laps') }}),

joined AS (
    SELECT
        COALESCE(f.race_id, j.race_id) AS race_id,
        COALESCE(f.race_year, j.race_year) AS race_year,
        COALESCE(f.driver_id, j.driver_id) AS driver_id,
        j.driver_ergast_id,
        f.fastf1_n_stops,
        f.fastf1_laps,
        f.fastf1_total_pit_lane_s,
        j.jolpica_n_stops,
        j.jolpica_laps,
        j.jolpica_total_duration_s,
        j.jolpica_n_durations
    FROM fastf1 AS f
    FULL OUTER JOIN jolpica AS j
        ON f.race_id = j.race_id AND f.driver_id = j.driver_id
)

SELECT
    CONCAT(jn.race_id, '_', jn.driver_id) AS crosscheck_id,
    jn.*,
    CASE
        WHEN jr.race_id IS NULL THEN 'JOLPICA_RACE_MISSING'
        WHEN fr.race_id IS NULL THEN 'FASTF1_RACE_MISSING'
        WHEN COALESCE(jn.fastf1_n_stops, 0) <> COALESCE(jn.jolpica_n_stops, 0)
            THEN 'COUNT_DIFFERS'
        WHEN jn.fastf1_laps IS DISTINCT FROM jn.jolpica_laps THEN 'LAPS_DIFFER'
        ELSE 'AGREE'
    END AS crosscheck_status
FROM joined AS jn
LEFT JOIN jolpica_races AS jr ON jn.race_id = jr.race_id
LEFT JOIN fastf1_races AS fr ON jn.race_id = fr.race_id
ORDER BY jn.race_year, jn.race_id, jn.driver_id
