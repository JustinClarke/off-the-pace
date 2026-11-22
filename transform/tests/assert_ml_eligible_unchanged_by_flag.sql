-- ml_eligible must not depend on constructor_pace_is_filled. Recomputes the
-- rule written in fct_lap_residuals (full-weight lap, compound component
-- present and <= 10, |constructor_component_s| <= 10, lap time present) and
-- compares it with the stored value. Returns violating rows.
SELECT
    lap_id,
    ml_eligible,
    constructor_pace_is_filled
FROM {{ ref('fct_lap_residuals') }}
WHERE
    ml_eligible IS DISTINCT FROM (
        correction_weight = 1.0
        AND compound_component_s IS NOT NULL
        AND compound_component_s <= 10.0
        AND ABS(constructor_component_s) <= 10.0
        AND lap_time_s IS NOT NULL
    )
