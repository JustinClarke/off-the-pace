-- T23 (WI-13, F31). Every stint that ended in a stop has its stop: a stint whose
-- stint_end_cause is green_pit / sc_pit / vsc_pit / red carries actual_pit_lap
-- in int_pit_strategy_value.
--
-- The model used to look for the stop only up to the stint's last VALID lap
-- + 1. A stop taken after a run of SC/VSC/red-flag laps, or after any invalid
-- lap, sat outside that window, and the stint came out with actual_pit_lap
-- NULL -- which the model reads as "never stopped": verdict NULL and
-- opportunity cost 0.0, and the app's Gantt drew the bar to the chequered
-- flag. 418 stints on the 2026-09-24 dev build, 107 of the 116 red-flag-ended
-- and 194 of the 653 SC-ended among them. The stop is now matched inside the
-- stint's full span, up to int_stint_end_regime.end_lap_number.
--
-- Scope is the model's own population (stints with at least one valid lap).
-- Censored stints (race_end, retirement) are out of scope: they did not end in
-- a tyre change, and a NULL there is the right answer unless the driver retired
-- in the pit lane.

SELECT
    pv.stint_id,
    er.stint_end_cause,
    er.end_regime,
    er.end_lap_number,
    pv.actual_pit_lap,
    pv.strategy_verdict
FROM {{ ref('int_pit_strategy_value') }} AS pv
INNER JOIN {{ ref('int_stint_end_regime') }} AS er
    ON pv.stint_id = er.stint_id
WHERE
    er.stint_end_cause IN ('green_pit', 'sc_pit', 'vsc_pit', 'red')
    AND pv.actual_pit_lap IS NULL
