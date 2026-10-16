-- CO-01 (T3). mart_race_driver_summary.teammate_gap_s is the paired median gap
-- to the teammate, not twice it. driver_skill_loro_s is already
-- MEDIAN(own lap - teammate lap), so the mart's gap must equal that rating, and
-- a two-driver pair's gaps must be exact negatives of each other.
-- Fails per offending row, and once if there is nothing to check.
WITH m AS (
    SELECT * FROM {{ ref('mart_race_driver_summary') }}
),

src AS (
    SELECT race_id, driver_id, driver_skill_loro_s
    FROM {{ ref('int_driver_race_skill_loro') }}
)

SELECT
    'gap_not_equal_paired_median' AS failure,
    m.race_id, m.driver_id, m.teammate_gap_s AS value_s
FROM m
INNER JOIN src USING (race_id, driver_id)
WHERE m.teammate_id IS NOT NULL
    AND ABS(m.teammate_gap_s - src.driver_skill_loro_s) > 1e-9

UNION ALL

SELECT
    'pair_not_antisymmetric' AS failure,
    a.race_id, a.driver_id, a.teammate_gap_s + b.teammate_gap_s AS value_s
FROM m AS a
INNER JOIN m AS b
    ON a.race_id = b.race_id AND a.teammate_id = b.driver_id
        AND b.teammate_id = a.driver_id
WHERE ABS(a.teammate_gap_s + b.teammate_gap_s) > 1e-9

UNION ALL

SELECT 'no_rows_with_teammate' AS failure, NULL, NULL, NULL
WHERE (SELECT COUNT(*) FROM m WHERE teammate_gap_s IS NOT NULL) = 0
