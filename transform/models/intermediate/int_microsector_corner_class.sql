-- int_microsector_corner_class.sql · intermediate · grain: one row per
-- (race, micro-sector), m = 0 .. var('microsector_n') - 1.
-- DA-02P (_roadmap/_dirty-air/wi/DA-02P-prerequisites.md): the micro-sector
-- to corner-class map the DA-03 P3 mechanism placebo needs (loss in
-- high-speed corners, tow gain on straights). It is built from corner
-- GEOMETRY and apex SPEED only. Nothing here reads a gap, a time loss or the
-- micro-sector panel, and the thresholds were fixed before any loss-versus-gap
-- number was looked at (pre-registration amendment, DA-02P).
--
-- WHERE A MICRO-SECTOR IS IN METRES. int_microsector_crossings puts boundary
-- m at lap fraction m / N of relative_distance, and FastF1 computes
-- relative_distance as distance / lap length per lap. So the lap length of a
-- race is the median of distance_m / relative_distance over its green-lap
-- position samples (mid-lap samples only, 0.25 to 0.95, where the ratio is
-- well conditioned), and micro-sector m spans [m, m + 1) * lap_length_m / N.
--
-- APEX SPEED. For each dim_corners corner (FastF1 apex position, per session),
-- the minimum position-channel speed within apex_window_m either side of the
-- apex on each green racing lap, then the median over laps. Local to the apex
-- on purpose: int_corner_metrics.v_min_kph is the minimum over a window that
-- is clipped at the neighbouring apex, so a fast corner just after a slow one
-- inherits the slow corner's speed, and its stg_telemetry input is cut at
-- 6500 m, which loses the end of a Spa lap. Green racing lap: lap >= 2,
-- stg_laps.is_valid_lap, lap track status '1', not an SC, VSC or red-flag lap,
-- and the sample OnTrack.
--
-- CLASSES (thresholds fixed in the DA-02P amendment; change them only by a
-- new amendment, never after a fit)
--   apex class   low: apex < 120 km/h   medium: 120 to < 200
--                high: 200 to < 280     flat: >= 280 (flat-out kinks, where a
--                following car may get a tow; split out of high by owner
--                decision D5 / DD10, 2026-10-25, so tow gain cannot blend into
--                the fast-corner test; reported, never part of high)
--   micro-sector corner_class
--     low / medium / high / flat  every apex inside the micro-sector has that
--                          class
--     mixed                apexes of more than one class inside it (so a
--                          micro-sector with a high and a flat apex is mixed
--                          and outside the fast-corner test)
--     straight             no apex inside, none in the straight_lead_m before
--                          its start (exit of the corner behind) and none in
--                          the straight_trail_m after its end (braking for
--                          the corner ahead)
--     link                 no apex inside, but one inside those buffers
--     unknown              an apex inside has no apex speed (no green lap)
--     no_geometry          the race has no dim_corners rows (2020 Tuscan and
--                          2020 Sakhir: FastF1's corner table is empty and no
--                          other season of either layout exists; registered
--                          as P3 exceptions in the DA-02P amendment)
-- unknown and no_geometry must not occur on a panel race:
-- assert_microsector_corner_class_covers_panel.
--
-- Positions wrap: each apex is also placed one lap length behind and ahead,
-- so the micro-sector before the lap line sees the first corner, and an apex
-- of a borrowed (nearest_season) geometry beyond this race's lap length still
-- lands in exactly one micro-sector.
{{ config(materialized='table', tags=['dirty_air_dynamic']) }}

{%- set n = var('microsector_n') %}
{%- set low_max_kph = 120 %}
{%- set medium_max_kph = 200 %}
{%- set flat_min_kph = 280 %}
{%- set apex_window_m = 50 %}
{%- set straight_lead_m = 100 %}
{%- set straight_trail_m = 150 %}
{%- set bucket_m = 100 %}

WITH green_laps AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number
    FROM {{ ref('stg_laps') }}
    WHERE
        lap_number >= 2
        AND is_valid_lap
        AND track_status = '1'
        AND NOT COALESCE(is_safety_car_lap, FALSE)
        AND NOT COALESCE(is_vsc_lap, FALSE)
        AND NOT COALESCE(is_red_flag_lap, FALSE)
),

on_track_samples AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        distance_m,
        relative_distance,
        speed_kph
    FROM {{ ref('stg_telemetry_position') }}
    WHERE
        track_status = 'OnTrack'
        AND distance_m IS NOT NULL
        AND lap_number >= 2
),

