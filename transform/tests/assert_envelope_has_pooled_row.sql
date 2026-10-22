-- The Degradation Simulator falls back to the compound = '_all' pooled curve
-- (app/src/features/degradation-simulator/queries.ts), so every (circuit_id, era)
-- cell in mart_degradation_history_envelope must carry one. Returns one row per
-- cell lacking it; the compound relationships test deliberately skips '_all'.
SELECT
    circuit_id,
    era
FROM {{ ref('mart_degradation_history_envelope') }}
GROUP BY circuit_id, era
HAVING COUNT(*) FILTER (WHERE compound = '_all') = 0
