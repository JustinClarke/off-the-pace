-- T20 (WI-05, F25). Lap 1 belongs to the driver's first real stint, and that
-- stint's ordinal and tyre age count from lap 1.
--
-- In 17 of 21 2018 races bronze left lap 1 with no Stint, so lap 1 became a
-- pseudo-stint ('<year>_<race>_<drv>_', CONCAT skipping the NULL), lap_in_stint
-- read 1 at lap 2, and TyreLife -- counted from the first assigned lap -- read one
-- lap low for the whole first stint (24.5% of 2018's eligible rows).
--
-- 1. every driver-race with any assigned stint has lap 1 assigned;
-- 2. lap 1 is on the driver's lowest stint number;
-- 3. on the stint that contains lap 1, lap_in_stint = lap_number (the ordinal
--    counts from lap 1, so lap 2 is 2);
-- 4. on that stint, tyre age rises by exactly one per lap over laps 1-3 -- the
--    lap-1 fill without the matching TyreLife offset would repeat a value here.

WITH geom AS (
    SELECT * FROM {{ ref('int_stint_geometry') }}
),

driver_race AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        MIN(stint_number) AS first_stint_number,
        COUNT(stint_number) AS n_assigned_laps
    FROM geom
    GROUP BY race_year, race_id, driver_id
),

lap1 AS (
    SELECT race_year, race_id, driver_id, stint_id, stint_number
    FROM geom
    WHERE lap_number = 1
),

lap1_stint AS (
    SELECT g.*
    FROM geom AS g
    INNER JOIN lap1 AS l ON g.stint_id = l.stint_id
    WHERE l.stint_number IS NOT NULL
)

SELECT
    'lap1_unassigned' AS check_name,
    dr.race_id || ' ' || dr.driver_id AS detail
FROM driver_race AS dr
INNER JOIN lap1 AS l
    ON
        dr.race_year = l.race_year
        AND dr.race_id = l.race_id
        AND dr.driver_id = l.driver_id
WHERE dr.n_assigned_laps > 0 AND l.stint_number IS NULL

UNION ALL

SELECT
    'lap1_not_on_first_stint' AS check_name,
    dr.race_id || ' ' || dr.driver_id AS detail
FROM driver_race AS dr
INNER JOIN lap1 AS l
    ON
        dr.race_year = l.race_year
        AND dr.race_id = l.race_id
        AND dr.driver_id = l.driver_id
WHERE l.stint_number <> dr.first_stint_number

UNION ALL

SELECT
    'first_stint_ordinal_not_from_lap1' AS check_name,
    stint_id || ' lap ' || lap_number || ' lap_in_stint ' || lap_in_stint
        AS detail
FROM lap1_stint
WHERE lap_in_stint <> lap_number

UNION ALL

SELECT
    'first_stint_age_not_counting_from_lap1' AS check_name,
    a.stint_id || ' lap ' || a.lap_number || ': age ' || a.age_in_stint
    || ' after ' || a.prev_age AS detail
FROM (
    SELECT
        stint_id,
        lap_number,
        age_in_stint,
        LAG(age_in_stint) OVER (
            PARTITION BY stint_id ORDER BY lap_number
        ) AS prev_age
    FROM lap1_stint
    WHERE lap_number <= 3
) AS a
WHERE a.prev_age IS NOT NULL AND a.age_in_stint <> a.prev_age + 1
