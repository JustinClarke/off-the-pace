{{ config(tags=['intermediate'], severity='error') }}
-- Task 2A, guard on a HELD change. expected_degradation_rate_s_per_lap keeps its
-- baseline behaviour on a lap with no compound parameter cell: 0.0 (the gradient
-- COALESCEs to 0.0 and the cliff plateau is 0.0), NOT NULL. The NULL-for-unknown
-- change is held pending a retraining decision: the column is a cliff_prior
-- input to the ML models (ml/src/schema.py), so changing it moves training data.
-- compound_wear_s / expected_compound_pace_s are NULL on those laps (see
-- assert_compound_wear_missing_cell_is_null); the rate is deliberately not.
--
-- Returns rows only on failure, on laps with a known age (laps_past_cliff set):
--   a missing cell (NULL gradient) whose rate is not exactly 0.0
-- A lap with unknown age (laps_past_cliff NULL) keeps a NULL rate (F39).
-- If the NULL change is ever adopted, retire this test with that change and
-- retrain; do not let it flip silently.
SELECT
    lap_id,
    race_id,
    compound,
    laps_past_cliff,
    compound_wear_gradient,
    expected_degradation_rate_s_per_lap,
    CASE
        WHEN laps_past_cliff IS NULL THEN 'unknown_age_rate_not_null'
        ELSE 'missing_cell_rate_not_zero'
    END AS violation
FROM {{ ref('int_compound_cliff_predicted') }}
WHERE
    (
        laps_past_cliff IS NULL
        AND expected_degradation_rate_s_per_lap IS NOT NULL
    )
    OR (
        laps_past_cliff IS NOT NULL
        AND compound_wear_gradient IS NULL
        AND (
            expected_degradation_rate_s_per_lap IS NULL
            OR ABS(expected_degradation_rate_s_per_lap) > 1e-9
        )
    )
