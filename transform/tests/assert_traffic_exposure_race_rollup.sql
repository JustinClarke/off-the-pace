-- int_traffic_exposure_race: the race roll-up conserves the driver-race table. Lap classes partition n_laps,
-- n_laps / n_laps_measured equal the driver-race sums, close-behind time never exceeds measured time, the
-- measured and unmeasured shares sum to 1 (to rounding), and quality_flag agrees with is_low_measured_share.
-- Complements assert_traffic_exposure_lap_partition (driver grain); shares in [0,1] are yml accepted_range.
WITH d AS (
    SELECT race_id, SUM(n_laps) AS n_laps, SUM(n_laps_measured) AS n_laps_measured, COUNT(*) AS n_drivers
    FROM {{ ref('int_traffic_exposure_driver_race') }}
    GROUP BY race_id
)
SELECT COALESCE(r.race_id, d.race_id) AS race_id
FROM {{ ref('int_traffic_exposure_race') }} AS r
FULL OUTER JOIN d ON r.race_id = d.race_id
WHERE
    r.race_id IS NULL OR d.race_id IS NULL
    OR r.n_laps <> d.n_laps
    OR r.n_laps_measured <> d.n_laps_measured
    OR r.n_drivers <> d.n_drivers
    OR r.n_laps <> r.n_laps_measured + r.n_laps_neutralised + r.n_laps_lap1 + r.n_laps_side_by_side
        + r.n_laps_overlapping + r.n_laps_lapped + r.n_laps_unknown
    OR r.time_close_behind_s > r.time_measured_s + 1e-6
    OR r.n_laps_within_1s > r.n_laps_measured
    -- seven 4-dp rounded shares: allow 7e-4
    OR ABS(r.share_laps_measured + r.share_laps_neutralised + r.share_laps_lap1 + r.share_laps_side_by_side
        + r.share_laps_overlapping + r.share_laps_lapped + r.share_laps_unknown - 1.0) > 7e-4
    OR (r.quality_flag = 'ok') = r.is_low_measured_share
