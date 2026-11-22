-- fct_lap_residuals: a filled constructor observation (the 0.0 fill, flagged
-- by constructor_pace_is_filled) keeps constructor_component_s = 0.0 and a
-- NULL constructor_component_se_s. Asserted on the mart, not on
-- int_lap_residual_decomposed. Returns violating rows. A NULL flag is not
-- skipped: it is documented not_null, so it is treated as a violation when
-- the fill signature (0.0 with NULL SE) is broken. No race id is required
-- (CI fixture safe).
SELECT
    lap_id,
    constructor_pace_is_filled,
    constructor_component_s,
    constructor_component_se_s
FROM {{ ref('fct_lap_residuals') }}
WHERE
    constructor_pace_is_filled IS DISTINCT FROM FALSE
    AND (
        constructor_component_s IS DISTINCT FROM 0.0
        OR constructor_component_se_s IS NOT NULL
    )
