-- int_traffic_exposure_race: lists races flagged is_low_measured_share (measured laps below the floor,
-- var traffic_exposure_min_measured_share, default 0.25, provisional). WARN only: the flag is a column and no
-- race is removed. The rows returned are the flagged races, so the row count is the count of flagged races:
-- for these races the headline shares describe a minority of laps. With the zero-XY guard off, Singapore 2019
-- is expected to appear if its lapped laps push the measured share under the floor.
{{ config(severity='warn') }}
SELECT race_id, share_laps_measured, share_laps_lapped, share_laps_unknown, quality_flag, zero_xy_guard_on
FROM {{ ref('int_traffic_exposure_race') }}
WHERE is_low_measured_share
