-- A phase's z-score must only be populated once its cell count clears
-- PHASE_MIN_CELLS=30, and corner_skill_index (a straight sum of the three
-- z-scores) must only be populated once all three clear their own floor --
-- this is the per-phase composite gate the corner-skill mart's
-- teammate-differential design depends on (see mart_corner_skill_driver.sql
-- header).
SELECT race_year, driver_id, braking_cells_n, mid_cells_n, exit_cells_n
FROM {{ ref('mart_corner_skill_driver') }}
WHERE
    (braking_skill_z IS NOT NULL AND braking_cells_n < 30)
    OR (mid_corner_skill_z IS NOT NULL AND mid_cells_n < 30)
    OR (exit_skill_z IS NOT NULL AND exit_cells_n < 30)
    OR (
        corner_skill_index IS NOT NULL
        AND (
            braking_skill_z IS NULL
            OR mid_corner_skill_z IS NULL
            OR exit_skill_z IS NULL
        )
    )
