-- COMPARISON DIAGNOSTIC, not a physical-model check. WARN only, non-blocking, no stored failures.
-- Comparison against int_lap_proximity, a different model. Disagreement is NOT evidence the physical model is
-- wrong. Last audit (2025 sample, 56 laps) found the physical model's named car correct on 55 of 56 and
-- proximity's correct on 8 of 56. Proximity ties resolve alphabetically by driver code.
--
-- Validation of the physical model is the separate sample-grain script
-- transform/scripts/check_physical_ahead_agreement.py (94% gate, read-only); this lap-grain proxy is not it.
-- The gate is SAMPLE grain against int_lap_proximity's per-bin car ahead (a CTE, not materialised).
-- 2026-11-09 script run: 162 of 170 rated races pass, 8 fail (listed in the script header).
--
-- This proxy: on valid_same_lap, non-neutralised laps where both models put the lap's minimum gap under 1 s, is
-- the car ahead at the minimum the same driver? The two minima can fall at different points of the lap behind
-- different cars in a train. Measured 2026-11-09 (scratch DB): pooled 92.3% (19,306 laps), race median 92.9%,
-- 5th percentile 84.6%, min 56.4%. Expected to warn on many races. Races with < 50 compared laps are skipped.
{{ config(severity='warn', store_failures=false) }}
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
