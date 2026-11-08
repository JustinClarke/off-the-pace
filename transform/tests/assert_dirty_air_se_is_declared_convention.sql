-- TX-04: dirty_air_tax_se_s is a declared CONVENTION, not an estimate:
-- 0.15 × dirty_air_tax_s, zero on clean-air laps, not propagated from θ's interval
-- (intermediate/schema.yml, marts/schema.yml fct_lap_residuals). This test pins that
-- convention, so a future change to how the SE is computed has to change the docs too.
--
-- Fails on any row where the tax is present and |SE − 0.15 × tax| > 1e-12, or where the
-- tax is present and the SE is NULL (or the reverse).
SELECT
    lap_id,
    dirty_air_tax_s,
    dirty_air_tax_se_s
FROM {{ ref('int_dirty_air_tax_component') }}
WHERE
    (
        dirty_air_tax_s IS NOT NULL
        AND (
            dirty_air_tax_se_s IS NULL
            OR ABS(dirty_air_tax_se_s - 0.15 * dirty_air_tax_s) > 1e-12
        )
    )
    OR (dirty_air_tax_s IS NULL AND dirty_air_tax_se_s IS NOT NULL)
