-- TX-06. mart_driver_season_summary carries its upstream uncertainty
-- unchanged: rating_se_s, rating_confidence, total_clean_laps_n,
-- bridge_driver_anchor_flag and low_anchor_sample_flag equal
-- int_era_normalized_driver_rating on (driver_id, race_year = season); the CI
-- identity ci_high - rating_s = 1.96 x rating_se_s holds within 1e-12; and
-- rank_separated_from_next matches its definition (ci_high < the next-ranked
-- driver's ci_low, NULL for the last-ranked). Fails per offending row, and
-- once if the mart has no rows (the CI fixture does produce season rows).
WITH m AS (
    SELECT
        *,
        LEAD(ci_low) OVER (
            PARTITION BY race_year ORDER BY rating_s, driver_id
        ) AS next_ci_low
    FROM {{ ref('mart_driver_season_summary') }}
),

src AS (
    SELECT * FROM {{ ref('int_era_normalized_driver_rating') }}
)

SELECT
    'column_not_carried' AS failure,
    m.driver_id,
    m.race_year
FROM m
LEFT JOIN src AS s ON m.driver_id = s.driver_id AND m.race_year = s.season
WHERE
    s.driver_id IS NULL
    OR m.rating_se_s IS DISTINCT FROM s.era_adjusted_rating_se_s
    OR m.rating_confidence IS DISTINCT FROM s.rating_confidence
    OR m.total_clean_laps_n IS DISTINCT FROM s.total_clean_laps_n
    OR m.bridge_driver_anchor_flag IS DISTINCT FROM s.bridge_driver_anchor_flag
    OR m.low_anchor_sample_flag IS DISTINCT FROM s.low_anchor_sample_flag

UNION ALL

SELECT
    'ci_identity' AS failure,
    driver_id,
    race_year
FROM m
WHERE
    ABS((ci_high - rating_s) - 1.96 * rating_se_s) > 1e-12
    OR ABS((rating_s - ci_low) - 1.96 * rating_se_s) > 1e-12

UNION ALL

SELECT
    'rank_separated_wrong' AS failure,
    driver_id,
    race_year
FROM m
WHERE rank_separated_from_next IS DISTINCT FROM (ci_high < next_ci_low)

UNION ALL

SELECT
    'no_rows' AS failure,
    NULL AS driver_id,
    NULL AS race_year
WHERE (SELECT COUNT(*) FROM m) = 0
