-- Driver circuit/era affinity: credible interval must bracket the posterior mean
--
-- A 95% credible interval is constructed symmetrically around the posterior mean
-- (shrunk_affinity_s ± 1.96 · se), so by construction:
--
--   shrunk_affinity_ci_low_s <= shrunk_affinity_s <= shrunk_affinity_ci_high_s
--
-- A row that violates this means the CI bounds and the mean were computed from
-- mismatched intermediates (e.g. a wrong se, or low/high swapped). Only checked
-- where the SE is estimable (multi-observation cells); degenerate single-obs
-- cells carry NULL CI bounds by design and are excluded.
-- Tolerance: floating-point epsilon (1e-9 s).
-- Gate: YES statistical bug if any rows returned.

WITH affinity AS (
    SELECT
        driver_circuit_id AS affinity_id,
        shrunk_affinity_s,
        shrunk_affinity_ci_low_s,
        shrunk_affinity_ci_high_s
    FROM {{ ref('int_driver_circuit_affinity') }}

    UNION ALL

    SELECT
        driver_circuit_era_id AS affinity_id,
        shrunk_affinity_s,
        shrunk_affinity_ci_low_s,
        shrunk_affinity_ci_high_s
    FROM {{ ref('int_driver_circuit_era_affinity') }}
)

SELECT
    affinity_id,
    shrunk_affinity_s,
    shrunk_affinity_ci_low_s,
    shrunk_affinity_ci_high_s
FROM affinity
WHERE shrunk_affinity_ci_low_s IS NOT NULL
    AND (
        shrunk_affinity_s < shrunk_affinity_ci_low_s - 1e-9
        OR shrunk_affinity_s > shrunk_affinity_ci_high_s + 1e-9
    )
