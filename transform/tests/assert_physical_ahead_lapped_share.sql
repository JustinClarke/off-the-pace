-- int_lap_physical_ahead: lapped share of known samples above 30% in a race. Guards the Singapore 2019
-- defect (exp 26: X = Y = 0 placeholder samples shift progress by a lap, 35.4% lapped; healthy races
-- 2.7-23.9%). WARN: with the unvalidated zero-XY guard off (the default) Singapore 2019 is expected to trip
-- it. Its laps fall into validity_class 'lapped', which no exposure figure counts.
{{ config(severity='warn') }}
SELECT
    race_id,
    SUM(n_lapped_samples)::DOUBLE / NULLIF(SUM(n_samples - n_unknown_samples), 0) AS lapped_share
FROM {{ ref('int_lap_physical_ahead') }}
GROUP BY race_id
HAVING SUM(n_lapped_samples)::DOUBLE / NULLIF(SUM(n_samples - n_unknown_samples), 0) > 0.30
