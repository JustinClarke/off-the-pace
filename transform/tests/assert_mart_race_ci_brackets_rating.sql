-- TX-01. mart_race_driver_summary's CI is the order-statistic CI of the
-- median paired gap, built from int_driver_race_paired_laps. Checks:
--   1. ci_low <= rating_s <= ci_high wherever the CI exists;
--   2. CI NULL <=> paired_lap_count < 6 (both bounds together);
--   3. two-driver cars: ci_low(A) = -ci_high(B) within 1e-9 (the teammate's
--      gaps are the driver's with the sign flipped);
--   4. paired_lap_count equals int_driver_race_skill_loro.paired_lap_count,
--      and the median of the paired rows equals driver_skill_loro_s, so the
--      new model's clean filter has not drifted from the rating's;
--   5. rating_trust_label matches the 6 / 12 thresholds.
-- Fails per offending row, and once if no row has a CI to bracket (only the
-- bracket check carries that guard: the CI fixture may have no n < 6 row).
WITH m AS (
    SELECT * FROM {{ ref('mart_race_driver_summary') }}
),

src AS (
    SELECT race_id, driver_id, paired_lap_count, driver_skill_loro_s
    FROM {{ ref('int_driver_race_skill_loro') }}
),

pairs AS (
    SELECT
        race_id,
        driver_id,
        COUNT(*) AS n,
        MEDIAN(paired_delta_s) AS median_s
    FROM {{ ref('int_driver_race_paired_laps') }}
    GROUP BY race_id, driver_id
),

two_driver_cars AS (
    SELECT race_id, constructor_id
    FROM m
    GROUP BY race_id, constructor_id
    HAVING COUNT(*) = 2
)

SELECT
    'ci_does_not_bracket_rating' AS failure,
    race_id, driver_id, rating_s AS value_s
FROM m
WHERE ci_low IS NOT NULL AND NOT (ci_low <= rating_s AND rating_s <= ci_high)

UNION ALL

SELECT
    'ci_null_iff_n_below_6' AS failure,
    race_id, driver_id, paired_lap_count AS value_s
FROM m
WHERE
    (ci_low IS NULL) <> (ci_high IS NULL)
    OR (ci_low IS NULL) <> (paired_lap_count < 6)

UNION ALL

SELECT
    'teammate_ci_not_mirrored' AS failure,
    a.race_id, a.driver_id, a.ci_low + b.ci_high AS value_s
FROM m AS a
INNER JOIN two_driver_cars AS t
    ON a.race_id = t.race_id AND a.constructor_id = t.constructor_id
INNER JOIN m AS b
    ON
        a.race_id = b.race_id
        AND a.constructor_id = b.constructor_id
        AND a.driver_id <> b.driver_id
WHERE
    (a.ci_low IS NULL) <> (b.ci_high IS NULL)
    OR ABS(a.ci_low + b.ci_high) > 1e-9

UNION ALL

SELECT
    'paired_n_or_median_differs_from_intermediate' AS failure,
    m.race_id, m.driver_id, m.paired_lap_count AS value_s
FROM m
INNER JOIN src ON m.race_id = src.race_id AND m.driver_id = src.driver_id
LEFT JOIN pairs AS p ON m.race_id = p.race_id AND m.driver_id = p.driver_id
WHERE
    m.paired_lap_count IS DISTINCT FROM src.paired_lap_count
    OR p.n IS DISTINCT FROM src.paired_lap_count
    OR ABS(p.median_s - src.driver_skill_loro_s) > 1e-9
    OR p.median_s IS NULL

UNION ALL

SELECT
    'trust_label_wrong' AS failure,
    race_id, driver_id, paired_lap_count AS value_s
FROM m
WHERE
    rating_trust_label IS DISTINCT FROM CASE
        WHEN paired_lap_count >= 12 THEN 'ok'
        WHEN paired_lap_count >= 6 THEN 'thin'
        ELSE 'suppressed'
    END

UNION ALL

SELECT
    'no_rows_with_ci' AS failure,
    NULL AS race_id,
    NULL AS driver_id,
    NULL AS value_s
WHERE (SELECT COUNT(ci_low) FROM m) = 0
