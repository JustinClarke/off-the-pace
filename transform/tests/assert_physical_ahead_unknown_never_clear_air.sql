-- int_lap_physical_ahead: a lap that is not valid_same_lap carries no gap, no close-behind time and no
-- within-1s flag, so it can never be read as clear air (flag FALSE) or as following (flag TRUE). A spine lap
-- with no position samples must be 'unknown'. A valid_same_lap lap must have the flag (TRUE or FALSE).
SELECT lap_id, validity_class, is_within_1s_of_car_ahead, gap_ahead_phys_s, time_within_1s_phys_s, n_samples
FROM {{ ref('int_lap_physical_ahead') }}
WHERE
    (validity_class <> 'valid_same_lap' AND (
        is_within_1s_of_car_ahead IS NOT NULL
        OR gap_ahead_phys_s IS NOT NULL
        OR gap_ahead_phys_median_s IS NOT NULL
        OR time_within_1s_phys_s IS NOT NULL
        OR time_measured_s IS NOT NULL))
    OR (validity_class = 'valid_same_lap' AND is_within_1s_of_car_ahead IS NULL)
    OR (n_samples = 0 AND validity_class <> 'unknown')
    -- the flag must agree with the gap it summarises
    OR (is_within_1s_of_car_ahead AND NOT (gap_ahead_phys_s < 1.0))
    OR (NOT is_within_1s_of_car_ahead AND gap_ahead_phys_s < 1.0)
