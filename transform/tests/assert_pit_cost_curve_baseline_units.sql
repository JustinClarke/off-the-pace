-- baseline_delta_s_per_lap is seconds per lap and may only contain the
-- temperature term, 0.005 * (difference of two terms each clamped to [0, 30]),
-- so |value| <= 0.005 * 30 = 0.15. A unitless compound_grip_peak ratio
-- (0.95-1.09) added as seconds would breach this bound.
{{ config(severity='error') }}

SELECT
    baseline_cost_s,
    laps_on_new_set
FROM {{ ref('int_pit_strategy_cost_curve') }}
WHERE laps_on_new_set > 0
  AND ABS(baseline_cost_s) > 0.15 * laps_on_new_set + 1e-9
