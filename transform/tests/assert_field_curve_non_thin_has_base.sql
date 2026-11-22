-- base_pace_status relies on this: an int_field_pace_curve row that is not thin
-- (eligible_lap_count >= 5) always carries a smoothed base. If it ever did not,
-- int_lap_residual_decomposed would label that lap THIN_CELL while its curve
-- row says otherwise. Returns any such curve row.
{{ config(severity='error') }}

SELECT
    race_year,
    race_id,
    lap_number,
    eligible_lap_count,
    low_sample_flag
FROM {{ ref('int_field_pace_curve') }}
WHERE
    NOT low_sample_flag
    AND field_pace_smoothed_s IS NULL
