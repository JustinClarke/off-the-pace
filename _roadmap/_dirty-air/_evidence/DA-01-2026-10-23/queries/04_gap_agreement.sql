-- DA-01 step 4. Gap agreement: position-channel crossing-time gap vs the
-- timing feed's gap, at the timing lines.
--
-- Truth = the timing feed's own sector-line session times (stg_laps
-- sector1/2/3_session_time_s, from FastF1 laps = F1 timing loops). The gap to
-- the car ahead at a line = my line time minus the line time of the car that
-- crossed that line immediately before me (any lap, other driver, <= 300 s).
--
-- Position estimate = the design note's g_i: the session time at which each
-- car's position-channel relative_distance reaches the line's location,
-- linearly interpolated between the two bracketing position samples of that
-- lap, differenced between the same two cars.
--
-- Line location r_line per race = median over driver-laps of the car's own
-- interpolated relative_distance at the timing-line instant. A bias in r_line
-- is common to both cars, so it only enters the gap through the two cars'
-- speed difference; the per-pair error is what we want to measure.
--
-- Lines: S1 and S2 are independent of FastF1's lap slicing. S3 (= finish
-- line) is NOT evaluated (line_loc keeps s1/s2 only, so s3 rows drop out of
-- every join below): FastF1 cuts telemetry into laps at timing lap
-- boundaries, so relative_distance there is partly defined by timing and the
-- comparison would be partly circular.
CREATE OR REPLACE TABLE line_times AS
WITH l AS (
    SELECT race_year, race_id, driver_id, lap_number, track_status, is_pit_lap,
           is_safety_car_lap, is_vsc_lap, is_red_flag_lap,
           sector1_session_time_s AS s1, sector2_session_time_s AS s2, sector3_session_time_s AS s3
    FROM dev.main.stg_laps
)
SELECT race_year, race_id, driver_id, lap_number, track_status, is_pit_lap,
       (is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap) AS neutralised, line, t_line
FROM l UNPIVOT (t_line FOR line IN (s1, s2, s3))
WHERE t_line IS NOT NULL
;;
-- own relative_distance at the timing instant (interpolated, same lap)
CREATE OR REPLACE TABLE line_rel AS
WITH pl AS (
    SELECT race_id, driver_id, lap_number, session_time_s, relative_distance FROM pos WHERE track_status = 'OnTrack'
), a AS (
    SELECT lt.*, p.session_time_s AS t0, p.relative_distance AS r0
    FROM line_times AS lt ASOF LEFT JOIN pl AS p
      ON lt.race_id = p.race_id AND lt.driver_id = p.driver_id AND lt.lap_number = p.lap_number
     AND lt.t_line >= p.session_time_s
), b AS (
    SELECT a.*, p.session_time_s AS t1, p.relative_distance AS r1
    FROM a ASOF LEFT JOIN pl AS p
      ON a.race_id = p.race_id AND a.driver_id = p.driver_id AND a.lap_number = p.lap_number
     AND a.t_line < p.session_time_s
)
SELECT *, CASE WHEN t1 > t0 THEN r0 + (r1 - r0) * (t_line - t0) / (t1 - t0) END AS r_at_line
FROM b
;;
CREATE OR REPLACE TABLE line_loc AS
SELECT race_id, line, MEDIAN(r_at_line) AS r_line, COUNT(*) AS n,
       QUANTILE_CONT(r_at_line, 0.9) - QUANTILE_CONT(r_at_line, 0.1) AS r_p10_p90_width
FROM line_rel
WHERE r_at_line IS NOT NULL AND NOT is_pit_lap AND NOT neutralised AND lap_number >= 2
  AND line IN ('s1', 's2')
