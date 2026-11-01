{{ config(severity='error', tags=['simulation', 'strategy']) }}
-- Every stint with a stop and a model optimum is graded: overrun_laps is set,
-- and the verdict is read off it. The actual offset has to fall back to the
-- race-remainder horizon together with the optimum; when only the optimum fell
-- back, the 265 race-remainder stints with a stop had overrun_laps NULL and a
-- verdict that skipped 'optimal' / 'overran' (2026-10-31 dev build: 32
-- undercut_forced and 233 early that were 217 optimal and 48 overran).
-- Also fails a graded stint whose overrun is not the valid-lap count minus the
-- optimum, the one definition both horizons share.
SELECT
    stint_id,
    horizon_source,
    actual_pit_lap,
    optimal_pit_lap_in_stint,
    stint_length_laps,
    overrun_laps,
    strategy_verdict
FROM {{ ref('int_pit_strategy_value') }}
WHERE
    actual_pit_lap IS NOT NULL
    AND optimal_pit_lap_in_stint IS NOT NULL
    AND (
        overrun_laps IS NULL
        OR overrun_laps != stint_length_laps - optimal_pit_lap_in_stint
        OR strategy_verdict IS NULL
        OR strategy_verdict = 'unknown'
    )