samples AS (
    SELECT s.*
    FROM on_track_samples AS s
    INNER JOIN green_laps AS g
        ON
            s.race_year = g.race_year
            AND s.race_id = g.race_id
            AND s.driver_id = g.driver_id
            AND s.lap_number = g.lap_number
),

-- Lap length does not depend on speed, so it uses every on-track lap from lap
-- 2, not only green ones (2021 Belgium has no green racing lap).
lap_length AS (
    SELECT
        race_year,
        race_id,
        ROUND(MEDIAN(distance_m / relative_distance), 3) AS lap_length_m
    FROM on_track_samples
    WHERE relative_distance BETWEEN 0.25 AND 0.95
    GROUP BY race_year, race_id
),

corners AS (
    SELECT
        race_year,
        race_id,
        track_id,
        corner_name,
        apex_distance_m,
        geometry_race_id,
        geometry_source
    FROM {{ ref('dim_corners') }}
),

-- Each corner listed under every bucket_m bucket its apex window touches, so
-- the sample join is an equality join on (race, bucket).
corner_buckets AS (
    SELECT
        c.race_year,
        c.race_id,
        c.corner_name,
        c.apex_distance_m,
        UNNEST(GENERATE_SERIES(c.first_bucket, c.last_bucket)) AS bucket
    FROM (
        SELECT
            race_year,
            race_id,
            corner_name,
            apex_distance_m,
            CAST(
                FLOOR((apex_distance_m - {{ apex_window_m }}) / {{ bucket_m }})
                AS BIGINT
            ) AS first_bucket,
            CAST(
                FLOOR((apex_distance_m + {{ apex_window_m }}) / {{ bucket_m }})
                AS BIGINT
            ) AS last_bucket
        FROM corners
    ) AS c
),

apex_lap AS (
    SELECT
        cb.race_year,
        cb.race_id,
        cb.corner_name,
        s.driver_id,
        s.lap_number,
        MIN(s.speed_kph) AS apex_speed_lap_kph
    FROM samples AS s
    INNER JOIN corner_buckets AS cb
        ON
            s.race_year = cb.race_year
            AND s.race_id = cb.race_id
            AND CAST(FLOOR(s.distance_m / {{ bucket_m }}) AS BIGINT) = cb.bucket
    WHERE ABS(s.distance_m - cb.apex_distance_m) <= {{ apex_window_m }}
    GROUP BY cb.race_year, cb.race_id, cb.corner_name, s.driver_id, s.lap_number
),

apex_speed AS (
    SELECT
        race_year,
        race_id,
        corner_name,
        ROUND(MEDIAN(apex_speed_lap_kph), 1) AS apex_speed_kph,
        COUNT(*) AS apex_laps_n
    FROM apex_lap
    GROUP BY race_year, race_id, corner_name
),

-- A race with no green-lap apex speed for a corner whose geometry dim_corners
-- already borrows from another season (nearest_season) takes that season's
-- apex speed for the same corner: the same borrow, one column further. Only
-- 2021 Belgium needs it today (no green racing lap; geometry from 2022).
corner_speed AS (
    SELECT
        c.race_year,
        c.race_id,
        c.corner_name,
        c.apex_distance_m,
        COALESCE(a.apex_speed_kph, b.apex_speed_kph) AS apex_speed_kph,
        a.apex_speed_kph IS NULL AND b.apex_speed_kph IS NOT NULL
            AS apex_speed_borrowed
    FROM corners AS c
    LEFT JOIN apex_speed AS a
        ON
            c.race_year = a.race_year
            AND c.race_id = a.race_id
            AND c.corner_name = a.corner_name
    LEFT JOIN apex_speed AS b
        ON
            c.geometry_source = 'nearest_season'
            AND c.geometry_race_id = b.race_id
            AND c.corner_name = b.corner_name
),

classed_corners AS (
    SELECT
        race_year,
        race_id,
        corner_name,
        apex_distance_m,
        apex_speed_kph,
        apex_speed_borrowed,
        CASE
            WHEN apex_speed_kph IS NULL THEN 'unknown'
            WHEN apex_speed_kph < {{ low_max_kph }} THEN 'low'
            WHEN apex_speed_kph < {{ medium_max_kph }} THEN 'medium'
            WHEN apex_speed_kph >= {{ flat_min_kph }} THEN 'flat'
            ELSE 'high'
        END AS apex_class
    FROM corner_speed
),

