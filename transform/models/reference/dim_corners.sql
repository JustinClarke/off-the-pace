-- dim_corners.sql · reference · grain: one row per race × circuit turn
-- Telemetry corner windows for the corner-skill chain, derived from FastF1's
-- own corner table (stg_circuit_info) rather than maintained by hand.
--
-- The hand catalogue this replaces held 193 corners across 17 of the 36 event
-- slugs, and int_corner_metrics gates on it with an INNER JOIN, so the other 19
-- -- Hungary, Melbourne, Baku, Jeddah, Miami, Las Vegas and Imola among them --
-- had no corner measurement at all. Its windows were also a uniform tiling of
-- 250-500 m blocks abutting one another rather than measured corner positions:
-- the block it called Bahrain "Turn_2" (700-1050 m) spans FastF1's turns 1, 2
-- and 3, whose apexes sit at 717, 819 and 941 m.
--
-- Geometry is per session, not per venue. FastF1 publishes the corner table per
-- event, venues re-profile mid-history (Abu Dhabi 2021, Barcelona 2023 and
-- Singapore 2023 each change corner count) and the distance origin can shift
-- between seasons at the same track -- the same discontinuity
-- int_track_geometry documents in the X/Y frame. Each race is windowed on
-- its own session's geometry; a race with no corner table borrows the nearest
-- season of the same event slug and records that in geometry_source. Nothing
-- here pools across event slugs, so the venue-identity trap (one physical
-- circuit carrying several slugs) cannot reach the windows.
--
-- Window: apex − corner_entry_margin_m to apex + corner_exit_margin_m, each end
-- clipped at the neighbouring apex so a corner never reaches past its
-- neighbours. Consecutive corners can overlap in the stretch between them: that
-- stretch is both the exit of one and the approach to the next, and each corner
-- aggregates its own window independently.
--
-- Validated against the telemetry speed trace: over the 1,586 slow corners
-- (apex below 55% of the race's peak binned speed, where the minimum is
-- unambiguous), the FastF1 apex sits a median 2 m from the measured speed
-- minimum, and no venue's median offset exceeds 54 m. The geometry is trusted
-- as published; a venue later found bad would be corrected by adding a seed
-- override here, and none needs one today.
{{ config(materialized='table') }}

WITH races AS (
    SELECT DISTINCT
        race_year,
        race_id
    FROM {{ ref('stg_laps') }}
),

race_map AS (
    SELECT
        race_id,
        track_id
    FROM {{ ref('race_to_track') }}
),

geometry AS (
    SELECT
        race_year,
        race_id,
        race_slug,
        corner_number,
        corner_letter,
        corner_distance_m,
        CONCAT(
            'Turn_',
            CAST(corner_number AS VARCHAR),
            COALESCE(corner_letter, '')
        ) AS corner_name
    FROM {{ ref('stg_circuit_info') }}
),

geometry_sessions AS (
    SELECT DISTINCT
        race_year,
        race_id,
        race_slug
    FROM geometry
),

-- Every (race, candidate geometry session) pair: the race's own session where
-- FastF1 published one, plus every session at the same event slug as a
-- fallback. The slug match is ORed with the self match so a race missing from
-- race_to_track (2018_14) still resolves through its own corner table.
candidates AS (
    SELECT
        r.race_year,
        r.race_id,
        m.track_id,
        g.race_id AS geometry_race_id,
        g.race_slug,
        CASE
            WHEN g.race_id = r.race_id THEN 'session' ELSE 'nearest_season'
        END AS geometry_source,
        ROW_NUMBER() OVER (
            PARTITION BY r.race_id
            ORDER BY
                CASE WHEN g.race_id = r.race_id THEN 0 ELSE 1 END ASC,
                ABS(g.race_year - r.race_year) ASC,
                g.race_year DESC
        ) AS candidate_rank
    FROM races AS r
    LEFT JOIN race_map AS m ON r.race_id = m.race_id
    INNER JOIN geometry_sessions AS g
        ON
            r.race_id = g.race_id
            OR m.track_id = g.race_slug
),

resolved AS (
    SELECT
        race_year,
        race_id,
        track_id,
        geometry_race_id,
        race_slug,
        geometry_source
    FROM candidates
    WHERE candidate_rank = 1
),

windowed AS (
    SELECT
        res.race_year,
        res.race_id,
        res.geometry_race_id,
        res.geometry_source,
        g.corner_name,
        g.corner_number,
        g.corner_letter,
        g.corner_distance_m AS apex_distance_m,
        COALESCE(res.track_id, res.race_slug) AS track_id,
        LAG(g.corner_distance_m) OVER w AS prev_apex_m,
        LEAD(g.corner_distance_m) OVER w AS next_apex_m
    FROM resolved AS res
    INNER JOIN geometry AS g ON res.geometry_race_id = g.race_id
    WINDOW w AS (PARTITION BY res.race_id ORDER BY g.corner_distance_m)
)

SELECT
    w.race_year,
    w.race_id,
    w.track_id,
    w.corner_name,
    w.corner_number,
    w.corner_letter,
    w.apex_distance_m,
    w.geometry_race_id,
    w.geometry_source,
    CONCAT(w.race_id, '_', w.corner_name) AS corner_key,
    c.circuit_id,
    GREATEST(
        w.apex_distance_m - {{ var('corner_entry_margin_m') }},
        COALESCE(w.prev_apex_m, 0),
        0
    ) AS start_distance_m,
    LEAST(
        w.apex_distance_m + {{ var('corner_exit_margin_m') }},
        COALESCE(
            w.next_apex_m,
            w.apex_distance_m + {{ var('corner_exit_margin_m') }}
        )
    ) AS end_distance_m
FROM windowed AS w
LEFT JOIN {{ ref('dim_circuits') }} AS c ON w.track_id = c.circuit_key
ORDER BY w.race_year, w.race_id, w.apex_distance_m
