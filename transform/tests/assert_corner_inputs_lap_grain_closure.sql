-- 02c: int_lap_corner_inputs must be a faithful roll-up of int_corner_skill_residuals.
--
-- WHAT THIS CATCHES, and it is not hypothetical. 02g replaced the FLOOR(lap/5)*5 block
-- bucket in int_corner_skill_residuals' field_medians CTE with window functions, but the
-- block bucket had been collapsing that CTE with a GROUP BY and the windows do not: they
-- return one row per input row, and corners_with_keys is at DRIVER grain. The LEFT JOIN
-- back onto (race_year, race_id, corner_name, lap_number) then fanned the model out by
-- the field size -- 2,206,939 rows became 38,444,069 (17.4x) -- with every duplicate
-- carrying identical values, so no aggregate MEAN or MEDIAN moved and nothing looked
-- wrong. What did move were the COUNTs: mart_corner_skill_driver's HAVING COUNT(*) >= 100
-- admission floor and its PHASE_MIN_CELLS=30 gate were both being cleared ~17x too
-- easily, and its LORO baseline silently became field-size-weighted.
--
-- The `unique` test on corner_id is the direct guard on that model and is the one that
-- should fail first. This test is the second line: it ties the lap-grain aggregate back to
-- the corner grain it claims to summarise, so a fan-out that somehow survived upstream
-- cannot reach the feature contract silently. It is a real check on THIS model too --
-- corners_total_n and the per-phase counts are what corner_input_coverage is built from,
-- and a wrong denominator there is a wrong feature, not just a wrong diagnostic.
--
-- Returns rows where the lap-grain counts disagree with a fresh count over the corner
-- grain, in either direction.

WITH corner_grain AS (
    SELECT
        lap_id,
        COUNT(*) AS expect_total_n,
        COUNT(*) FILTER (WHERE NOT corner_unmapped_flag) AS expect_mapped_n,
        COUNT(braking_loss_s) AS expect_braking_n,
        COUNT(mid_corner_residual_s) AS expect_mid_n,
        COUNT(exit_residual_s) AS expect_exit_n
    FROM {{ ref('int_corner_skill_residuals') }}
    GROUP BY lap_id
)

SELECT
    li.lap_id,
    li.corners_total_n,
    cg.expect_total_n,
    li.corners_mapped_n,
    cg.expect_mapped_n,
    li.corner_braking_n,
    cg.expect_braking_n,
    li.corner_mid_n,
    cg.expect_mid_n,
    li.corner_exit_n,
    cg.expect_exit_n
FROM {{ ref('int_lap_corner_inputs') }} AS li
FULL OUTER JOIN corner_grain AS cg ON li.lap_id = cg.lap_id
WHERE
    li.lap_id IS NULL
    OR cg.lap_id IS NULL
    OR li.corners_total_n != cg.expect_total_n
    OR li.corners_mapped_n != cg.expect_mapped_n
    OR li.corner_braking_n != cg.expect_braking_n
    OR li.corner_mid_n != cg.expect_mid_n
    OR li.corner_exit_n != cg.expect_exit_n
