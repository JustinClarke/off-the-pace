-- DA-01 step 6. DRS code 8 reliability. DRS is a car-channel signal, so this
-- reads bronze raw_telemetry Source='car' directly (stg_telemetry projects it
-- but only drs_active). Codes: 0/1 off, 8 = eligible (detected within 1 s,
-- not yet open), 10/12/14 = open.
CREATE OR REPLACE TABLE car_drs AS
SELECT CAST(season AS INTEGER) AS race_year, CAST(race_id AS VARCHAR) AS race_id,
       CAST(driver_id AS VARCHAR) AS driver_id, CAST(lap_number AS INTEGER) AS lap_number,
       CAST(SessionTime AS DOUBLE) / 1e9 AS session_time_s, CAST(DRS AS INTEGER) AS drs,
       CAST(speed_kph AS DOUBLE) AS speed_kph
FROM read_parquet('../data/bronze/telemetry/*/*/*.parquet', hive_partitioning = true, union_by_name = true)
WHERE Source = 'car'
;;
-- OUT: 06_drs_code_distribution_by_season
SELECT race_year, COUNT(*) AS car_samples,
       ROUND(AVG(CASE WHEN drs IN (0, 1) THEN 1.0 ELSE 0 END), 4) AS share_0_1,
       ROUND(AVG(CASE WHEN drs = 2 THEN 1.0 ELSE 0 END), 5) AS share_2,
       ROUND(AVG(CASE WHEN drs = 3 THEN 1.0 ELSE 0 END), 5) AS share_3,
       ROUND(AVG(CASE WHEN drs = 8 THEN 1.0 ELSE 0 END), 4) AS share_8,
       ROUND(AVG(CASE WHEN drs IN (10, 12, 14) THEN 1.0 ELSE 0 END), 4) AS share_open_10_12_14,
       ROUND(AVG(CASE WHEN drs NOT IN (0, 1, 2, 3, 8, 10, 12, 14) OR drs IS NULL THEN 1.0 ELSE 0 END), 5) AS share_other_or_null,
       COUNT(DISTINCT CASE WHEN drs = 8 THEN race_id END) AS races_with_8,
       COUNT(DISTINCT race_id) AS races
FROM car_drs GROUP BY 1 ORDER BY 1
;;
-- DRS episodes: maximal runs of consecutive samples with the same state class
-- (off / eligible-8 / open) per driver. An "open" episode is an activation.
CREATE OR REPLACE TABLE drs_ep AS
WITH c AS (
    SELECT *, CASE WHEN drs = 8 THEN 'E' WHEN drs IN (10, 12, 14) THEN 'O' ELSE 'X' END AS st
    FROM car_drs
), r AS (
    SELECT *, CASE WHEN st <> LAG(st) OVER w OR LAG(st) OVER w IS NULL THEN 1 ELSE 0 END AS chg
    FROM c WINDOW w AS (PARTITION BY race_id, driver_id ORDER BY session_time_s, lap_number)
), g AS (
    SELECT *, SUM(chg) OVER (PARTITION BY race_id, driver_id ORDER BY session_time_s, lap_number
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS ep
    FROM r
)
SELECT race_year, race_id, driver_id, ep, ANY_VALUE(st) AS st, MIN(lap_number) AS lap_number,
       MIN(session_time_s) AS t_start, MAX(session_time_s) AS t_end, COUNT(*) AS n
FROM g GROUP BY 1, 2, 3, 4
;;
CREATE OR REPLACE TABLE drs_ep2 AS
SELECT *, LAG(st) OVER w AS prev_st, LAG(t_end) OVER w AS prev_t_end,
       LEAD(st) OVER w AS next_st
FROM drs_ep WINDOW w AS (PARTITION BY race_id, driver_id ORDER BY ep)
;;
-- OUT: 06_drs_activation_preceded_by_8
-- Of every activation (open episode), how many come straight out of an
-- eligible-8 episode? And of every 8 episode, how many end in an opening?
SELECT race_year,
       SUM(CASE WHEN st = 'O' THEN 1 ELSE 0 END) AS activations,
       ROUND(AVG(CASE WHEN st = 'O' THEN CASE WHEN prev_st = 'E' THEN 1.0 ELSE 0 END END), 4) AS share_open_preceded_by_8,
       SUM(CASE WHEN st = 'E' THEN 1 ELSE 0 END) AS eligible_episodes,
       ROUND(AVG(CASE WHEN st = 'E' THEN CASE WHEN next_st = 'O' THEN 1.0 ELSE 0 END END), 4) AS share_8_followed_by_open,
       ROUND(MEDIAN(CASE WHEN st = 'E' THEN t_end - t_start END), 2) AS median_8_episode_s,
       ROUND(AVG(CASE WHEN st = 'O' AND lap_number <= 2 THEN 1.0 WHEN st = 'O' THEN 0.0 END), 4) AS share_activations_on_lap_1_2
FROM drs_ep2 GROUP BY 1 ORDER BY 1
;;
-- OUT: 06_drs8_vs_timing_gap
-- External check: is the car within ~1 s of the car ahead (TIMING feed, S1/S2
-- line gap from step 4) when 8 is showing? For every green timing-line pair,
-- the car's DRS state at the line instant (asof car sample) vs timing gap.
-- Line instants are not DRS detection points, so this is a consistency check,
-- not a detection-point test.
WITH g AS (
    SELECT race_year, race_id, driver_id, t_line, gap_timing_s
    FROM gap_eval WHERE line IN ('s1', 's2')
), j AS (
    SELECT g.*, c.drs
    FROM g ASOF LEFT JOIN car_drs AS c
      ON g.race_id = c.race_id AND g.driver_id = c.driver_id AND g.t_line >= c.session_time_s
)
SELECT race_year,
       SUM(CASE WHEN drs = 8 THEN 1 ELSE 0 END) AS line_crossings_showing_8,
       ROUND(MEDIAN(CASE WHEN drs = 8 THEN gap_timing_s END), 3) AS median_timing_gap_when_8,
       ROUND(AVG(CASE WHEN drs = 8 THEN CASE WHEN gap_timing_s < 1.2 THEN 1.0 ELSE 0 END END), 4) AS share_8_with_gap_lt_1_2s,
       ROUND(AVG(CASE WHEN drs = 8 THEN CASE WHEN gap_timing_s > 2.0 THEN 1.0 ELSE 0 END END), 4) AS share_8_with_gap_gt_2s,
       ROUND(AVG(CASE WHEN gap_timing_s >= 3 THEN CASE WHEN drs IN (8, 10, 12, 14) THEN 1.0 ELSE 0 END END), 4) AS share_gap_ge_3s_showing_8_or_open
FROM j GROUP BY 1 ORDER BY 1
