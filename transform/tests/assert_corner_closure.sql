-- Corner skill decomposition model identity: corner-grain component closure.
-- The sum of three corner components (braking + mid-corner + exit) must equal
-- the total corner residual within 0.001 s.
-- Applies only to rows where all three components are non-NULL.
-- Returns rows that fail the identity check.

SELECT
    corner_id,
    braking_loss_s,
    mid_corner_residual_s,
    exit_residual_s,
    corner_residual_total_s,
    ABS(braking_loss_s + mid_corner_residual_s + exit_residual_s-corner_residual_total_s) AS diff_s
FROM {{ ref('int_corner_skill_residuals') }}
WHERE braking_loss_s IS NOT NULL
  AND mid_corner_residual_s IS NOT NULL
  AND exit_residual_s IS NOT NULL
  AND ABS(braking_loss_s + mid_corner_residual_s + exit_residual_s-corner_residual_total_s) > 0.001
