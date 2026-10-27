-- OUT: 03b_ff_names_lower_lap_detail
-- Detail for FastF1 DriverAhead naming a car on a lower lap: how long ago did
-- that car last cross this bin (a lapped car just passed = ~0-few s behind me
-- would show ~ one lap time), and is it near the line?
WITH named AS (
    SELECT x.race_year, x.race_id, x.driver_id, x.lap_number, x.track_bin, x.crossing_time_s, x.ff_ahead_driver_id
    FROM xorder AS x WHERE x.all_green AND x.ff_ahead_driver_id IS NOT NULL
), j AS (
    SELECT n.*, c.lap_number AS ff_ahead_lap, c.crossing_time_s AS ff_ahead_cross
    FROM named AS n ASOF LEFT JOIN crossings AS c
      ON n.race_id = c.race_id AND n.track_bin = c.track_bin AND n.ff_ahead_driver_id = c.driver_id
     AND n.crossing_time_s >= c.crossing_time_s
), nxt AS (
    -- the named car's NEXT crossing of the bin after mine: if it comes within seconds, it is right behind me (lapped, just passed)
    SELECT j.*, c2.crossing_time_s AS ff_next_cross
    FROM j ASOF LEFT JOIN crossings AS c2
      ON j.race_id = c2.race_id AND j.track_bin = c2.track_bin AND j.ff_ahead_driver_id = c2.driver_id
     AND c2.crossing_time_s > j.crossing_time_s
    WHERE j.ff_ahead_lap < j.lap_number
)
SELECT COUNT(*) AS n,
       ROUND(MEDIAN(ff_next_cross - crossing_time_s), 2) AS med_named_car_crosses_after_me_s,
       ROUND(AVG(CASE WHEN ff_next_cross - crossing_time_s < 5 THEN 1.0 ELSE 0 END), 3) AS share_named_car_within_5s_behind,
       ROUND(AVG(CASE WHEN ff_next_cross IS NULL THEN 1.0 ELSE 0 END), 3) AS share_named_car_never_crosses_again,
       ROUND(AVG(CASE WHEN track_bin IN (0, 99) THEN 1.0 ELSE 0 END), 3) AS share_at_line_bins
FROM nxt
