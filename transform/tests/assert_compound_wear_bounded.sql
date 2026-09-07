-- The compound wear curve must respect var('compound_wear_max_s_per_lap').
--
-- This is the bound's own test, and it exists because the bound has two
-- independent applications of the same three terms: the source curve in
-- int_compound_cliff_predicted (per observed lap) and the recomputation
-- in int_pit_strategy_cost_curve (over a synthetic age grid). Between
-- Phase 5 and Phase 8 only the second was capped, and nothing failed --
-- the source curve kept emitting up to 93.5 s/lap into
-- driver_skill_residual_s, and from there into both ML targets.
--
-- Asserted on compound_wear_s rather than on expected_compound_pace_s, because
-- the pace total legitimately exceeds the bound by grip_peak plus the
-- temperature offset, which are per-lap constants and are not what runs away.
--
-- A tolerance of 1e-9 absorbs float accumulation in POWER(); the failure this
-- guards against is the tail returning, which is a 20-80 s violation, not a
-- 1e-12 one.
SELECT
    lap_id,
    compound,
    age_in_stint,
    compound_wear_s
FROM {{ ref('int_compound_cliff_predicted') }}
WHERE
    compound_wear_s
    > {{ var('compound_wear_max_s_per_lap', 10.0) }} + 1e-9
