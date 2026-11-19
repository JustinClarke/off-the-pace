-- 2025 Miami (race_id 2025_6): the racing pit stops in stg_pits agree with the independent
-- Jolpica pit-stop record for the same round. Jolpica lists 18 stops, one per in-lap.
-- stg_pits has the same 18 racing stops (a pit-in with an out-lap); its extra row, LAW lap 36,
-- is an in-only record on his final lap and is excluded here. Compared as a multiset of
-- in-lap numbers, because driver codes differ between the two sources.
-- Returns one row per lap where the two counts disagree.

WITH jolpica AS (
    SELECT CAST(lap AS INTEGER) AS in_lap, COUNT(*) AS n_stops
    FROM read_parquet('{{ var("bronze_base", "../data/bronze") }}/reference/jolpica/pit_stops/season=2025/round=6/pit_stops.parquet')
    GROUP BY 1
),

stg AS (
    SELECT pit_in_lap_number AS in_lap, COUNT(*) AS n_stops
    FROM {{ ref('stg_pits') }}
    WHERE race_id = '2025_6' AND pit_out_lap_number IS NOT NULL
    GROUP BY 1
)

SELECT
    CAST(COALESCE(j.in_lap, s.in_lap) AS VARCHAR) AS key,
    'jolpica stops ' || CAST(COALESCE(j.n_stops, 0) AS VARCHAR)
        || ' != stg_pits stops ' || CAST(COALESCE(s.n_stops, 0) AS VARCHAR) AS reason
FROM jolpica AS j
FULL OUTER JOIN stg AS s ON j.in_lap = s.in_lap
WHERE COALESCE(j.n_stops, 0) != COALESCE(s.n_stops, 0)
