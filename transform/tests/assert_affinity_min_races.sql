-- Check that no driver is assigned an affinity if they have < 2 races at that circuit in that era
SELECT driver_id, circuit_id, era_key
FROM {{ ref('int_driver_circuit_era_affinity') }}
WHERE n_obs < 2 AND shrunk_affinity_s IS NOT NULL
