-- 02g/02c: the corner field median must be backward-only.
--
-- WHAT WENT WRONG, so the test is read as a guard on a real defect rather than a
-- formality. int_corner_skill_residuals used to compute FLOOR(lap/5)*5 AS lap_window and
-- GROUP BY it. That is a fixed BLOCK bucket, so a lap at block position 0 was scored
-- against a median drawn from itself and the next four laps. Measured over all 2,206,939
-- rows: mean forward reach 1.877 laps, 38.45% of the average median drawn from laps that
-- had not yet run, and at block position 0, 95.55% of rows scored against a baseline
-- holding a mean 3.351 of that driver's OWN future laps. DEGRADATION_TARGET is
-- next_5_lap_cumulative_jump_s (t+1..t+5) and maximum reach was 4 laps, so every
-- contaminating lap sat INSIDE the label's own window. 02g replaced it with
-- RANGE BETWEEN 5 PRECEDING AND 1 PRECEDING.
--
-- WHY audit_forward_window CANNOT SEE THIS. The reach lived entirely in the scope of a
-- GROUP BY key -- no LEAD, no FOLLOWING frame, no self-join inequality. The static guard
-- read the model as clean the whole time it was wrong (this is 08b's premise). So the
-- check has to be made against the DATA, which is what this test does.
--
-- THE CHECK. For each (race, corner, lap L), count how many corner rows exist in laps
-- L-5..L-1 by an explicit self-join inequality -- deliberately NOT the trailing_median
-- macro, so the test does not verify the window using the window it is testing. That count
-- is a hard UPPER BOUND on how many observations a backward-only median could possibly
-- have seen. A window that reaches forward, or that includes lap L itself, exceeds it.
--
-- Under the old block bucket this fails immediately and hard: lap 2 has zero backward
-- supply and the block gave it a full five-lap group (~70 rows).
--
-- Two independent assertions, both returned as failing rows:
--   forward_reach  -- field_corner_sample_n exceeds the backward-only row supply
--   lap_2_baseline -- lap 2 has no predecessor, so its count must be 0 and every
--                     residual on it must be NULL
--
-- field_corner_sample_n counts only non-NULL braking_point_m, while the supply below
-- counts every corner row, so the bound is loose by design. It is still sharp enough:
-- the failure mode it guards is a window reaching whole laps forward, not an off-by-one.

WITH rows_per_lap AS (
    SELECT
        race_year,
        race_id,
        corner_name,
        lap_number,
        COUNT(*) AS n_rows
    FROM {{ ref('int_corner_skill_residuals') }}
    GROUP BY race_year, race_id, corner_name, lap_number
),

-- Explicit inequality join, not a window frame: the point is to recompute the backward
-- supply by a different mechanism than the one under test.
backward_supply AS (
    SELECT
        focal.race_year,
        focal.race_id,
        focal.corner_name,
        focal.lap_number,
        COALESCE(SUM(prior.n_rows), 0) AS max_backward_rows
    FROM rows_per_lap AS focal
    LEFT JOIN rows_per_lap AS prior
        ON
            focal.race_year = prior.race_year
            AND focal.race_id = prior.race_id
            AND focal.corner_name = prior.corner_name
            AND prior.lap_number < focal.lap_number
            AND prior.lap_number >= focal.lap_number - 5
    GROUP BY focal.race_year, focal.race_id, focal.corner_name, focal.lap_number
)

SELECT
    'forward_reach' AS check_name,
    csr.corner_id,
    csr.lap_number,
    csr.field_corner_sample_n,
    bs.max_backward_rows,
    'field median saw more observations than laps t-5..t-1 could supply'
        AS issue
FROM {{ ref('int_corner_skill_residuals') }} AS csr
INNER JOIN backward_supply AS bs
    ON
        csr.race_year = bs.race_year
        AND csr.race_id = bs.race_id
        AND csr.corner_name = bs.corner_name
        AND csr.lap_number = bs.lap_number
WHERE csr.field_corner_sample_n > bs.max_backward_rows

UNION ALL

SELECT
    'lap_2_baseline' AS check_name,
    corner_id,
    lap_number,
    field_corner_sample_n,
    0 AS max_backward_rows,
    'lap 2 has no predecessor: count must be 0 and residuals NULL' AS issue
FROM {{ ref('int_corner_skill_residuals') }}
WHERE
    lap_number = 2
    AND (
        field_corner_sample_n != 0
        OR braking_loss_s IS NOT NULL
        OR mid_corner_residual_s IS NOT NULL
        OR exit_residual_s IS NOT NULL
    )
