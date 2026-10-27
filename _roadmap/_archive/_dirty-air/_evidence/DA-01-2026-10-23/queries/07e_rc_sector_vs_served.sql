-- OUT: 07e_rc_sector_exceeds_served_layout
-- 2018-2020: does any race-control sector number exceed the number of marshal
-- sectors in the layout the API served for that race? (a layout mismatch signal)
WITH ms AS (
    SELECT race_id, race_slug, CAST(served_year AS INTEGER) AS served_year,
           CAST(NULLIF(marshal_sectors, '') AS INTEGER) AS n_ms
    FROM read_csv_auto('/private/tmp/claude-501/-Users-justin-github-off-the-pace/1fdfffb0-6280-4ac0-900e-471f09f2c9ba/scratchpad/da-01/out/07c_served_year_by_race_2018_2020.csv', all_varchar = true)
), rc AS (
    SELECT race_id, MAX(Sector) AS max_rc_sector, COUNT(*) AS sector_msgs
    FROM read_parquet('../data/bronze/race_control/*/*/*.parquet', hive_partitioning = true, union_by_name = true)
    WHERE Scope = 'Sector' AND season <= 2020 GROUP BY 1
)
SELECT ms.race_id, ms.race_slug, ms.served_year, ms.n_ms, rc.max_rc_sector, rc.sector_msgs
FROM ms LEFT JOIN rc USING (race_id)
WHERE rc.max_rc_sector > COALESCE(ms.n_ms, 0)
ORDER BY 1
