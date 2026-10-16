{{ config(tags=['marts']) }}

-- CO-01 (T5). A pit-lane start (grid_position = 0) is not a grid slot, so
-- positions_gained must be NULL there, and must equal grid - finish elsewhere.
-- Fails per offending row, and once if no pit-lane start exists to check
-- (vacuity guard).
WITH r AS (
    SELECT race_id, driver_id, grid_position, finish_position
    FROM {{ ref('stg_results') }}
),

m AS (
    SELECT race_id, driver_id, positions_gained
    FROM {{ ref('mart_race_driver_summary') }}
)

SELECT 'pit_lane_start_has_value' AS failure, m.race_id, m.driver_id
FROM m INNER JOIN r USING (race_id, driver_id)
WHERE r.grid_position = 0 AND m.positions_gained IS NOT NULL

UNION ALL

SELECT 'grid_slot_mismatch' AS failure, m.race_id, m.driver_id
FROM m INNER JOIN r USING (race_id, driver_id)
WHERE r.grid_position >= 1
    AND m.positions_gained IS DISTINCT FROM r.grid_position - r.finish_position

UNION ALL

SELECT 'no_pit_lane_starts' AS failure, NULL, NULL
WHERE (
    SELECT COUNT(*) FROM m INNER JOIN r USING (race_id, driver_id)
    WHERE r.grid_position = 0
) = 0
