-- T50 (WI-17): the power-law fits are well formed.
--
-- int_stint_power_law_fit: one row per eligible stint (>= 8 laps over an age span >= 7 in
-- int_power_law_lap, with some spread in lap time), none for anything else flagged eligible;
-- beta on the grid [0.2, 3.0]; r2 in [0, 1]; and r2 >= r2_linear - 1e-9. The grid contains
-- beta = 1, so the profiled fit can never do worse than a straight line -- a row where it does
-- means the argmax or the linear lookup picked the wrong grid row.
-- int_cell_power_law_fit: one row per (race, rank); beta on the grid; r2_within in [0, 1].
-- Non-vacuous: both models must hold rows.

{% set tol = 1e-9 %}

WITH fit AS (
    SELECT * FROM {{ ref('int_stint_power_law_fit') }}
),

eligible_in_lap_set AS (
    SELECT stint_id
    FROM {{ ref('int_power_law_lap') }}
    GROUP BY stint_id
    HAVING
        COUNT(*) >= 8
        AND MAX(age_in_stint) - MIN(age_in_stint) >= 7
        AND VAR_POP(y_s) > 0
),

cells AS (
    SELECT * FROM {{ ref('int_cell_power_law_fit') }}
)

SELECT stint_id AS unit_id, 'duplicate stint row' AS failure
FROM fit
GROUP BY stint_id
HAVING COUNT(*) > 1

UNION ALL

SELECT e.stint_id, 'eligible stint has no fit_eligible row'
FROM eligible_in_lap_set AS e
LEFT JOIN fit AS f
    ON e.stint_id = f.stint_id
WHERE f.stint_id IS NULL OR NOT f.fit_eligible

UNION ALL

SELECT f.stint_id, 'row flagged fit_eligible for a stint that is not eligible'
FROM fit AS f
LEFT JOIN eligible_in_lap_set AS e
    ON f.stint_id = e.stint_id
WHERE f.fit_eligible AND e.stint_id IS NULL

UNION ALL

SELECT
    stint_id,
    CASE
        WHEN beta IS NULL OR beta < 0.2 - {{ tol }} OR beta > 3.0 + {{ tol }} THEN 'beta off the grid'
        WHEN r2 IS NULL OR r2 < -{{ tol }} OR r2 > 1 + {{ tol }} THEN 'r2 outside [0, 1]'
        WHEN r2_linear IS NULL THEN 'no straight-line R^2'
        WHEN r2 < r2_linear - {{ tol }} THEN 'power law fits worse than the straight line on its own grid'
        WHEN alpha_s IS NULL OR intercept_s IS NULL THEN 'NULL coefficient'
    END
FROM fit
WHERE
    beta IS NULL OR beta < 0.2 - {{ tol }} OR beta > 3.0 + {{ tol }}
    OR r2 IS NULL OR r2 < -{{ tol }} OR r2 > 1 + {{ tol }}
    OR r2_linear IS NULL OR r2 < r2_linear - {{ tol }}
    OR alpha_s IS NULL OR intercept_s IS NULL

UNION ALL

SELECT
    cell_id,
    CASE
        WHEN beta IS NULL OR beta < 0.2 - {{ tol }} OR beta > 3.0 + {{ tol }} THEN 'cell beta off the grid'
        ELSE 'cell r2_within outside [0, 1]'
    END
FROM cells
WHERE
    beta IS NULL OR beta < 0.2 - {{ tol }} OR beta > 3.0 + {{ tol }}
    OR r2_within IS NULL OR r2_within < -{{ tol }} OR r2_within > 1 + {{ tol }}

UNION ALL

SELECT 'none', 'int_stint_power_law_fit is empty'
WHERE NOT EXISTS (SELECT 1 FROM fit WHERE fit_eligible)

UNION ALL

SELECT 'none', 'int_cell_power_law_fit has no eligible cell'
WHERE NOT EXISTS (SELECT 1 FROM cells WHERE fit_eligible)
