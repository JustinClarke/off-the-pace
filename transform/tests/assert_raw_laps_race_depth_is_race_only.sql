-- F19 (WI-09). No file the race-lap glob reads declares a session other than the
-- race: a `session_type` column, if a race-depth file has one, holds 'R' or NULL.
--
-- bronze_f1.raw_laps globs laps/*/*/*.parquet. Race files carry no session_type
-- column today, so the only thing keeping qualifying (session=Q/, one level
-- deeper) and any future practice or sprint session out of stg_laps is directory
-- depth. The source description used to claim the opposite -- that a session_type
-- column existed and stg_laps coalesced it to 'R' -- and no such code was ever
-- written, so an engineer landing FP1-3 ingestion (02f) could reasonably have
-- skipped building the guard. This is that guard: it reads the raw files, not
-- stg_laps, and fails the moment a race-depth file announces itself as another
-- session, before the laps are mixed into the race set.
--
-- unique(stg_laps.lap_id) is the complementary check for a second session written
-- with no marker at all: it collides on (season, race, driver, lap).
--
-- Reads with union_by_name so a session_type column present in ANY file is seen
-- even when the first file lacks it (a plain glob read takes the first file's
-- schema and would silently drop it). The value is pulled from the row as JSON so
-- the query binds, and returns nothing, while no file has the column: the state
-- today, 173 race-depth files with none. `filename` names the offending file.

SELECT DISTINCT
    t.filename,
    JSON_EXTRACT_STRING(TO_JSON(t), '$.session_type') AS session_type
FROM read_parquet(
    {{ source('bronze_f1', 'raw_laps') }},
    union_by_name = TRUE,
    filename = TRUE
) AS t
WHERE
    JSON_EXTRACT_STRING(TO_JSON(t), '$.session_type') IS NOT NULL
    AND JSON_EXTRACT_STRING(TO_JSON(t), '$.session_type') <> 'R'
