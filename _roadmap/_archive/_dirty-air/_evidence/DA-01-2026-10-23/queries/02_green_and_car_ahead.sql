-- DA-01 step 2. Green-flag samples, car-ahead known, distance NULL.
-- Green sample (audit definition, stricter-or-equal to design note s1):
--   * pos Status = 'OnTrack'
--   * session track status at that instant = '1' (all clear) -- asof join on
--     stg_track_status; codes 2 (yellow, any sector), 4 SC, 5 red, 6/7 VSC excluded
--   * lap_number >= 2
--   * outside the driver's own pit window (stg_pits; open window = +120 s,
--     the proximity_pit_window_open_s default)
-- The "2 laps after a restart" rule is NOT applied here (noted in the README).
CREATE OR REPLACE TABLE ts AS
SELECT race_id, session_time_s, MAX(status_code) AS status_code  -- same-instant pairs: worst code wins
FROM dev.main.stg_track_status GROUP BY 1, 2
;;
CREATE OR REPLACE TABLE pitw AS
SELECT race_id, driver_id, pit_in_time_s,
       COALESCE(pit_out_time_s, pit_in_time_s + 120.0) AS pit_out_time_s
FROM dev.main.stg_pits WHERE pit_in_time_s IS NOT NULL
;;
CREATE OR REPLACE TABLE dn AS
SELECT DISTINCT race_id, driver_number, driver_id
FROM dev.main.stg_results WHERE driver_number IS NOT NULL
;;
CREATE OR REPLACE TABLE lap_pos AS
SELECT race_id, driver_id, lap_number, position
FROM dev.main.stg_laps
;;
CREATE OR REPLACE TABLE pos_flags AS
WITH a AS (
    SELECT p.race_year, p.race_id, p.driver_id, p.lap_number, p.rn, p.session_time_s,
           p.relative_distance, p.track_status, p.driver_ahead_number, p.distance_to_ahead_m,
           p.speed_kph, p.dt_s, t.status_code
    FROM pos AS p ASOF LEFT JOIN ts AS t
      ON p.race_id = t.race_id AND p.session_time_s >= t.session_time_s
), b AS (
    SELECT a.*, (w.pit_in_time_s IS NOT NULL AND a.session_time_s <= w.pit_out_time_s) AS in_pit
    FROM a ASOF LEFT JOIN pitw AS w
      ON a.race_id = w.race_id AND a.driver_id = w.driver_id AND a.session_time_s >= w.pit_in_time_s
)
SELECT b.*, dn.driver_id AS ff_ahead_driver_id, lp.position AS lap_end_position,
       (b.track_status = 'OnTrack' AND b.status_code = '1' AND b.lap_number >= 2 AND NOT b.in_pit) AS is_green
FROM b
LEFT JOIN dn ON b.race_id = dn.race_id AND b.driver_ahead_number = dn.driver_number
LEFT JOIN lap_pos AS lp ON b.race_id = lp.race_id AND b.driver_id = lp.driver_id AND b.lap_number = lp.lap_number
;;
-- OUT: 02_exclusion_funnel_by_season
SELECT race_year,
       COUNT(*) AS all_samples,
       SUM(CASE WHEN track_status = 'OnTrack' THEN 1 ELSE 0 END) AS ontrack,
       SUM(CASE WHEN status_code IS NULL THEN 1 ELSE 0 END) AS no_track_status_yet,
       SUM(CASE WHEN status_code <> '1' THEN 1 ELSE 0 END) AS non_green_flag,
       SUM(CASE WHEN lap_number < 2 THEN 1 ELSE 0 END) AS lap1,
       SUM(CASE WHEN in_pit THEN 1 ELSE 0 END) AS in_own_pit_window,
       SUM(CASE WHEN is_green THEN 1 ELSE 0 END) AS green,
       ROUND(AVG(CASE WHEN is_green THEN 1.0 ELSE 0 END), 4) AS share_green
FROM pos_flags GROUP BY 1 ORDER BY 1
;;
-- OUT: 02_car_ahead_known_by_season
-- Of GREEN samples: raw DriverAhead present, it resolves to a race entrant,
-- distance present, both present ("ff_valid"), and NULL-distance share.
SELECT race_year,
       COUNT(*) AS green,
       ROUND(AVG(CASE WHEN driver_ahead_number IS NOT NULL THEN 1.0 ELSE 0 END), 4) AS share_driver_ahead_present,
       ROUND(AVG(CASE WHEN ff_ahead_driver_id IS NOT NULL THEN 1.0 ELSE 0 END), 4) AS share_driver_ahead_resolved,
       ROUND(AVG(CASE WHEN distance_to_ahead_m IS NULL THEN 1.0 ELSE 0 END), 4) AS share_distance_null,
       ROUND(AVG(CASE WHEN distance_to_ahead_m = 0 THEN 1.0 ELSE 0 END), 4) AS share_distance_zero,
       ROUND(AVG(CASE WHEN ff_ahead_driver_id IS NOT NULL AND distance_to_ahead_m > 0 THEN 1.0 ELSE 0 END), 4) AS share_ff_valid,
       ROUND(AVG(CASE WHEN lap_end_position = 1 THEN 1.0 ELSE 0 END), 4) AS share_leader_samples
FROM pos_flags WHERE is_green GROUP BY ROLLUP(1) ORDER BY 1
;;
-- OUT: 02_car_ahead_missing_leader_split
-- Is a missing DriverAhead concentrated on the race leader (who may legitimately have no car ahead)?
SELECT CASE WHEN lap_end_position = 1 THEN 'leader (lap-end P1)' WHEN lap_end_position IS NULL THEN 'position unknown' ELSE 'P2+' END AS who,
       COUNT(*) AS green,
       ROUND(AVG(CASE WHEN ff_ahead_driver_id IS NULL THEN 1.0 ELSE 0 END), 4) AS share_ahead_unresolved,
       ROUND(AVG(CASE WHEN distance_to_ahead_m IS NULL THEN 1.0 ELSE 0 END), 4) AS share_distance_null
FROM pos_flags WHERE is_green GROUP BY 1 ORDER BY 1
;;
-- OUT: 02_distance_null_pattern
-- When distance is NULL, what does DriverAhead look like, and where in the lap?
SELECT race_year,
       COUNT(*) AS green_null_distance,
       ROUND(AVG(CASE WHEN driver_ahead_number IS NULL THEN 1.0 ELSE 0 END), 4) AS share_also_no_driver_ahead,
       ROUND(AVG(CASE WHEN relative_distance < 0.02 OR relative_distance > 0.98 THEN 1.0 ELSE 0 END), 4) AS share_within_2pct_of_line,
       ROUND(AVG(CASE WHEN rn <= 20 THEN 1.0 ELSE 0 END), 4) AS share_first_20_samples
FROM pos_flags WHERE is_green AND distance_to_ahead_m IS NULL GROUP BY 1 ORDER BY 1
