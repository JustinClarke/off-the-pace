-- T30 (F40, WI-14b). The equal-car rating is a teammate comparison, so it
-- must be antisymmetric across a two-driver car: if A is 0.2 s faster than B,
-- B is 0.2 s slower than A, and the two ratings sum to 0.
--
-- int_driver_race_skill_loro.driver_skill_loro_s is the median lap-by-lap gap
-- to the teammate (FD5 option C): both drivers' ratings are medians of the
-- same paired laps with the sign flipped, so each pair sums to 0 up to float
-- rounding in the median interpolation (measured max |sum| 0.0 on the
-- 2026-09-28 build, 1,569 pairs).
--
-- What this catches. Before WI-14b the rating was P20(own) minus the
-- teammate's MEDIAN -- a ceiling against a typical lap -- so each driver
-- carried his own lap-time spread (mean -0.92 s) into the level: mean pair
-- sum -1.83 s at the audit (-1.49 s on the WI-01 label), and in 79% of
-- two-driver cars BOTH teammates were rated faster than each other. Any
-- statistic that mixes location with dispersion, or compares unequal
-- statistics on the two sides, fails here.
--
-- Fails with one row per offending car-race, one row if the mean pair sum
-- drifts from 0 by more than 0.1 s (the audit's T30 bound, kept as a second,
-- coarser line), and one row if there is nothing to check (vacuity guard:
-- the table has two-driver car-races but none carries two ratings).
{{ config(severity='error') }}

WITH rated AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        driver_skill_loro_s
    FROM {{ ref('int_driver_race_skill_loro') }}
    WHERE driver_skill_loro_s IS NOT NULL
),

pairs AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        SUM(driver_skill_loro_s) AS pair_sum_s
    FROM rated
    GROUP BY race_year, race_id, constructor_id
    HAVING COUNT(*) = 2
),

two_driver_cars AS (
    SELECT COUNT(*) AS n_cars
    FROM (
        SELECT race_year, race_id, constructor_id
        FROM {{ ref('int_driver_race_skill_loro') }}
        GROUP BY race_year, race_id, constructor_id
        HAVING COUNT(*) = 2
    )
)

SELECT
    'pair_not_antisymmetric' AS failure,
    race_year,
    race_id,
    constructor_id,
    pair_sum_s AS value_s
FROM pairs
WHERE ABS(pair_sum_s) > 1e-9

UNION ALL

SELECT
    'mean_pair_sum_off_zero' AS failure,
    NULL AS race_year,
    NULL AS race_id,
    NULL AS constructor_id,
    AVG(pair_sum_s) AS value_s
FROM pairs
HAVING ABS(AVG(pair_sum_s)) > 0.1

UNION ALL

SELECT
    'no_rated_pairs' AS failure,
    NULL AS race_year,
    NULL AS race_id,
    NULL AS constructor_id,
    NULL AS value_s
FROM two_driver_cars
WHERE n_cars > 0 AND (SELECT COUNT(*) FROM pairs) = 0
