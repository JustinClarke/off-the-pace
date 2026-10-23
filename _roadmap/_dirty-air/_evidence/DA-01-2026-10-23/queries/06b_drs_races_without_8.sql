-- OUT: 06b_races_without_drs8
SELECT c.race_year, c.race_id, ANY_VALUE(r.race_slug) AS race_slug,
       SUM(CASE WHEN drs = 8 THEN 1 ELSE 0 END) AS n8,
       SUM(CASE WHEN drs IN (10, 12, 14) THEN 1 ELSE 0 END) AS n_open,
       COUNT(*) AS n
FROM car_drs AS c LEFT JOIN (SELECT DISTINCT race_id, race_slug FROM dev.main.stg_results) AS r USING (race_id)
GROUP BY 1, 2 HAVING SUM(CASE WHEN drs = 8 THEN 1 ELSE 0 END) = 0 ORDER BY 1, 2
;;
-- OUT: 06b_drs8_2018_by_race
-- 2018 per race: share of 8 samples and activation-preceded-by-8 share.
SELECT e.race_id,
       SUM(CASE WHEN st = 'O' THEN 1 ELSE 0 END) AS activations,
       ROUND(AVG(CASE WHEN st = 'O' THEN CASE WHEN prev_st = 'E' THEN 1.0 ELSE 0 END END), 3) AS share_open_after_8,
       ROUND(AVG(CASE WHEN st = 'E' THEN CASE WHEN next_st = 'O' THEN 1.0 ELSE 0 END END), 3) AS share_8_then_open
FROM drs_ep2 AS e WHERE race_year = 2018 GROUP BY 1 ORDER BY 1
