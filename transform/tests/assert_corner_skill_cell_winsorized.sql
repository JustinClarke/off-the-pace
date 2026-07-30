-- Each (driver, race, corner) cell is winsorized to +/-1.0s before season
-- aggregation, so a lap-weighted season mean (a convex combination of
-- winsorized cells) can never exceed that bound either. A breach means the
-- winsorization -- the guard against a single thin/outlier cell (e.g. a
-- corner with only n=3 laps) dominating a whole season -- has been lost.
SELECT race_year, driver_id, braking_skill_s, mid_corner_skill_s, exit_skill_s
FROM {{ ref('mart_corner_skill_driver') }}
WHERE
    ABS(braking_skill_s) > 1.0
    OR ABS(mid_corner_skill_s) > 1.0
    OR ABS(exit_skill_s) > 1.0
