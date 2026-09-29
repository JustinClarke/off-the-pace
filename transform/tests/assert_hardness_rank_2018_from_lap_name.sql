-- T52 (WI-17, W50): 2018 hardness rank comes from the lap's own compound name.
--
-- 2018 laps carry absolute names (SOFT, SUPERSOFT, ULTRASOFT, HYPERSOFT, ...), while
-- tyre_allocations maps RELATIVE labels to C-codes. The W50 defect put 2018 rows into
-- tyre_allocations, and int_stint_geometry's LOWER(compound) = compound_label join would have
-- coded 8,967 of 20,664 slick 2018 laps wrong. So every 2018 lap in int_power_law_lap must:
--   * resolve a rank (the lap set is slicks with a name, so every one of them);
--   * take it from its own name: hardness_identity = compound_label, era '2018', and the rank
--     equal to compound_hardness_scale's rank for that name;
--   * have no compound_code, i.e. nothing reached it through tyre_allocations;
-- and tyre_allocations must hold no 2018 row at all. Non-vacuous: 2018 must have laps.

WITH laps_2018 AS (
    SELECT * FROM {{ ref('int_power_law_lap') }}
    WHERE race_year = 2018
),

scale_2018 AS (
    SELECT
        compound_code AS compound_name,
        hardness_rank
    FROM {{ ref('compound_hardness_scale') }}
    WHERE era = '2018'
),

checked AS (
    SELECT
        l.lap_id,
        CASE
            WHEN l.compound_hardness_rank IS NULL THEN '2018 slick lap with a name has no rank'
            WHEN l.compound_code IS NOT NULL THEN '2018 lap carries a compound_code (tyre_allocations reached 2018)'
            WHEN l.hardness_era <> '2018' THEN '2018 lap not in the 2018 hardness era'
            WHEN l.hardness_identity IS DISTINCT FROM l.compound_label THEN '2018 rank looked up on something other than the lap name'
            WHEN s.hardness_rank IS DISTINCT FROM l.compound_hardness_rank THEN '2018 rank differs from the seed rank for the lap name'
        END AS failure
    FROM laps_2018 AS l
    LEFT JOIN scale_2018 AS s
        ON l.compound_label = s.compound_name
)

SELECT lap_id, failure
FROM checked
WHERE failure IS NOT NULL

UNION ALL

SELECT CAST(race_year AS VARCHAR) || '/' || circuit_key, 'tyre_allocations holds a 2018 row'
FROM {{ ref('tyre_allocations') }}
WHERE race_year = 2018

UNION ALL

SELECT 'none', 'int_power_law_lap has no 2018 laps'
WHERE NOT EXISTS (SELECT 1 FROM laps_2018)
