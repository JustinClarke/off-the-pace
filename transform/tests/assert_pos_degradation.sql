-- Fails if any stint has a confidence interval so wide (>5s) that the
-- degradation signal is statistically meaningless. A CI that broad
-- indicates data quality issues upstream rather than genuine tyre behaviour.
SELECT *
FROM {{ ref('fct_driver_degradation') }}
WHERE (confidence_interval_high-confidence_interval_low) > 5.0
  AND sample_size_laps >= 5
