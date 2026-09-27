-- T45 (WI-16a): every Ω lap has exactly one stint phase, and the phase follows its rule.
--
-- int_driver_isolation_lap_panel assigns the tyre phase from the seed's cliff onset
-- (exogenous to the residual) and overlays recovery:
--   tyre_phase   cliff iff laps_past_cliff > 0; otherwise early iff valid_lap_in_stint <= 5,
--                mid iff >= 6
--   stint_phase  'recovery' iff is_recovery, else tyre_phase
-- so stint_phase = 'cliff' iff laps_past_cliff > 0 and the lap is not on the recovery
-- overlay. Every row must carry a phase from the four allowed values. One row per failing
-- lap. (The WI doc's recovery-share band, [1%, 10%] of Ω, is a separate warn-severity
-- test: assert_isolation_recovery_share.)

SELECT
    lap_id,
    tyre_phase,
    stint_phase,
    is_recovery,
    laps_past_cliff,
    valid_lap_in_stint
FROM {{ ref('int_driver_isolation_lap_panel') }}
WHERE
    stint_phase IS NULL
    OR tyre_phase IS NULL
    OR is_recovery IS NULL
    OR stint_phase NOT IN ('early', 'mid', 'cliff', 'recovery')
    OR (stint_phase = 'recovery') != is_recovery
    OR (NOT is_recovery AND stint_phase != tyre_phase)
    OR (tyre_phase = 'cliff') != (laps_past_cliff > 0)
    OR (tyre_phase = 'early') != (laps_past_cliff = 0 AND valid_lap_in_stint <= 5)
    OR (tyre_phase = 'mid') != (laps_past_cliff = 0 AND valid_lap_in_stint >= 6)
    OR (stint_phase = 'cliff') != (laps_past_cliff > 0 AND NOT is_recovery)