-- Each apex at its own position and one lap length either side (wrap).
corner_positions AS (
    SELECT
        cc.race_year,
        cc.race_id,
        cc.corner_name,
        cc.apex_speed_kph,
        cc.apex_class,
        cc.apex_speed_borrowed,
        cc.apex_distance_m + k.lap_shift * l.lap_length_m AS pos_m
    FROM classed_corners AS cc
    INNER JOIN lap_length AS l
        ON
            cc.race_year = l.race_year
            AND cc.race_id = l.race_id
    CROSS JOIN (VALUES (-1), (0), (1)) AS k (lap_shift)
),

race_meta AS (
    SELECT
        race_year,
        race_id,
        ANY_VALUE(track_id) AS track_id,
        ANY_VALUE(geometry_source) AS geometry_source,
        COUNT(*) AS race_corners_n
    FROM corners
    GROUP BY race_year, race_id
),

microsectors AS (
    SELECT
        l.race_year,
        l.race_id,
        l.lap_length_m,
        CAST(m.range AS INTEGER) AS microsector,
        ROUND(m.range * l.lap_length_m / {{ n }}, 3) AS start_m,
        ROUND((m.range + 1) * l.lap_length_m / {{ n }}, 3) AS end_m
    FROM lap_length AS l
    CROSS JOIN RANGE(0, {{ n }}) AS m
),

inside AS (
    SELECT
        ms.race_year,
        ms.race_id,
        ms.microsector,
        COUNT(cp.corner_name) AS apex_n,
        COUNT(DISTINCT cp.apex_class) AS apex_class_n,
        MIN(cp.apex_class) AS any_apex_class,
        BOOL_OR(cp.apex_class = 'unknown') AS has_unknown_apex,
        COALESCE(BOOL_OR(cp.apex_speed_borrowed), FALSE) AS apex_speed_borrowed,
        STRING_AGG(cp.corner_name, ',' ORDER BY cp.pos_m, cp.corner_name)
            AS apex_corners,
        MIN(cp.apex_speed_kph) AS min_apex_speed_kph,
        MAX(cp.apex_speed_kph) AS max_apex_speed_kph
    FROM microsectors AS ms
    LEFT JOIN corner_positions AS cp
        ON
            ms.race_year = cp.race_year
            AND ms.race_id = cp.race_id
            AND ms.start_m <= cp.pos_m
            AND ms.end_m > cp.pos_m
    GROUP BY ms.race_year, ms.race_id, ms.microsector
),

near AS (
    SELECT
        ms.race_year,
        ms.race_id,
        ms.microsector,
        COUNT(cp.corner_name) AS near_apex_n
    FROM microsectors AS ms
    LEFT JOIN corner_positions AS cp
        ON
            ms.race_year = cp.race_year
            AND ms.race_id = cp.race_id
            AND (
                (
                    ms.start_m - {{ straight_lead_m }} <= cp.pos_m
                    AND ms.start_m > cp.pos_m
                )
                OR (
                    ms.end_m <= cp.pos_m
                    AND ms.end_m + {{ straight_trail_m }} > cp.pos_m
                )
            )
    GROUP BY ms.race_year, ms.race_id, ms.microsector
)

SELECT
    CONCAT(
        ms.race_year, '_', ms.race_id, '_',
        LPAD(CAST(ms.microsector AS VARCHAR), 2, '0')
    ) AS race_microsector_id,
    ms.race_year,
    ms.race_id,
    rm.track_id,
    ms.microsector,
    ms.lap_length_m,
    ms.start_m,
    ms.end_m,
    i.apex_n,
    i.apex_corners,
    i.min_apex_speed_kph,
    i.max_apex_speed_kph,
    nr.near_apex_n,
    CASE
        WHEN COALESCE(rm.race_corners_n, 0) = 0 THEN 'no_geometry'
        WHEN i.apex_n > 0 AND i.has_unknown_apex THEN 'unknown'
        WHEN i.apex_n > 0 AND i.apex_class_n = 1 THEN i.any_apex_class
        WHEN i.apex_n > 0 THEN 'mixed'
        WHEN nr.near_apex_n > 0 THEN 'link'
        ELSE 'straight'
    END AS corner_class,
    rm.geometry_source,
    i.apex_speed_borrowed
FROM microsectors AS ms
INNER JOIN inside AS i
    ON
        ms.race_year = i.race_year
        AND ms.race_id = i.race_id
        AND ms.microsector = i.microsector
INNER JOIN near AS nr
    ON
        ms.race_year = nr.race_year
        AND ms.race_id = nr.race_id
        AND ms.microsector = nr.microsector
LEFT JOIN race_meta AS rm
    ON
        ms.race_year = rm.race_year
        AND ms.race_id = rm.race_id
ORDER BY ms.race_year, ms.race_id, ms.microsector
