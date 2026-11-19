-- Pins the known races that have 'ok' laps with a NULL compound. Each such lap has a NULL
-- bronze compound (checked by assert_ok_null_compound_is_source_gap), so these are source gaps,
-- not transform defects. Staging maps FastF1 'None'/'nan' to NULL and does not invent a
-- compound. Example: 2025_13 has compound 'None' and TyreLife null for the whole third stint of
-- ALO, ANT, COL and HUL (57 laps, out-lap to end of race).
-- Any NULL-compound 'ok' lap in a race outside this list is a new gap and must be reviewed,
-- documented (KNOWN_THIN in ingestion/src/bronze_checks.py) and added here on purpose.
-- Returns one row per unexpected lap.

SELECT
    lap_id AS key,
    'unexpected NULL compound on ok lap in race ' || race_id AS reason
FROM {{ ref('stg_lap_tyre_qa') }}
WHERE tyre_qa_status = 'ok'
  AND compound IS NULL
  AND race_id NOT IN (
      '2018_5', '2018_13', '2018_18',
      '2021_12',
      '2022_7', '2022_11',
      '2023_8',
      '2025_13',
      '2026_11'
  )
