-- Component fill semantics of int_lap_residual_decomposed, unchanged by
-- base_pace_status (asserted, not fixed):
--   * a lap with no int_track_evolution row (NO_EVOLUTION_ROW) has NULL
--     rubber_component_s and NULL ambient_component_s (the join leaves both NULL);
--   * a lap that has an evolution row carries a non-NULL ambient_component_s
--     (int_track_evolution zero-fills it with COALESCE(..., 0.0) upstream) and a
--     reason that is NULL, INSUFFICIENT_LAPS or NO_FIELD_BASE;
--   * rubber_component_s is NULL where the reason is INSUFFICIENT_LAPS or NO_FIELD_BASE.
-- Returns the offending rows.
{{ config(severity='error') }}

SELECT
    lap_id,
    race_id,
    lap_number,
    base_pace_status,
    track_evolution_unavailable_reason,
    rubber_component_s,
    ambient_component_s
FROM {{ ref('int_lap_residual_decomposed') }}
WHERE
    (
        track_evolution_unavailable_reason = 'NO_EVOLUTION_ROW'
        AND (rubber_component_s IS NOT NULL OR ambient_component_s IS NOT NULL)
    )
    OR (
        track_evolution_unavailable_reason IS DISTINCT FROM 'NO_EVOLUTION_ROW'
        AND ambient_component_s IS NULL
    )
    OR (
        track_evolution_unavailable_reason IN ('INSUFFICIENT_LAPS', 'NO_FIELD_BASE')
        AND rubber_component_s IS NOT NULL
    )
