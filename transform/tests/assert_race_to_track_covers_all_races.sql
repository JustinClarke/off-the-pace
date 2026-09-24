-- T4 (WI-05, F8). No race may silently disappear through an INNER JOIN.
--
-- race_to_track had no 2018_14 row, and the INNER JOINs in int_lap_fuel_state and
-- int_compound_cliff_predicted dropped the whole 2018 Italian GP (927 laps, 833
-- valid) with nothing saying so. Both joins stay INNER -- a race with no track
-- slug cannot be priced -- so this test is what makes them safe:
--
-- 1. every race in stg_laps has a race_to_track row;
-- 2. every race_to_track slug resolves in dim_circuits (int_lap_fuel_state's
--    second INNER hop);
-- 3. every race with a valid lap reaches the two named join sites and the lap
--    spine -- a direct check that nothing further down drops a race either.
--    (A race with no valid lap at all, like 2021_12 -- 60 laps, every one
--    neutralised -- legitimately has no row in any of them.)

WITH races AS (
    SELECT DISTINCT race_id FROM {{ ref('stg_laps') }}
),

races_with_valid_laps AS (
    SELECT DISTINCT race_id FROM {{ ref('stg_laps') }} WHERE is_valid_lap
)

SELECT
    'race_missing_from_race_to_track' AS check_name,
    r.race_id AS detail
FROM races AS r
LEFT JOIN {{ ref('race_to_track') }} AS rt ON r.race_id = rt.race_id
WHERE rt.race_id IS NULL

UNION ALL

SELECT
    'track_missing_from_dim_circuits' AS check_name,
    rt.race_id || ' -> ' || rt.track_id AS detail
FROM {{ ref('race_to_track') }} AS rt
LEFT JOIN {{ ref('dim_circuits') }} AS d ON rt.track_id = d.circuit_key
WHERE d.circuit_key IS NULL

UNION ALL

SELECT
    'race_dropped_by_int_lap_fuel_state' AS check_name,
    v.race_id AS detail
FROM races_with_valid_laps AS v
WHERE v.race_id NOT IN (SELECT DISTINCT race_id FROM {{ ref('int_lap_fuel_state') }})

UNION ALL

SELECT
    'race_dropped_by_int_compound_cliff_predicted' AS check_name,
    v.race_id AS detail
FROM races_with_valid_laps AS v
WHERE v.race_id NOT IN (SELECT DISTINCT race_id FROM {{ ref('int_compound_cliff_predicted') }})

UNION ALL

SELECT
    'race_dropped_by_int_lap_residual_decomposed' AS check_name,
    v.race_id AS detail
FROM races_with_valid_laps AS v
WHERE v.race_id NOT IN (SELECT DISTINCT race_id FROM {{ ref('int_lap_residual_decomposed') }})
