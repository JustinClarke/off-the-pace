-- OUT: 07d_race_control_sector_flags_by_season
-- Do race-control messages carry a marshal sector for local yellows? (bronze
-- raw_race_control; Scope='Sector' with a Sector number.)
SELECT season AS race_year, COUNT(DISTINCT race_id) AS races,
       SUM(CASE WHEN Scope = 'Sector' THEN 1 ELSE 0 END) AS sector_scope_msgs,
       SUM(CASE WHEN Scope = 'Sector' AND Flag IN ('YELLOW', 'DOUBLE YELLOW') THEN 1 ELSE 0 END) AS sector_yellow_msgs,
       SUM(CASE WHEN Scope = 'Sector' AND Sector IS NULL THEN 1 ELSE 0 END) AS sector_scope_missing_number,
       MAX(Sector) AS max_sector_number,
       COUNT(DISTINCT CASE WHEN Scope = 'Sector' AND Flag IN ('YELLOW', 'DOUBLE YELLOW') THEN race_id END) AS races_with_sector_yellows
FROM read_parquet('../data/bronze/race_control/*/*/*.parquet', hive_partitioning = true, union_by_name = true)
GROUP BY 1 ORDER BY 1
