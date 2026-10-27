-- DA-01 step 3. Crossing-order car ahead (int_lap_proximity logic, rebuilt
-- fresh from bronze rather than read from the stale table), lapped-car share,
-- and FastF1 DriverAhead vs crossing order.
-- Crossings: first session-clock reading per (race, driver, lap, 1%-bin),
-- on track, outside the driver's own pit window. Ordered inside (race, bin)
-- by (crossing_time, driver_id); previous row = car ahead on track.
-- Self-match and > 300 s gaps are "no car ahead" (same guards as the model).
CREATE OR REPLACE TABLE crossings AS
SELECT race_year, race_id, driver_id, lap_number,
       CAST(FLOOR(relative_distance * 100) AS INTEGER) AS track_bin,
       MIN(session_time_s) AS crossing_time_s,
       BOOL_AND(is_green) AS all_green,
       MIN(ff_ahead_driver_id) AS ff_ahead_driver_id
FROM pos_flags
WHERE track_status = 'OnTrack' AND NOT in_pit
GROUP BY 1, 2, 3, 4, 5
;;
CREATE OR REPLACE TABLE xorder AS
WITH n AS (
    SELECT *,
           LAG(driver_id) OVER w AS ahead_driver_id,
           LAG(crossing_time_s) OVER w AS ahead_crossing_s,
           LAG(lap_number) OVER w AS ahead_lap_number
    FROM crossings
    WINDOW w AS (PARTITION BY race_id, track_bin ORDER BY crossing_time_s, driver_id)
)
SELECT *,
       CASE WHEN ahead_driver_id <> driver_id AND crossing_time_s - ahead_crossing_s <= 300
            THEN crossing_time_s - ahead_crossing_s END AS gap_ahead_s,
       CASE WHEN ahead_driver_id <> driver_id AND crossing_time_s - ahead_crossing_s <= 300
            THEN CASE WHEN ahead_lap_number < lap_number THEN 'ahead_is_lapped_car'
                      WHEN ahead_lap_number > lap_number THEN 'self_is_lapped_ahead_is_lapping_car'
                      ELSE 'same_lap' END
            ELSE 'no_car_ahead' END AS lap_relation
FROM n
;;
-- OUT: 03_crossing_order_green_bins_by_season
SELECT race_year, COUNT(*) AS green_bins,
       ROUND(AVG(CASE WHEN lap_relation = 'no_car_ahead' THEN 1.0 ELSE 0 END), 4) AS share_no_car_ahead,
       ROUND(AVG(CASE WHEN lap_relation = 'same_lap' THEN 1.0 ELSE 0 END), 4) AS share_same_lap,
       ROUND(AVG(CASE WHEN lap_relation = 'ahead_is_lapped_car' THEN 1.0 ELSE 0 END), 4) AS share_ahead_is_lapped,
       ROUND(AVG(CASE WHEN lap_relation = 'self_is_lapped_ahead_is_lapping_car' THEN 1.0 ELSE 0 END), 4) AS share_self_is_lapped,
       ROUND(AVG(CASE WHEN lap_relation = 'ahead_is_lapped_car' AND gap_ahead_s < 3 THEN 1.0 ELSE 0 END), 4) AS share_lapped_ahead_within_3s
FROM xorder WHERE all_green GROUP BY ROLLUP(1) ORDER BY 1
;;
-- OUT: 03_driverahead_vs_crossing_order
-- Q4: does FastF1 DriverAhead name lapped cars? Compare it with the on-track
-- car ahead, split by how that on-track car relates by lap.
SELECT lap_relation, COUNT(*) AS green_bins,
       ROUND(AVG(CASE WHEN ff_ahead_driver_id IS NULL THEN 1.0 ELSE 0 END), 4) AS share_ff_null,
       ROUND(AVG(CASE WHEN ff_ahead_driver_id = ahead_driver_id THEN 1.0 ELSE 0 END), 4) AS share_ff_equals_track_ahead
FROM xorder WHERE all_green GROUP BY 1 ORDER BY 2 DESC
;;
-- OUT: 03_driverahead_vs_crossing_order_close
-- Same, restricted to on-track gap < 2 s (the band that matters).
SELECT lap_relation, COUNT(*) AS green_bins_gap_lt_2s,
       ROUND(AVG(CASE WHEN ff_ahead_driver_id IS NULL THEN 1.0 ELSE 0 END), 4) AS share_ff_null,
       ROUND(AVG(CASE WHEN ff_ahead_driver_id = ahead_driver_id THEN 1.0 ELSE 0 END), 4) AS share_ff_equals_track_ahead
FROM xorder WHERE all_green AND gap_ahead_s < 2 GROUP BY 1 ORDER BY 2 DESC
;;
-- OUT: 03_ff_ahead_lap_relation
-- Direct test: when FastF1 names a car ahead, is that car ever on a lower lap
-- (i.e. a lapped car) at the same bin crossing? Join FF-named car's crossing of
-- the same bin closest before this crossing.
WITH named AS (
    SELECT x.race_id, x.driver_id, x.lap_number, x.track_bin, x.crossing_time_s, x.ff_ahead_driver_id
    FROM xorder AS x WHERE x.all_green AND x.ff_ahead_driver_id IS NOT NULL
), j AS (
    SELECT n.*, c.lap_number AS ff_ahead_lap, c.crossing_time_s AS ff_ahead_cross
    FROM named AS n ASOF LEFT JOIN crossings AS c
      ON n.race_id = c.race_id AND n.track_bin = c.track_bin AND n.ff_ahead_driver_id = c.driver_id
     AND n.crossing_time_s >= c.crossing_time_s
)
SELECT CASE WHEN ff_ahead_lap IS NULL THEN 'ff_ahead_not_found_before'
            WHEN ff_ahead_lap < lap_number THEN 'ff_ahead_on_lower_lap (lapped car)'
            WHEN ff_ahead_lap = lap_number THEN 'ff_ahead_same_lap'
            ELSE 'ff_ahead_on_higher_lap' END AS ff_ahead_relation,
       COUNT(*) AS n, ROUND(COUNT(*) / SUM(COUNT(*)) OVER (), 5) AS share
FROM j GROUP BY 1 ORDER BY 2 DESC
