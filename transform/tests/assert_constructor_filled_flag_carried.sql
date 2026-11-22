-- fct_lap_residuals.constructor_pace_is_filled equals the flag on
-- int_lap_residual_decomposed per lap_id, and filled laps carry the 0.0 fill.
-- The SE-NULL-on-filled invariant is asserted by the expression test on
-- int_lap_residual_decomposed.constructor_pace_is_filled (intermediate
-- schema.yml). Returns violating rows. No race id is required (CI fixture
-- safe).
SELECT
    f.lap_id,
    f.constructor_pace_is_filled AS fct_flag,
    d.constructor_pace_is_filled AS int_flag,
    f.constructor_component_s
FROM {{ ref('fct_lap_residuals') }} AS f
LEFT JOIN {{ ref('int_lap_residual_decomposed') }} AS d
    ON f.lap_id = d.lap_id
WHERE
    d.lap_id IS NULL
    OR f.constructor_pace_is_filled
        IS DISTINCT FROM d.constructor_pace_is_filled
    OR (
        f.constructor_pace_is_filled
        AND f.constructor_component_s IS DISTINCT FROM 0.0
    )
