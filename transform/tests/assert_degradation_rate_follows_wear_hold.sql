{{ config(tags=['intermediate'], severity='error') }}
-- CO-15 (ruling CD9), found by the CO-17 audit. expected_degradation_rate_s_per_lap
-- is documented as the slope of the wear curve (compound_wear_s). The wear hold
-- flattens the linear term past onset + compound_wear_hold_after_onset_laps, so
-- the rate there must not keep charging the wear gradient. Before the fix, laps
-- at or past the hold carried rate = gradient on a flat curve (26,382 rows on
-- the CO-17 build; 23,973 strictly past it, mean 0.11 s/lap).
--
-- Two checks, one row per failing lap:
--   held_lap_charges_wear -- past the hold, the rate is only the ramp's slope,
--     which is 0 once laps_past_cliff >= the ramp span (2.5 < 5 laps).
--   pre_hold_rate_wrong   -- before the onset the rate is the wear gradient.
SELECT
    lap_id,
    race_id,
    age_in_stint,
    compound_cliff_onset_laps,
    laps_past_cliff,
    compound_wear_gradient,
    expected_degradation_rate_s_per_lap,
    CASE
        WHEN laps_past_cliff >= {{ var('compound_wear_hold_after_onset_laps') }}
            THEN 'held_lap_charges_wear'
        ELSE 'pre_hold_rate_wrong'
    END AS check_name
FROM {{ ref('int_compound_cliff_predicted') }}
WHERE
    laps_past_cliff IS NOT NULL
    AND (
        (
            laps_past_cliff >= {{ var('compound_wear_hold_after_onset_laps') }}
            AND laps_past_cliff >= {{ var('cliff_ramp_span_laps') }}
            AND ABS(expected_degradation_rate_s_per_lap) > 1e-9
        )
        OR (
            laps_past_cliff = 0
            AND ABS(
                expected_degradation_rate_s_per_lap
                - COALESCE(compound_wear_gradient, 0.0)
            ) > 1e-9
        )
    )
