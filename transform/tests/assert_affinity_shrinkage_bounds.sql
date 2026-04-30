-- Driver circuit affinity model identity: Bayesian shrinkage bounds
--
-- Bayesian shrinkage with a proper prior is convex: the posterior mean must lie
-- strictly between (or equal to) the observed and prior means.
--
--   shrunk_affinity_s ∈ [min(raw_affinity_s, prior_mean_s),
--                         max(raw_affinity_s, prior_mean_s)]
--
-- Violation = the shrinkage formula is wrong or the prior/observed are mismatched.
-- Tolerance: floating-point epsilon (1e-9 s).
-- Gate: YES statistical bug if any rows returned.

SELECT
    driver_circuit_id,
    driver_id,
    circuit_key,
    raw_affinity_s,
    shrunk_affinity_s,
    _shrinkage_lower_bound,
    _shrinkage_upper_bound
FROM {{ ref('int_driver_circuit_affinity') }}
WHERE shrunk_affinity_s IS NOT NULL
  AND (
      shrunk_affinity_s < _shrinkage_lower_bound-1e-9
   OR shrunk_affinity_s > _shrinkage_upper_bound + 1e-9
  )
