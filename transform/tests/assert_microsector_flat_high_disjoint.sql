-- assert_microsector_flat_high_disjoint.sql
-- DA-02P (_roadmap/_dirty-air/wi/DA-02P-prerequisites.md), owner decision D5 /
-- DD10 (2026-10-25): flat-out kinks (apex speed at or above 280 km/h) are their
-- own class and are never part of the fast-corner class 'high' (200 to under
-- 280 km/h), so a tow in a flat kink cannot blend into the P3 fast-corner test.
-- Returns one row per micro-sector that breaks the split:
--   a 'high' micro-sector holding an apex at or above 280 km/h, or
--   a 'flat' micro-sector holding an apex below 280 km/h.
-- (A micro-sector with both a high and a flat apex must be 'mixed'.)
{{ config(tags=['dirty_air_dynamic']) }}

{%- set flat_min_kph = 280 %}

SELECT
    race_microsector_id,
    race_year,
    race_id,
    microsector,
    corner_class,
    apex_corners,
    min_apex_speed_kph,
    max_apex_speed_kph
FROM {{ ref('int_microsector_corner_class') }}
WHERE
    (
        corner_class = 'high'
        AND (
            max_apex_speed_kph IS NULL
            OR max_apex_speed_kph >= {{ flat_min_kph }}
        )
    )
    OR (
        corner_class = 'flat'
        AND (
            min_apex_speed_kph IS NULL
            OR min_apex_speed_kph < {{ flat_min_kph }}
        )
    )
