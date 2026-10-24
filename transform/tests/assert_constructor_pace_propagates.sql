-- W19 / CO-23 (CD15 option C). The constructor structural pace signal must be
-- non-trivial: VAR_POP(constructor_structural_pace_s) in
-- int_constructor_structural_pace must be strictly greater than zero.
--
-- Replaces the baseline-dependent assert_constructor_pace_propagates removed in
-- e87f728, which only ran when the external snapshot
-- data/silver/_lap_residuals_baseline/ existed. This version needs no saved
-- file: it checks only that the constructor signal has spread (a constant or
-- all-NULL signal would mean the constructor term is not propagating).
--
-- Returns a row (FAILS) if the variance is zero, negative, or NULL (no rows).

WITH constructor_signal AS (
    SELECT VAR_POP(constructor_structural_pace_s) AS constructor_var
    FROM {{ ref('int_constructor_structural_pace') }}
    WHERE constructor_structural_pace_s IS NOT NULL
)

SELECT
    constructor_var,
    'constructor_structural_pace_s has no variance (signal not propagating)' AS failure_reason
FROM constructor_signal
WHERE constructor_var IS NULL
   OR constructor_var <= 0
