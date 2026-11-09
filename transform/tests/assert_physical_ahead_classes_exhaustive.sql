-- int_lap_physical_ahead: the per-sample classes partition the lap's samples, and the lap class follows the
-- documented precedence (unknown > lap1 > lapped > overlapping > side_by_side > valid_same_lap). Together with
-- the accepted_values test on validity_class this makes the six lap classes exhaustive and exclusive.
{% set m = var('physical_ahead_min_class_samples', 4) %}
{% set u = var('physical_ahead_unknown_max_share', 0.05) %}
WITH x AS (
    SELECT
        *,
        CASE
            WHEN n_samples = 0 OR n_unknown_samples::DOUBLE / n_samples > {{ u }} THEN 'unknown'
            WHEN lap_number = 1 THEN 'lap1'
            WHEN n_lapped_samples >= {{ m }} THEN 'lapped'
            WHEN n_overlapping_samples >= {{ m }} THEN 'overlapping'
            WHEN n_side_by_side_samples >= {{ m }} THEN 'side_by_side'
            ELSE 'valid_same_lap'
        END AS expected_class
    FROM {{ ref('int_lap_physical_ahead') }}
)
SELECT lap_id, validity_class, expected_class, n_samples
FROM x
WHERE
    n_samples <> n_unknown_samples + n_lap1_samples + n_side_by_side_samples + n_overlapping_samples
        + n_lapped_samples + n_same_lap_samples + n_clear_samples
    OR validity_class <> expected_class
