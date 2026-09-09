-- No-future-leakage test for the thermal proxy: the BASELINE first, then the EW
-- cumulative loads built on it.
--
-- This file used to check only the two EWMAs, and its own comment called that
-- "the definitive future-leakage guard". It was not. It re-derived the loads over
-- push_residual with backward LAGs and never asked where push_residual came from,
-- so it passed for the whole life of a baseline that pooled laps the scored lap
-- had not yet run (08e). A window validated over a contaminated input is not a
-- guard. The baseline check below is what closes that: it re-derives the baseline
-- by SELF-JOIN on strictly-prior laps -- deliberately NOT with the trailing_median
-- macro the model uses, so the test is an independent construction rather than a
-- restatement of the model's own window.
--
-- Note: int_lap_air_state leakage is validated by assert_stint_boundary_integrity
-- (ratio identity at the stint's first scored lap). The lap-2 max-bound check was
-- removed because dirty_air_intensity = 1/GREATEST(gap_s, 0.3) can reach 3.33,
-- making the 0.840 bound incorrect.

WITH lap_source AS (
    SELECT
        g.stint_id,
        g.lap_id,
        g.lap_in_stint,
        g.is_valid_lap,
        t.lap_time_s
    FROM {{ ref('int_stint_geometry') }} AS g
    INNER JOIN {{ ref('int_lap_thermal_proxy') }} AS t ON t.lap_id = g.lap_id
),

-- Strictly-prior is the join predicate (lap_in_stint <), not a window frame.
-- FILTER in a plain GROUP BY, which is legal where FILTER in an ordered-set
-- aggregate inside a window function is not -- a second axis of independence.
prior_agg AS (
    SELECT
        cur.lap_id,
        MEDIAN(prv.lap_time_s) FILTER (WHERE prv.is_valid_lap) AS expected_baseline,
        COUNT(prv.lap_time_s) FILTER (WHERE prv.is_valid_lap)  AS expected_n_prior
    FROM lap_source AS cur
    LEFT JOIN lap_source AS prv
        ON prv.stint_id = cur.stint_id
       AND prv.lap_in_stint < cur.lap_in_stint
    GROUP BY cur.lap_id
)

-- baseline check: the stint baseline must equal the median of this stint's valid
-- laps STRICTLY BEFORE the scored lap. This is the check whose absence let 08e run.
SELECT
    t.lap_id,
    'stint_baseline_pace' AS check_name,
    p.expected_baseline AS expected,
    t.stint_baseline_pace AS actual
FROM {{ ref('int_lap_thermal_proxy') }} AS t
INNER JOIN prior_agg AS p ON p.lap_id = t.lap_id
WHERE t.stint_baseline_pace IS DISTINCT FROM p.expected_baseline
  AND (
      t.stint_baseline_pace IS NULL
      OR p.expected_baseline IS NULL
      OR ABS(t.stint_baseline_pace - p.expected_baseline) > 0.000001
  )

UNION ALL

-- floor check: the baseline is NULL exactly where no valid prior lap exists, and
-- baseline_observations_n reports that count honestly. The NULLs are deterministic
-- on this column and on nothing else in the contract, which is why it ships.
SELECT
    t.lap_id,
    'baseline_observations_n' AS check_name,
    CAST(p.expected_n_prior AS DOUBLE) AS expected,
    CAST(t.baseline_observations_n AS DOUBLE) AS actual
FROM {{ ref('int_lap_thermal_proxy') }} AS t
INNER JOIN prior_agg AS p ON p.lap_id = t.lap_id
WHERE t.baseline_observations_n IS DISTINCT FROM p.expected_n_prior
   OR (t.stint_baseline_pace IS NULL) <> (p.expected_n_prior = 0)

UNION ALL

-- residual identity: push_residual carries the baseline's NULLs, it does not
-- silently become 0 where the baseline is unknown.
SELECT
    lap_id,
    'push_residual' AS check_name,
    stint_baseline_pace - lap_time_s AS expected,
    push_residual AS actual
FROM {{ ref('int_lap_thermal_proxy') }}
WHERE push_residual IS DISTINCT FROM stint_baseline_pace - lap_time_s

UNION ALL

-- surface check: re-derive using 4-lap lookback (α=0.6 → weights 0.717, 0.514, 0.369, 0.264)
SELECT
    lap_id,
    'push_surface' AS check_name,
    CASE WHEN push_residual IS NOT NULL THEN ROUND(
        GREATEST(push_residual, 0)
        + 0.717 * GREATEST(COALESCE(LAG(push_residual, 1) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.514 * GREATEST(COALESCE(LAG(push_residual, 2) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.369 * GREATEST(COALESCE(LAG(push_residual, 3) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.264 * GREATEST(COALESCE(LAG(push_residual, 4) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0),
    4) END AS expected,
    cumulative_push_load_surface AS actual
FROM {{ ref('int_lap_thermal_proxy') }}
QUALIFY cumulative_push_load_surface IS DISTINCT FROM expected
   AND (
       cumulative_push_load_surface IS NULL OR expected IS NULL
       OR ABS(cumulative_push_load_surface-expected) > 0.0001
   )

UNION ALL

-- bulk check: re-derive using 7-lap lookback (α=0.25 → weights decay as 0.25^k)
SELECT
    lap_id,
    'push_bulk' AS check_name,
    CASE WHEN push_residual IS NOT NULL THEN ROUND(
        GREATEST(push_residual, 0)
        + 0.819 * GREATEST(COALESCE(LAG(push_residual, 1) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.670 * GREATEST(COALESCE(LAG(push_residual, 2) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.549 * GREATEST(COALESCE(LAG(push_residual, 3) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.449 * GREATEST(COALESCE(LAG(push_residual, 4) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.368 * GREATEST(COALESCE(LAG(push_residual, 5) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.301 * GREATEST(COALESCE(LAG(push_residual, 6) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0)
        + 0.247 * GREATEST(COALESCE(LAG(push_residual, 7) OVER (PARTITION BY stint_id ORDER BY lap_in_stint ROWS BETWEEN 7 PRECEDING AND CURRENT ROW), 0), 0),
    4) END AS expected,
    cumulative_push_load_bulk AS actual
FROM {{ ref('int_lap_thermal_proxy') }}
QUALIFY cumulative_push_load_bulk IS DISTINCT FROM expected
   AND (
       cumulative_push_load_bulk IS NULL OR expected IS NULL
       OR ABS(cumulative_push_load_bulk-expected) > 0.0001
   )
