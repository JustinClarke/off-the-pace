-- dim_driver_seasons keeps one driver_id per season x driver code via MIN(DriverId).
-- MIN silently picks one value, so a (season, Abbreviation) that maps to two DriverIds
-- in bronze results would be hidden rather than surfaced. This test returns every such
-- group, so a DriverId conflict fails the build instead of being collapsed.
-- Name spellings (FullName) may legitimately differ within a group (ANT in 2025 has two
-- spellings and one DriverId), so they are deliberately not checked here.
SELECT
    CAST(season AS INTEGER) AS season,
    Abbreviation,
    COUNT(DISTINCT DriverId) AS n_driver_ids
FROM {{ source('bronze_f1', 'raw_results') }}
WHERE Abbreviation IS NOT NULL
GROUP BY CAST(season AS INTEGER), Abbreviation
HAVING COUNT(DISTINCT DriverId) > 1
