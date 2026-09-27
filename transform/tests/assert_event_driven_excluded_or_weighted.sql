-- New (F51, WI-01). FD2 ruled exclude (not weight), and extended the rule to
-- the lap after a restart. Two things must hold on fct_cliff_prediction_features:
--
--   1. No anomaly_class = 'event_driven' row (SC/VSC/red-flag/restart lap/
--      pre-deployment/local-yellow, int_lap_anomaly_flags) is
--      is_training_eligible, mirroring the 'mistake'/'conditions' exclusions.
--   2. No lap after an SC or red-flag restart lap is is_training_eligible.
--      Re-derived here from int_event_corrections' raw SC/VSC/red flags
--      (two laps back SC or red, one lap back green), not read from the
--      is_lap_after_restart column, so a bug in that column's own logic still
--      fails this test. VSC restarts are out of FD2's scope (measured
--      unaffected). About 1,400 eligible rows were caught by this on the
--      2026-09-27 build.
--
-- If a future ruling switches this to the weighting option instead, this
-- test should be replaced with one asserting correction_weight is actually
-- read as an XGBoost sample weight in ml/src, not left both unexcluded and
-- unapplied.
{{ config(severity='error') }}

WITH flags AS (
    SELECT
        lap_id,
        LAG(is_safety_car_lap OR is_red_flag_lap, 2) OVER w AS two_back_sc_or_red,
        LAG(is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap, 1) OVER w AS one_back_controlled
    FROM {{ ref('int_event_corrections') }}
    WINDOW w AS (PARTITION BY race_year, race_id, driver_id ORDER BY lap_number)
)

SELECT
    f.lap_id,
    'event_driven row is training-eligible' AS failure
FROM {{ ref('fct_cliff_prediction_features') }} AS f
WHERE f.anomaly_class = 'event_driven'
  AND f.is_training_eligible

UNION ALL

SELECT
    f.lap_id,
    'lap after an SC/red-flag restart is training-eligible' AS failure
FROM {{ ref('fct_cliff_prediction_features') }} AS f
INNER JOIN flags AS fl ON f.lap_id = fl.lap_id
WHERE fl.two_back_sc_or_red
  AND NOT COALESCE(fl.one_back_controlled, FALSE)
  AND f.is_training_eligible
