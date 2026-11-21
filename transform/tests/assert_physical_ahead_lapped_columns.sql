-- int_lap_physical_ahead: the lapped tag is consistent and never leaks into the headline columns. Returns violating laps.
--   * is_lapped_lap is exactly validity_class = 'lapped';
--   * the lapped_* columns are populated on lapped laps (lapped_time_measured_s) and NULL on every other lap;
--   * lapped_seconds_within_1s never exceeds lapped_time_measured_s;
--   * the headline gap / time columns stay NULL on lapped laps (lapped time is reported on its own, never merged).
SELECT lap_id, validity_class, is_lapped_lap, lapped_seconds_within_1s, lapped_time_measured_s
FROM {{ ref('int_lap_physical_ahead') }}
WHERE
    is_lapped_lap IS DISTINCT FROM (validity_class = 'lapped')
    OR (NOT is_lapped_lap AND (
        lapped_seconds_within_1s IS NOT NULL OR lapped_time_measured_s IS NOT NULL OR lapped_gap_phys_min_s IS NOT NULL
    ))
    OR (is_lapped_lap AND (
        lapped_time_measured_s IS NULL OR lapped_seconds_within_1s IS NULL
        OR lapped_seconds_within_1s > lapped_time_measured_s + 1e-9
        OR gap_ahead_phys_s IS NOT NULL OR time_within_1s_phys_s IS NOT NULL OR time_measured_s IS NOT NULL
    ))
