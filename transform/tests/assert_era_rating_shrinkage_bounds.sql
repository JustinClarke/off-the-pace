-- Era-normalised driver rating model identity: Bayesian shrinkage bounds for era-normalized ratings
--
-- The per-(driver, season) shrinkage must satisfy convexity:
--   shrunk_residual_s ∈ [min(raw_residual_mean_s, season_mean_s),
--                         max(raw_residual_mean_s, season_mean_s)]
--
-- Violation = the shrinkage formula is wrong or the prior/observed are mismatched.
-- Tolerance: floating-point epsilon (1e-9 s).
-- Gate: YES statistical bug if any rows returned.

SELECT
    driver_season_id,
    driver_id,
    season,
    raw_residual_mean_s,
    shrunk_residual_s,
    _shrinkage_lower_bound,
    _shrinkage_upper_bound
FROM {{ ref('int_driver_season_ratings') }}
WHERE shrunk_residual_s IS NOT NULL
  AND (
      shrunk_residual_s < _shrinkage_lower_bound-1e-9
   OR shrunk_residual_s > _shrinkage_upper_bound + 1e-9
  )
