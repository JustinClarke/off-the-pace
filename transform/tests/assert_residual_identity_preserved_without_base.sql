-- The five-term identity, to 1e-6 s (the older assert_residual_decomposition_identity
-- allows 1e-4): wherever every term is non-NULL,
--   pace_delta_s = fuel + compound + constructor + dirty_air_tax + driver_skill_residual_s.
-- No base_pace_status filter: it covers every row the model has, so a row with
-- base_pace_status <> 'MEASURED' is held to the identity too if all its terms
-- are non-NULL. pace_delta_s is a term, and it is NULL without a base, so in
-- practice that set is empty; the test states the contract rather than
-- relying on it. Returns the offending rows.
{{ config(severity='error') }}

SELECT
    lap_id,
    race_id,
    lap_number,
    base_pace_status,
    pace_delta_s,
    total_explained_s,
    driver_skill_residual_s
FROM {{ ref('int_lap_residual_decomposed') }}
WHERE
    pace_delta_s IS NOT NULL
    AND fuel_component_s IS NOT NULL
    AND compound_component_s IS NOT NULL
    AND constructor_component_s IS NOT NULL
    AND dirty_air_tax_s IS NOT NULL
    AND driver_skill_residual_s IS NOT NULL
    AND ABS(
        pace_delta_s
        - (
            fuel_component_s
            + compound_component_s
            + constructor_component_s
            + dirty_air_tax_s
            + driver_skill_residual_s
        )
    ) > 1e-6
