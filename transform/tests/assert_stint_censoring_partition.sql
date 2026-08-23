-- Stint-life right-censoring: exactly one censored stint per driver-race.
--
-- is_censored_stint marks the driver's last stint of a race -- the one that
-- ended at the flag or at retirement rather than at a tyre change. Every driver
-- who ran a race has exactly one such stint: no more (two "last" stints is a
-- broken window partition) and no fewer (zero means the flag never fired and
-- every row would train as an uncensored observation).
--
-- This is the liveness assertion for the flag. The failure mode it exists to
-- catch is the silent one: a MAX() partitioned by the wrong key still returns
-- TRUE for something, and a model fitted against it would report a clean AFT
-- likelihood over the wrong population. A gate that cannot fail is not a gate.
--
-- Gate: YES any row returned means the censoring flag is not a partition.

SELECT
    race_id,
    driver_id,
    COUNT(*) AS stints,
    SUM(CASE WHEN is_censored_stint THEN 1 ELSE 0 END) AS censored_stints
FROM {{ ref('fct_stint_features') }}
GROUP BY race_id, driver_id
HAVING SUM(CASE WHEN is_censored_stint THEN 1 ELSE 0 END) <> 1
