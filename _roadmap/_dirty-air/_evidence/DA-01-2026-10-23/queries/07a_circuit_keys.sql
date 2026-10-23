-- OUT: 07a_circuit_keys
-- Circuit key per race (stg_laps.circuit_key) for the MultiViewer circuit API probe.
SELECT race_year, race_id, MIN(circuit_key) AS circuit_key, COUNT(DISTINCT circuit_key) AS n_keys
FROM dev.main.stg_laps GROUP BY 1, 2 ORDER BY 1, CAST(SPLIT_PART(race_id, '_', 2) AS INTEGER)
