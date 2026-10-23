-- OUT: 07b_race_slugs
SELECT DISTINCT race_year, race_id, race_slug FROM dev.main.stg_results
WHERE race_year <= 2020 ORDER BY 1, CAST(SPLIT_PART(race_id, '_', 2) AS INTEGER)
