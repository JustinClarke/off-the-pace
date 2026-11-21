-- Every qualifying red flag is counted in exactly one segment.
--
-- int_qualifying_segments reads red flags from stg_red_flags_qualifying (track
-- status), not from session status's 'Aborted' rows, which omit some of them
-- (2019_4, 2019_7, 2022_9, 2023_15, 2025_7, 2025_8, 2024_21). Per race, the
-- stoppage_n summed over Q1..Q3 must equal the red flags raised after Q1 opened.
-- Races with no segment rows (no qualifying results in bronze) are skipped: the
-- model produces nothing for them by design.

WITH segs AS (
    SELECT
        race_year,
        race_id,
        SUM(stoppage_n) AS stoppage_total,
        MIN(segment_start_s) AS first_start_s
    FROM {{ ref('int_qualifying_segments') }}
    GROUP BY race_year, race_id
),

reds AS (
    SELECT
        s.race_year,
        s.race_id,
        COUNT(r.red_flag_id) AS red_flag_n
    FROM segs AS s
    LEFT JOIN {{ ref('stg_red_flags_qualifying') }} AS r
        ON
            s.race_year = r.race_year
            AND s.race_id = r.race_id
            AND r.session_time_s > s.first_start_s
    GROUP BY s.race_year, s.race_id
)

SELECT
    s.race_year,
    s.race_id,
    s.stoppage_total,
    r.red_flag_n
FROM segs AS s
INNER JOIN reds AS r
    ON s.race_year = r.race_year AND s.race_id = r.race_id
WHERE s.stoppage_total <> r.red_flag_n
