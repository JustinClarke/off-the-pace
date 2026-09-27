-- T45, second half (WI-16a): the recovery overlay is a thin stratum, not a dead or a
-- runaway one.
--
-- The share of Ω laps on the recovery overlay must sit in [1%, 10%]. Below 1% the overlay
-- has stopped firing (for example the air-state coding it reads changed its labels); above
-- 10% it is no longer "the first laps after dropping out of a wake". Measured 5.0% on the
-- 2026-09-26 build (WI-15a's S2 coding raised it from the WI doc's pre-WI-15a 3.1% of
-- valid laps). Warn severity, as the WI doc specifies: the band is a sanity range, not an
-- identity, and it is split out of assert_isolation_phase_partition so that the partition
-- itself can stay an error.

{{ config(severity='warn') }}

SELECT
    COUNT(*) AS omega_laps,
    AVG(CASE WHEN is_recovery THEN 1.0 ELSE 0.0 END) AS recovery_share
FROM {{ ref('int_driver_isolation_lap_panel') }}
HAVING
    AVG(CASE WHEN is_recovery THEN 1.0 ELSE 0.0 END) < 0.01
    OR AVG(CASE WHEN is_recovery THEN 1.0 ELSE 0.0 END) > 0.10
