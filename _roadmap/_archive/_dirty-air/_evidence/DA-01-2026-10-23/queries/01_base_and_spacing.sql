-- DA-01 step 1. Position-channel base table and sample spacing per season.
-- Source: dev.main.stg_telemetry_position (dbt view over bronze raw_telemetry,
-- Source='pos', RelativeDistance NOT NULL). dt = time to the driver's next
-- position sample in the same race (ordered by session clock, lap, rel dist).
CREATE OR REPLACE TABLE pos AS
SELECT
    p.*,
    LEAD(p.session_time_s) OVER w - p.session_time_s AS dt_s,
    ROW_NUMBER() OVER w AS rn
FROM dev.main.stg_telemetry_position AS p
WINDOW w AS (
    PARTITION BY p.race_id, p.driver_id
    ORDER BY p.session_time_s, p.lap_number, p.relative_distance
)
;;
-- OUT: 01_coverage_by_season
SELECT race_year,
       COUNT(DISTINCT race_id) AS races,
       COUNT(DISTINCT race_id || driver_id) AS race_drivers,
       COUNT(*) AS pos_samples,
       ROUND(AVG(CASE WHEN track_status = 'OnTrack' THEN 1 ELSE 0 END), 4) AS share_ontrack
FROM pos GROUP BY 1 ORDER BY 1
;;
-- OUT: 01_spacing_by_season
-- On-track samples only, dt capped nowhere here (raw); share_gt_1s shows the cap's reach.
SELECT race_year,
       COUNT(*) AS n_dt,
       ROUND(QUANTILE_CONT(dt_s, 0.01), 3) AS p01,
       ROUND(QUANTILE_CONT(dt_s, 0.10), 3) AS p10,
       ROUND(MEDIAN(dt_s), 3) AS p50,
       ROUND(AVG(dt_s), 3) AS mean,
       ROUND(QUANTILE_CONT(dt_s, 0.90), 3) AS p90,
       ROUND(QUANTILE_CONT(dt_s, 0.99), 3) AS p99,
       ROUND(AVG(CASE WHEN dt_s = 0 THEN 1 ELSE 0 END), 5) AS share_dt_zero,
       ROUND(AVG(CASE WHEN dt_s > 0.5 THEN 1 ELSE 0 END), 5) AS share_gt_0_5s,
       ROUND(AVG(CASE WHEN dt_s > 1.0 THEN 1 ELSE 0 END), 5) AS share_gt_1s
FROM pos
WHERE dt_s IS NOT NULL AND track_status = 'OnTrack'
GROUP BY 1 ORDER BY 1
;;
-- OUT: 01_spacing_race_medians_by_season
-- Spread of the per-race median spacing inside each season (is it one cadence?).
WITH r AS (
    SELECT race_year, race_id, MEDIAN(dt_s) AS med, QUANTILE_CONT(dt_s, 0.9) AS p90
    FROM pos WHERE dt_s IS NOT NULL AND track_status = 'OnTrack' GROUP BY 1, 2
)
SELECT race_year, COUNT(*) AS races,
       ROUND(MIN(med), 3) AS min_race_median, ROUND(MEDIAN(med), 3) AS median_race_median,
       ROUND(MAX(med), 3) AS max_race_median,
       ROUND(MIN(p90), 3) AS min_race_p90, ROUND(MAX(p90), 3) AS max_race_p90
FROM r GROUP BY 1 ORDER BY 1
;;
-- OUT: 01_spacing_histogram_by_season
-- dt in 20 ms buckets (on track), share within season; top buckets only.
WITH h AS (
    SELECT race_year, ROUND(dt_s / 0.02) * 0.02 AS dt_bucket, COUNT(*) AS n
    FROM pos WHERE dt_s IS NOT NULL AND track_status = 'OnTrack' GROUP BY 1, 2
), s AS (
    SELECT *, n / SUM(n) OVER (PARTITION BY race_year) AS share,
           ROW_NUMBER() OVER (PARTITION BY race_year ORDER BY n DESC) AS k
    FROM h
)
SELECT race_year, ROUND(dt_bucket, 2) AS dt_bucket_s, n, ROUND(share, 4) AS share
FROM s WHERE k <= 6 ORDER BY race_year, k
