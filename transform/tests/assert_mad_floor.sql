-- MAD floor test: mad_floored_s must be >= 0.10s on every lap.
-- Ensures the scale estimator never collapses to zero (which would make
-- all laps appear anomalous by setting an infinitely tight threshold).
-- Any row returned is a test failure.
SELECT *
FROM {{ ref('int_lap_anomaly_flags') }}
WHERE mad_floored_s IS NOT NULL
  AND mad_floored_s < 0.10
