-- int_lap_physical_ahead vs int_lap_proximity (production crossing-time model), per race, LAP-GRAIN PROXY.
-- WARN only. This is NOT the 94% validation gate.
--
-- The gate ("agreement on valid same-lap samples >= 94% per race") is SAMPLE grain against
-- int_lap_proximity's per-bin car ahead, which is a CTE and is not materialised, so it cannot run as a dbt
-- test on existing tables. It is the documented check transform/scripts/check_physical_ahead_agreement.py
-- (read-only). 2026-11-09 run: 162 of 170 rated races pass, 8 fail (listed in the script header).
--
-- What this proxy compares: on valid_same_lap, non-neutralised laps where both models put the lap's minimum
-- gap under 1 s, is the car ahead at the minimum the same driver? That is a different statistic: the two
-- minima can fall at different points of the lap behind different cars in a train. Measured 2026-11-09 on
-- the full build (scratch DB): pooled 92.3% (19,306 laps), race median 92.9%, 5th percentile 84.6%,
-- min 56.4%. It is kept as a regression guard against gross drift, with the gate's 94% threshold, and is
-- expected to warn on many races. Races with < 50 compared laps are skipped.
{{ config(severity='warn') }}
WITH cmp AS (
    SELECT
        p.race_id,
        CASE WHEN p.gap_ahead_phys_min_driver_id = x.gap_ahead_min_driver_id THEN 1.0 ELSE 0.0 END AS agree
    FROM {{ ref('int_lap_physical_ahead') }} AS p
    INNER JOIN {{ ref('int_lap_proximity') }} AS x
        ON p.lap_id = x.lap_id
    WHERE
        p.validity_class = 'valid_same_lap'
        AND NOT p.is_neutralised_lap
        AND p.gap_ahead_phys_s < 1.0
        AND x.gap_ahead_min_s < 1.0
)
SELECT race_id, COUNT(*) AS n_laps, AVG(agree) AS agreement
FROM cmp
GROUP BY race_id
HAVING COUNT(*) >= 50 AND AVG(agree) < 0.94
