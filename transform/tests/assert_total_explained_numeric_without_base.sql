-- Accepted behaviour, pinned so it is stated rather than assumed:
-- total_explained_s does NOT read the pace base. It is the sum of fuel,
-- compound, constructor and dirty-air tax, so it is numeric on rows where
-- base_pace_status is THIN_CELL or NO_CELL, and NULL exactly when one of those
-- four terms is NULL (an unknown tyre age or an unknown dirty-air tax). The
-- test returns a row only if total_explained_s depends on the base in some
-- other way, or is NULL/non-NULL against that rule. A numeric total_explained_s
-- on a non-MEASURED row is allowed and returns nothing.
{{ config(severity='error') }}

SELECT
    lap_id,
    race_id,
    lap_number,
    base_pace_status,
    total_explained_s
FROM {{ ref('int_lap_residual_decomposed') }}
WHERE
    (
        total_explained_s IS NULL
        AND fuel_component_s IS NOT NULL
        AND compound_component_s IS NOT NULL
        AND constructor_component_s IS NOT NULL
        AND dirty_air_tax_s IS NOT NULL
    )
    OR (
        total_explained_s IS NOT NULL
        AND (
            fuel_component_s IS NULL
            OR compound_component_s IS NULL
            OR constructor_component_s IS NULL
            OR dirty_air_tax_s IS NULL
            OR ABS(
                total_explained_s
                - (fuel_component_s + compound_component_s + constructor_component_s + dirty_air_tax_s)
            ) > 1e-6
        )
    )
