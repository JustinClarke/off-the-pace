-- WI-15a/W59 seed gate: the tyre_allocations seed carries 2019-2025, and its shape is pinned.
--
-- Returns one row per violation. Checks:
--   * per-season race count equals the declared count (2019-2024 = every ingested race;
--     2025 = 23, Miami absent -- a 2025 row added or dropped must change this list on purpose);
--   * no season outside 2019-2025 (W50: 2018 rows are never allowed, 2018 identity comes from
--     the lap name);
--   * stg_tyre_allocations holds exactly three rows per (race_year, circuit_key), one per
--     hard/medium/soft label;
--   * codes step strictly harder -> softer (hard < medium < soft), which every row of the
--     seed satisfies (2022 Australia C2/C3/C5 skips a code but still increases).
WITH expected(race_year, n_races) AS (
    VALUES (2019, 21), (2020, 17), (2021, 22), (2022, 22), (2023, 22), (2024, 24), (2025, 23)
),

seed_counts AS (
    SELECT CAST(race_year AS INTEGER) AS race_year, COUNT(*) AS n_races
    FROM {{ ref('tyre_allocations') }}
    GROUP BY 1
),

season_violations AS (
    SELECT
        CAST(COALESCE(e.race_year, s.race_year) AS VARCHAR) AS key,
        'seed race count ' || COALESCE(CAST(s.n_races AS VARCHAR), '0')
            || ' != expected ' || COALESCE(CAST(e.n_races AS VARCHAR), '0 (season not declared)') AS reason
    FROM expected AS e
    FULL OUTER JOIN seed_counts AS s ON e.race_year = s.race_year
    WHERE COALESCE(e.n_races, -1) != COALESCE(s.n_races, -1)
),

label_violations AS (
    SELECT
        CAST(race_year AS VARCHAR) || '/' || circuit_key AS key,
        'stg rows ' || CAST(COUNT(*) AS VARCHAR) || ' / distinct labels '
            || CAST(COUNT(DISTINCT compound_label) AS VARCHAR) || ' (expected 3 / 3)' AS reason
    FROM {{ ref('stg_tyre_allocations') }}
    GROUP BY race_year, circuit_key
    HAVING COUNT(*) != 3 OR COUNT(DISTINCT compound_label) != 3
),

order_violations AS (
    SELECT
        CAST(race_year AS VARCHAR) || '/' || circuit_key AS key,
        'codes not strictly hard < medium < soft: ' || hard_code || '/' || medium_code || '/' || soft_code AS reason
    FROM {{ ref('tyre_allocations') }}
    WHERE NOT (hard_code < medium_code AND medium_code < soft_code)
)

SELECT key, reason FROM season_violations
UNION ALL
SELECT key, reason FROM label_violations
UNION ALL
SELECT key, reason FROM order_violations
