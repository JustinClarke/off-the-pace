-- T32 (F42a, WI-01). expected_compound_pace_s must equal
-- compound_wear_s + 0.005 * ambient_temp_delta exactly (to float precision):
-- no third, unitless constant added as if it were seconds.
--
-- Before this fix, int_compound_cliff_predicted added
-- COALESCE(compound_grip_peak, 0.0) into the pace sum. compound_grip_peak is
-- a unitless 0.95-1.09 ratio (dim_compounds_season), not a seconds offset;
-- F42a dropped it from the sum (0.0 pending a properly-fitted per-compound
-- offset in seconds).
--
-- The other half of the original T32 spec -- "the temperature term is
-- non-zero on > 5% of slick laps with a cell, or is removed" -- is F42b, a
-- separate finding not in WI-01's scope (the temperature term's own scale
-- mismatch against the tyre window is untouched here) and is not asserted by
-- this test.
--
-- int_pit_strategy_cost_curve already excludes compound_grip_peak from
-- baseline_delta_s_per_lap (temperature term only); that model's dead
-- grip_peak column was removed. assert_pit_cost_curve_baseline_units covers it.
{{ config(severity='error') }}

SELECT
    lap_id,
    expected_compound_pace_s,
    compound_wear_s,
    ambient_temp_delta
FROM {{ ref('int_compound_cliff_predicted') }}
WHERE expected_compound_pace_s IS NOT NULL
  AND ABS(expected_compound_pace_s - compound_wear_s - 0.005 * ambient_temp_delta) > 1e-9
