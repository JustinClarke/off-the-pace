-- assert_microsector_corner_class_covers_panel.sql
-- DA-02P (_roadmap/_dirty-air/wi/DA-02P-prerequisites.md). Every circuit-year
-- (race) in the micro-sector panel has a complete corner-class map: exactly
-- var('microsector_n') rows, micro-sectors 0 .. N - 1 each once, every one
-- with a usable corner_class (not NULL, not 'unknown', and not 'no_geometry'
-- outside the registered exceptions below), and a positive lap length. Every
-- other class is usable, including 'flat' (apex >= 280 km/h, D5 / DD10).
-- Without this the P3 placebo would silently fit on the races the map happens
-- to cover. Returns one row per failing race.
--
-- REGISTERED EXCEPTIONS (DA-02P amendment): 2020_9 (Tuscan, Mugello) and
-- 2020_16 (Sakhir, Bahrain outer loop). FastF1's corner table for both is
-- empty in bronze and neither layout was raced in another season, so
-- dim_corners has no geometry to classify. They must still have their N rows
-- (class no_geometry) and nothing else may be unusable; P3 leaves them out.
-- Any other race that loses its geometry fails here.
{{ config(tags=['dirty_air_dynamic']) }}

{%- set n = var('microsector_n') %}

WITH panel_races AS (
    SELECT DISTINCT
        race_year,
        race_id
    FROM {{ ref('int_microsector_crossings') }}
),

map_rows AS (
    SELECT
        race_year,
        race_id,
        microsector,
        lap_length_m,
        CASE
            WHEN corner_class IS NULL THEN 1
            WHEN corner_class = 'unknown' THEN 1
            WHEN
                corner_class = 'no_geometry'
                AND race_id NOT IN ('2020_9', '2020_16')
                THEN 1
            ELSE 0
        END AS is_unusable
    FROM {{ ref('int_microsector_corner_class') }}
),

map_by_race AS (
    SELECT
        race_year,
        race_id,
        COUNT(*) AS rows_n,
        COUNT(DISTINCT microsector) AS microsectors_n,
        MIN(microsector) AS min_microsector,
        MAX(microsector) AS max_microsector,
        SUM(is_unusable) AS unusable_n,
        MIN(lap_length_m) AS min_lap_length_m
    FROM map_rows
    GROUP BY race_year, race_id
)

SELECT
    p.race_year,
    p.race_id,
    m.rows_n,
    m.microsectors_n,
    m.min_microsector,
    m.max_microsector,
    m.unusable_n,
    m.min_lap_length_m
FROM panel_races AS p
LEFT JOIN map_by_race AS m
    ON
        p.race_year = m.race_year
        AND p.race_id = m.race_id
WHERE
    m.race_id IS NULL
    OR m.rows_n != {{ n }}
    OR m.microsectors_n != {{ n }}
    OR m.min_microsector != 0
    OR m.max_microsector != {{ n }} - 1
    OR m.unusable_n > 0
    OR NOT (m.min_lap_length_m > 0)
