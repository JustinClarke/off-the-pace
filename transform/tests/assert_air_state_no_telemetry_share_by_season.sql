-- T15 (F12 guard). 2018's elevated share of rows with no car telemetry -- verify_findings.py's
-- F12 check measures it as `gap_ahead_min_s IS NULL`, an excess of 9.18 percentage points
-- vs. every later season on the 2026-09-25 dev build (2018: 9.18%; every other season:
-- <= 0.04%) -- is a KNOWN, not-yet-fixed defect: int_lap_air_state.sql's `with_stint` CTE
-- (`COALESCE(a.air_state_dominant, 'free_air')`, `COALESCE(a.dirty_air_share_lap, 0.0)`) and
-- int_lap_proximity.sql's exposure-share columns (`COALESCE(share_lap_within_1s, 0.0)` and
-- siblings, lines ~404-427) both fabricate a real-looking value when the underlying
-- telemetry-derived row is simply missing, rather than leaving it NULL the way
-- `gap_ahead_min_s` itself does. Fixing the fabrication is deferred to WI-01/WI-15a
-- pending a ruling on what "cleared" means for F12 (open decision FD6); this is the guard
-- against it getting WORSE or spreading in the meantime, not the fix.
--
-- Per-season, not pooled: a table-wide null-rate check (the data-profile drift baseline)
-- dilutes a one-season spike across every season's rows and can miss a regression the
-- size of 2018's own. Two things must hold:
--   1. 2018 itself must not regress past a generous ceiling -- a re-ingestion of 2018
--      should not quietly make an already-known problem worse without anyone noticing;
--   2. no OTHER season may develop anything close to 2018's share -- if a future season's
--      telemetry coverage degrades this way, that is a NEW occurrence and must be caught,
--      not silently absorbed as "2018 is already like this".
--
-- Warn severity: this guards a known, deliberately-deferred defect; it must not block a
-- build over the very condition it exists to keep an eye on.
{{ config(severity='warn', tags=['data_quality']) }}

WITH per_season AS (
    SELECT
        race_year,
        AVG(CASE WHEN gap_ahead_min_s IS NULL THEN 1.0 ELSE 0.0 END) AS no_telemetry_share
    FROM {{ ref('fct_cliff_prediction_features') }}
    WHERE is_training_eligible
    GROUP BY race_year
)

SELECT
    race_year,
    no_telemetry_share
FROM per_season
WHERE
    (race_year = 2018 AND no_telemetry_share > 0.15)
    OR (race_year != 2018 AND no_telemetry_share > 0.02)
