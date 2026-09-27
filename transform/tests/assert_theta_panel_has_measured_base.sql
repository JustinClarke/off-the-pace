-- T18 (F23a, WI-01). No lap in int_dirty_air_tax_component's output (its
-- grain IS its calibration/application panel, panel_base) may lack a
-- measured field base. Before this fix, `panel`'s partial_residual_s used
-- COALESCE(field_pace_smoothed_s, lap_time_s), which made
-- partial_residual_s = -fuel_component_s (never NULL) for a fabricated-base
-- lap, so the pre-existing `WHERE partial_residual_s IS NOT NULL` filter
-- never actually excluded it from theta's fit. panel_base now INNER JOINs
-- int_field_pace_curve directly, so a base-missing lap gets no row at all.
{{ config(severity='error') }}

SELECT d.lap_id
FROM {{ ref('int_dirty_air_tax_component') }} AS d
INNER JOIN {{ ref('int_lap_residual_decomposed') }} AS r ON d.lap_id = r.lap_id
WHERE r.base_track_pace_s IS NULL
