-- T17 (F23b, WI-01). Every BASE-MEASURED spine lap with a lagged dirty-air
-- share > 0 must have a tax row in int_dirty_air_tax_component. The lag is
-- re-derived independently here (not read from int_dirty_air_tax_component's
-- own dirty_air_intensity_lag1 column) so this test cannot pass by
-- construction.
--
-- Before this fix, int_dirty_air_tax_component's `panel` CTE filtered on
-- correction_weight = 1.0 AND NOT rainfall -- governing which laps
-- ESTIMATED theta, but because with_tax also read from that same filtered
-- panel, a downweighted or wet lap that genuinely followed dirty air got no
-- row at all, which int_lap_residual_decomposed's
-- COALESCE(dirty_air_tax_s, 0.0) then read as "0 s of dirty air." The
-- estimation filter now governs calibration_panel only; every base-measured
-- lap (panel_base) gets a tax row regardless of its own weight/weather.
--
-- Restricted to base_track_pace_s IS NOT NULL: a lap with no measured field
-- base correctly has no tax row either (F1/F23a, its own NULL-propagation
-- reason, not this one) -- e.g. lap 2 of a race whose whole field shares an
-- out-lap there (2,309 such rows measured 2026-09-27).
{{ config(severity='error') }}

WITH lag AS (
    SELECT
        g.lap_id,
        LAG(COALESCE(a.dirty_air_share_lap, 0.0), 1, 0.0) OVER (
            PARTITION BY g.stint_id ORDER BY g.lap_in_stint
        ) AS dirty_air_share_lag1
    FROM {{ ref('int_stint_geometry') }} AS g
    LEFT JOIN {{ ref('int_lap_air_state') }} AS a ON g.lap_id = a.lap_id
)

SELECT
    r.lap_id,
    lag.dirty_air_share_lag1
FROM {{ ref('int_lap_residual_decomposed') }} AS r
INNER JOIN lag ON r.lap_id = lag.lap_id
LEFT JOIN {{ ref('int_dirty_air_tax_component') }} AS d ON r.lap_id = d.lap_id
WHERE d.lap_id IS NULL
  AND lag.dirty_air_share_lag1 > 0
  AND r.base_track_pace_s IS NOT NULL