GROUP BY 1, 2
;;
-- position-channel crossing time of r_line, per driver-lap
CREATE OR REPLACE TABLE pos_line_cross AS
WITH pl AS (
    SELECT race_id, driver_id, lap_number, session_time_s, relative_distance, speed_kph,
           distance_to_ahead_m, ff_ahead_driver_id
    FROM pos_flags WHERE track_status = 'OnTrack'
), k AS (
    SELECT lt.race_year, lt.race_id, lt.driver_id, lt.lap_number, lt.line, lt.t_line, lt.track_status,
           lt.is_pit_lap, lt.neutralised, ll.r_line
    FROM line_times AS lt JOIN line_loc AS ll ON lt.race_id = ll.race_id AND lt.line = ll.line
), a AS (
    SELECT k.*, p.session_time_s AS t0, p.relative_distance AS r0, p.speed_kph AS v0,
           p.distance_to_ahead_m AS ff_dist0, p.ff_ahead_driver_id AS ff_ahead0
    FROM k ASOF LEFT JOIN pl AS p
      ON k.race_id = p.race_id AND k.driver_id = p.driver_id AND k.lap_number = p.lap_number
     AND k.r_line >= p.relative_distance
), b AS (
    SELECT a.*, p.session_time_s AS t1, p.relative_distance AS r1
    FROM a ASOF LEFT JOIN pl AS p
      ON a.race_id = p.race_id AND a.driver_id = p.driver_id AND a.lap_number = p.lap_number
     AND a.r_line < p.relative_distance
)
SELECT *, CASE WHEN r1 > r0 AND t1 > t0 AND t1 - t0 <= 1.0
               THEN t0 + (t1 - t0) * (r_line - r0) / (r1 - r0) END AS t_pos,
       t1 - t0 AS bracket_dt
FROM b
;;
-- the pairs: car ahead by the TIMING feed at each line
CREATE OR REPLACE TABLE gap_pairs AS
WITH o AS (
    SELECT *,
           LAG(driver_id) OVER w AS a_driver, LAG(lap_number) OVER w AS a_lap,
           LAG(t_line) OVER w AS a_t_line, LAG(t_pos) OVER w AS a_t_pos,
           LAG(track_status) OVER w AS a_track_status, LAG(is_pit_lap) OVER w AS a_is_pit_lap,
           LAG(neutralised) OVER w AS a_neutralised
    FROM pos_line_cross
    WINDOW w AS (PARTITION BY race_id, line ORDER BY t_line, driver_id)
)
SELECT *,
       t_line - a_t_line AS gap_timing_s,
       t_pos - a_t_pos AS gap_pos_s,
       (t_pos - a_t_pos) - (t_line - a_t_line) AS disagreement_s,
       CASE WHEN ff_ahead0 = a_driver AND v0 > 0 THEN ff_dist0 / (v0 / 3.6) END AS gap_ff_dist_over_speed_s
FROM o
WHERE a_driver IS NOT NULL AND a_driver <> driver_id AND t_line - a_t_line <= 300
;;
CREATE OR REPLACE VIEW gap_eval AS
SELECT *,
       CASE WHEN gap_timing_s < 1 THEN '1: <1 s' WHEN gap_timing_s < 2 THEN '2: 1-2 s' ELSE '3: >=2 s' END AS band,
       CASE WHEN a_lap < lap_number THEN 'ahead_lapped' WHEN a_lap > lap_number THEN 'self_lapped' ELSE 'same_lap' END AS lap_rel
FROM gap_pairs
WHERE lap_number >= 2 AND a_lap >= 2
  AND track_status = '1' AND a_track_status = '1'
  AND NOT neutralised AND NOT a_neutralised
  AND NOT is_pit_lap AND NOT a_is_pit_lap
  AND t_pos IS NOT NULL AND a_t_pos IS NOT NULL
