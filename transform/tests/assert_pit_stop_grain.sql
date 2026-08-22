-- stg_pits grain and pit-duration test.
-- Bronze puts PitInTime on the in-lap and PitOutTime on the following out-lap,
-- so a stop spans two lap rows. stg_pits collapses that to one row per stop
-- keyed on the in-lap; before 2026-08 it emitted both rows and derived
-- pit_duration_s from a single one, which made the column 97.6% NULL and
-- negative wherever it fired. These five checks pin the collapsed contract.

-- 1. Grain: every emitted row is the in-lap of a real stop. An out-lap-only
--    row (a pit-lane race start, or the exit half of a stop) must not survive.
SELECT
    'row_is_a_stop' AS check_name,
    lap_id,
    CAST(pit_in_lap_number AS VARCHAR) AS detail
FROM {{ ref('stg_pits') }}
WHERE pit_in_time_s IS NULL

UNION ALL

-- 2. The out-lap is always the very next lap. The old model hardcoded this
--    rather than reading it; it holds for every stop that has an out-lap.
SELECT
    'out_lap_is_next_lap' AS check_name,
    lap_id,
    CAST(pit_out_lap_number AS VARCHAR) AS detail
FROM {{ ref('stg_pits') }}
WHERE
    pit_out_lap_number IS NOT NULL
    AND pit_out_lap_number != pit_in_lap_number + 1

UNION ALL

-- 3. The three exit-side columns resolve together or not at all: a stop either
--    has an out-lap with a timestamp, or has no exit side.
SELECT
    'exit_side_resolves_together' AS check_name,
    lap_id,
    CAST(pit_out_lap_number AS VARCHAR) AS detail
FROM {{ ref('stg_pits') }}
WHERE
    (pit_out_lap_number IS NULL) != (pit_out_time_s IS NULL)
    OR (pit_out_lap_number IS NULL) != (pit_duration_s IS NULL)

UNION ALL

-- 4. Time runs forwards. The pre-2026-08 subtraction ran backwards on every
--    row it produced, so this is the check that would have caught it.
SELECT
    'duration_is_positive' AS check_name,
    lap_id,
    CAST(pit_duration_s AS VARCHAR) AS detail
FROM {{ ref('stg_pits') }}
WHERE pit_duration_s IS NOT NULL AND pit_duration_s <= 0

UNION ALL

-- 5. The duration is the two stamps it claims to be, not a proxy.
SELECT
    'duration_matches_stamps' AS check_name,
    lap_id,
    CAST(pit_duration_s AS VARCHAR) AS detail
FROM {{ ref('stg_pits') }}
WHERE
    pit_duration_s IS NOT NULL
    AND ABS(pit_duration_s - (pit_out_time_s - pit_in_time_s)) > 1e-6
