-- TX-03. fct_lap_residuals writes dirty_air_tax_s = 0.0 where
-- int_dirty_air_tax_component has no row. That fill is harmless to
-- driver_skill_residual_s only because a missing row happens exactly where
-- the base is unmeasured: no dirty-air row <=> pace_delta_s IS NULL. This
-- turns the int_lap_residual_decomposed header's claim into a tested
-- invariant; consumers (AP-01) tell an unmeasured 0.0 apart by
-- pace_delta_s IS NULL. Fails per offending lap.
SELECT
    f.lap_id,
    f.race_id,
    f.pace_delta_s,
    da.lap_id IS NOT NULL AS has_dirty_air_row
FROM {{ ref('fct_lap_residuals') }} AS f
LEFT JOIN {{ ref('int_dirty_air_tax_component') }} AS da
    ON f.lap_id = da.lap_id
WHERE (da.lap_id IS NULL) <> (f.pace_delta_s IS NULL)
