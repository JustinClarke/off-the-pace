-- end_of_stint_pace_falloff_s_per_lap must use the last 3 laps of each stint
-- THAT CARRY a driver_skill_residual_s. Independent of the model's window:
-- the selection is rebuilt by a self-join (a lap is selected when fewer than 3
-- residual-carrying laps of its stint come after it), then the slope is taken
-- with REGR_SLOPE, not the model's hand-rolled sums.
--
-- This checks the SELECTION rule, not only the arithmetic. Case it exists for:
-- a stint whose last 3 rows include a NULL residual must use the 3 non-NULL
-- laps ending before it, so the slope is NOT NULL when >= 3 residual laps
-- exist; the old rule (last 3 rows, then drop NULLs) left 2 laps and no slope.
-- A stint with fewer than 3 residual laps in total has a NULL slope.
-- Returns offending stints.
WITH resid_laps AS (
    SELECT
        sg.stint_id,
        sg.lap_in_stint,
        sg.valid_lap_in_stint AS x,
        lr.driver_skill_residual_s AS y
    FROM {{ ref('int_stint_geometry') }} AS sg
    INNER JOIN {{ ref('int_lap_residual_decomposed') }} AS lr
        ON sg.lap_id = lr.lap_id
    WHERE lr.driver_skill_residual_s IS NOT NULL
),

selected AS (
    SELECT a.stint_id, a.x, a.y
    FROM resid_laps AS a
    WHERE (
        SELECT COUNT(*)
        FROM resid_laps AS b
        WHERE b.stint_id = a.stint_id AND b.lap_in_stint > a.lap_in_stint
    ) < 3
),

expected AS (
    SELECT
        stint_id,
        COUNT(*) AS n_selected,
        CASE WHEN COUNT(*) < 3 THEN NULL ELSE REGR_SLOPE(y, x) END AS slope
    FROM selected
    GROUP BY stint_id
)

SELECT
    f.stint_id,
    f.end_of_stint_pace_falloff_s_per_lap,
    e.n_selected,
    e.slope
FROM {{ ref('fct_stint_features') }} AS f
LEFT JOIN expected AS e ON f.stint_id = e.stint_id
WHERE
    (f.end_of_stint_pace_falloff_s_per_lap IS NULL) != (e.slope IS NULL)
    OR ABS(f.end_of_stint_pace_falloff_s_per_lap - e.slope) > 1e-9
