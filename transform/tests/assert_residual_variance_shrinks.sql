-- W19 / CO-23 (CD15 option C). The constructor component must reduce residual
-- variance, checked inside the build with no saved baseline.
--
-- Replaces the baseline-dependent assert_residual_variance_shrinks removed in
-- e87f728 (which compared against data/silver/_lap_residuals_baseline/).
-- fct_lap_residuals carries the identity
--   pace_delta_s = fuel + compound + constructor + dirty_air + driver_skill_residual_s
-- so the residual with the constructor term removed is
--   driver_skill_residual_s + constructor_component_s
-- (the same laps, constructor left unexplained). The ratio
--   VAR_POP(driver_skill_residual_s) / VAR_POP(driver_skill_residual_s + constructor_component_s)
-- is the share of variance left after the constructor term is applied.
--
-- The old [0.85, 0.99] band does not carry over: it bounded residual variance
-- against an older snapshot, not against the same laps without the constructor
-- term. This check uses two bounds that each come from what the term is:
--
--   Upper: ratio must be below 0.95 (the term removes at least 5%). A zero term
--   gives exactly 1.0; a sign-flipped term 1.93; a term joined to the wrong team
--   or shuffled across laps about 1.33; all fail. 0.95 is about where the term
--   has lost four-fifths of its current effect (zeroing it in 80% of races gives
--   0.94), and is above the worst single season (2023, 0.87).
--
--   Lower: ratio must not go below the floor, the ratio left after subtracting
--   each (race, constructor) group's own mean. The term is one constant per
--   (race, constructor), and no such constant can remove more variance than the
--   group mean, so a ratio under the floor means the term varies within a team's
--   race (a fan-out join, or a per-lap value leaking the lap's own pace). The
--   small tolerance covers floating-point error only.
--
-- Measured on the 2026-10-24 build: 148,622 laps, ratio 0.720 (residual variance
-- 1.320 against 1.834 without the constructor term, so the term removes 28%);
-- floor 0.641, so the term gets about 78% of the reduction a per-team-race
-- constant could reach. It is fitted on dry, full-weight laps only, so it is not
-- expected to reach the floor.
--
-- Returns rows (i.e. FAILS) if the ratio is NULL, at or above 0.95, or below
-- the floor.

WITH laps AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        driver_skill_residual_s,
        driver_skill_residual_s + constructor_component_s AS residual_without_constructor_s
    FROM {{ ref('fct_lap_residuals') }}
    WHERE driver_skill_residual_s IS NOT NULL
      AND constructor_component_s IS NOT NULL
),

group_demeaned AS (
    SELECT
        residual_without_constructor_s
            - AVG(residual_without_constructor_s) OVER (
                PARTITION BY race_year, race_id, constructor_id
            ) AS within_group_s
    FROM laps
),

ratio AS (
    SELECT
        VAR_POP(l.driver_skill_residual_s) AS current_variance,
        VAR_POP(l.residual_without_constructor_s) AS variance_without_constructor,
        VAR_POP(l.driver_skill_residual_s)
            / NULLIF(VAR_POP(l.residual_without_constructor_s), 0) AS variance_ratio,
        (SELECT VAR_POP(within_group_s) FROM group_demeaned)
            / NULLIF(VAR_POP(l.residual_without_constructor_s), 0) AS variance_ratio_floor
    FROM laps AS l
)

SELECT
    variance_ratio,
    variance_ratio_floor,
    variance_without_constructor,
    current_variance,
    CASE
        WHEN variance_ratio IS NULL THEN 'variance_ratio is NULL (no laps)'
        WHEN variance_ratio >= 0.95
            THEN 'constructor term removes under 5% of residual variance'
        ELSE 'variance_ratio below the per-(race, constructor) floor: term is not one constant per team-race'
    END AS failure_reason
FROM ratio
WHERE variance_ratio IS NULL
   OR variance_ratio >= 0.95
   OR variance_ratio < variance_ratio_floor - 1e-9
