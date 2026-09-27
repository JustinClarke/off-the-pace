-- T1 (F1, WI-01). pace_delta_s must never carry a value for a lap the field
-- pace curve has no measured row for.
--
-- Before this fix, int_lap_residual_decomposed computed
-- pace_delta_s = lap_time_s - COALESCE(base_track_pace_s, lap_time_s), which
-- reads as pace_delta_s = 0 for a lap with no measured base -- "this driver
-- ran exactly the field's pace" fabricated for a lap where the field's pace
-- was never measured at all (9.3% of laps, 14,892 / 160,207, pre-fix
-- 2026-09-25 build). NULL must propagate instead.
{{ config(severity='error') }}

SELECT *
FROM {{ ref('int_lap_residual_decomposed') }}
WHERE base_track_pace_s IS NULL
  AND pace_delta_s IS NOT NULL