;;
-- OUT: 04_line_location_spread
-- How well does one relative_distance value locate a timing line? (width of
-- the 10-90% range of cars' own rel-distance at the line instant, in lap fraction)
SELECT line, COUNT(*) AS races, ROUND(MEDIAN(r_p10_p90_width), 5) AS median_width,
       ROUND(MAX(r_p10_p90_width), 5) AS max_width
FROM line_loc GROUP BY 1 ORDER BY 1
;;
-- OUT: 04_gap_agreement_by_band_s1s2
SELECT band, COUNT(*) AS n_pairs,
       ROUND(MEDIAN(disagreement_s), 4) AS median_diff_s,
       ROUND(MEDIAN(ABS(disagreement_s)), 4) AS median_abs_diff_s,
       ROUND(QUANTILE_CONT(disagreement_s, 0.25), 4) AS p25,
       ROUND(QUANTILE_CONT(disagreement_s, 0.75), 4) AS p75,
       ROUND(QUANTILE_CONT(ABS(disagreement_s), 0.90), 4) AS p90_abs,
       ROUND(QUANTILE_CONT(ABS(disagreement_s), 0.99), 4) AS p99_abs,
       ROUND(AVG(CASE WHEN ABS(disagreement_s) > 0.1 THEN 1.0 ELSE 0 END), 4) AS share_abs_gt_0_1,
       ROUND(AVG(CASE WHEN ABS(disagreement_s) > 0.25 THEN 1.0 ELSE 0 END), 4) AS share_abs_gt_0_25
FROM gap_eval WHERE line IN ('s1', 's2') GROUP BY 1 ORDER BY 1
;;
-- OUT: 04_gap_agreement_by_season_band_s1s2
SELECT race_year, band, COUNT(*) AS n_pairs,
       ROUND(MEDIAN(disagreement_s), 4) AS median_diff_s,
       ROUND(MEDIAN(ABS(disagreement_s)), 4) AS median_abs_diff_s,
       ROUND(QUANTILE_CONT(ABS(disagreement_s), 0.90), 4) AS p90_abs,
       ROUND(AVG(CASE WHEN ABS(disagreement_s) > 0.1 THEN 1.0 ELSE 0 END), 4) AS share_abs_gt_0_1,
       ROUND(AVG(CASE WHEN gap_pos_s <= 0 THEN 1.0 ELSE 0 END), 4) AS share_order_flipped
FROM gap_eval WHERE line IN ('s1', 's2') GROUP BY 1, 2 ORDER BY 1, 2
;;
-- OUT: 04_gap_agreement_by_line_band
SELECT line, band, COUNT(*) AS n_pairs,
       ROUND(MEDIAN(disagreement_s), 4) AS median_diff_s,
       ROUND(MEDIAN(ABS(disagreement_s)), 4) AS median_abs_diff_s,
       ROUND(QUANTILE_CONT(ABS(disagreement_s), 0.90), 4) AS p90_abs
FROM gap_eval GROUP BY 1, 2 ORDER BY 1, 2
;;
-- OUT: 04_gap_agreement_under_1s_fine
-- Finer bands under 1 s (the stop rule's band), S1+S2.
SELECT CASE WHEN gap_timing_s < 0.25 THEN '0.00-0.25' WHEN gap_timing_s < 0.5 THEN '0.25-0.50'
            WHEN gap_timing_s < 0.75 THEN '0.50-0.75' ELSE '0.75-1.00' END AS sub_band,
       COUNT(*) AS n_pairs,
       ROUND(MEDIAN(disagreement_s), 4) AS median_diff_s,
       ROUND(MEDIAN(ABS(disagreement_s)), 4) AS median_abs_diff_s,
       ROUND(QUANTILE_CONT(ABS(disagreement_s), 0.90), 4) AS p90_abs,
       ROUND(AVG(CASE WHEN gap_pos_s <= 0 THEN 1.0 ELSE 0 END), 4) AS share_order_flipped
FROM gap_eval WHERE line IN ('s1', 's2') AND gap_timing_s < 1 GROUP BY 1 ORDER BY 1
;;
-- OUT: 04_gap_agreement_by_lap_relation
SELECT lap_rel, band, COUNT(*) AS n_pairs,
       ROUND(MEDIAN(disagreement_s), 4) AS median_diff_s,
       ROUND(MEDIAN(ABS(disagreement_s)), 4) AS median_abs_diff_s,
       ROUND(QUANTILE_CONT(ABS(disagreement_s), 0.90), 4) AS p90_abs
FROM gap_eval WHERE line IN ('s1', 's2') GROUP BY 1, 2 ORDER BY 1, 2
;;
-- OUT: 04_incumbent_ff_distance_over_speed
-- For comparison: FastF1 DistanceToDriverAhead / own speed (the incumbent
-- conversion), only where FastF1's named car = the timing car ahead.
SELECT band, COUNT(gap_ff_dist_over_speed_s) AS n_pairs,
       ROUND(MEDIAN(gap_ff_dist_over_speed_s - gap_timing_s), 4) AS median_diff_s,
       ROUND(MEDIAN(ABS(gap_ff_dist_over_speed_s - gap_timing_s)), 4) AS median_abs_diff_s,
       ROUND(QUANTILE_CONT(ABS(gap_ff_dist_over_speed_s - gap_timing_s), 0.90), 4) AS p90_abs
FROM gap_eval WHERE line IN ('s1', 's2') GROUP BY 1 ORDER BY 1
;;
-- OUT: 04_pair_coverage
-- How many timing-line pairs survive the filters, and why do some lack a pos time?
SELECT line,
       COUNT(*) AS pairs_all,
       SUM(CASE WHEN t_pos IS NULL OR a_t_pos IS NULL THEN 1 ELSE 0 END) AS pairs_missing_pos_time,
       (SELECT COUNT(*) FROM gap_eval e WHERE e.line = g.line) AS pairs_evaluated
FROM gap_pairs AS g GROUP BY 1 ORDER BY 1
