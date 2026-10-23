-- OUT: 05_valid_share_by_season
-- DA-01 step 5. Gate 1 at SAMPLE grain: share of green position samples that
-- are "valid" under each candidate reading of the design note's v_i.
-- Each green sample takes the crossing-order car ahead of its own 1% bin
-- crossing (xorder, step 3). Time-weighted shares use dt capped at 1 s, the
-- design note's exposure weight.
WITH s AS (
    SELECT p.race_year, LEAST(COALESCE(p.dt_s, 0), 1.0) AS w,
           p.ff_ahead_driver_id, p.distance_to_ahead_m,
           x.lap_relation, x.gap_ahead_s
    FROM pos_flags AS p
    LEFT JOIN xorder AS x
      ON p.race_id = x.race_id AND p.driver_id = x.driver_id AND p.lap_number = x.lap_number
     AND CAST(FLOOR(p.relative_distance * 100) AS INTEGER) = x.track_bin
    WHERE p.is_green
)
SELECT race_year, COUNT(*) AS green_samples,
       -- A: FastF1 field present (DriverAhead resolved and distance not NULL)
       ROUND(AVG(CASE WHEN ff_ahead_driver_id IS NOT NULL AND distance_to_ahead_m IS NOT NULL THEN 1.0 ELSE 0 END), 4) AS a_ff_known,
       -- B: crossing-order car ahead exists (not alone / not > 300 s)
       ROUND(AVG(CASE WHEN lap_relation IN ('same_lap', 'self_is_lapped_ahead_is_lapping_car', 'ahead_is_lapped_car') THEN 1.0 ELSE 0 END), 4) AS b_track_ahead_known,
       -- C: design note literal: known AND the car ahead is not a lapped car (any distance)
       ROUND(AVG(CASE WHEN lap_relation IN ('same_lap', 'self_is_lapped_ahead_is_lapping_car') THEN 1.0 ELSE 0 END), 4) AS c_known_not_lapped_ahead,
       -- D: as C, but a lapped car ahead counts as invalid only when within 3 s (beyond 3 s it is the reference band anyway)
       ROUND(AVG(CASE WHEN lap_relation IN ('same_lap', 'self_is_lapped_ahead_is_lapping_car')
                       OR (lap_relation = 'ahead_is_lapped_car' AND gap_ahead_s >= 3) THEN 1.0 ELSE 0 END), 4) AS d_lapped_within_3s_invalid,
       ROUND(SUM(CASE WHEN lap_relation IN ('same_lap', 'self_is_lapped_ahead_is_lapping_car') THEN w ELSE 0 END) / SUM(w), 4) AS c_time_weighted,
       ROUND(AVG(CASE WHEN lap_relation IS NULL THEN 1.0 ELSE 0 END), 5) AS share_bin_not_all_green_or_missing
FROM s GROUP BY ROLLUP(1) ORDER BY 1
