-- base_pace_status (int_lap_residual_decomposed) must agree with the lap's own
-- int_field_pace_curve row, not with a proxy:
--   NO_CELL   <=> no curve row for (race_year, race_id, lap_number), and
--                 base_eligible_lap_count IS NULL
--   THIN_CELL <=> a curve row with low_sample_flag, and base_eligible_lap_count
--                 equals that row's eligible_lap_count
--   MEASURED  <=> base_track_pace_s IS NOT NULL (a curve row, not thin)
-- Returns the offending laps.
{{ config(severity='error') }}

SELECT
    r.lap_id,
    r.race_id,
    r.lap_number,
    r.base_pace_status,
    r.base_eligible_lap_count,
    r.base_track_pace_s,
    f.eligible_lap_count AS curve_eligible_lap_count,
    f.low_sample_flag AS curve_low_sample_flag
FROM {{ ref('int_lap_residual_decomposed') }} AS r
LEFT JOIN {{ ref('int_field_pace_curve') }} AS f
    ON
        r.race_year = f.race_year
        AND r.race_id = f.race_id
        AND r.lap_number = f.lap_number
WHERE
    (r.base_pace_status = 'NO_CELL'
        AND (f.race_id IS NOT NULL OR r.base_eligible_lap_count IS NOT NULL))
    OR (r.base_pace_status = 'THIN_CELL'
        AND (
            f.race_id IS NULL
            OR r.base_eligible_lap_count IS DISTINCT FROM f.eligible_lap_count
            OR r.base_track_pace_s IS NOT NULL
        ))
    OR (r.base_pace_status = 'MEASURED'
        AND (
            f.race_id IS NULL
            OR f.low_sample_flag
            OR r.base_track_pace_s IS NULL
            OR r.base_eligible_lap_count IS DISTINCT FROM f.eligible_lap_count
        ))
    OR (r.base_track_pace_s IS NOT NULL AND r.base_pace_status <> 'MEASURED')
    OR (f.race_id IS NULL AND r.base_pace_status <> 'NO_CELL')
    OR (f.low_sample_flag AND r.base_pace_status <> 'THIN_CELL')
