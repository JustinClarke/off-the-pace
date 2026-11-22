-- A lap whose base_pace_status is not MEASURED has no field base pace, so its
-- driver_skill_residual_s (the label source) is NULL and it must never enter an
-- ML training population. fct_cliff_prediction_features.is_training_eligible is the
-- flag ml/src/features.py reads (WHERE is_training_eligible); base_pace_status is
-- not in that mart's enforced final SELECT, so it is read from
-- int_lap_residual_decomposed on lap_id. A cliff-mart lap with no residual row has
-- no status and is not MEASURED either. Returns offending rows; passes when empty.
SELECT
    f.lap_id,
    d.base_pace_status,
    f.is_training_eligible
FROM {{ ref('fct_cliff_prediction_features') }} AS f
LEFT JOIN {{ ref('int_lap_residual_decomposed') }} AS d ON f.lap_id = d.lap_id
WHERE
    f.is_training_eligible
    AND d.base_pace_status IS DISTINCT FROM 'MEASURED'
