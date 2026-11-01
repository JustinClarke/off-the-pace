-- No two drivers in one ghost scenario share a predicted finish position.
-- fct_ghost_race_finish ranks with RANK() and does not break ties, so tied
-- drivers get the same predicted_finish_position and the position after them
-- is skipped. p_beats_next is then NULL for every tied driver, because no row
-- is ranked exactly one place below them (see the model header). There are
-- 0 ties today; this test fails if a future build produces one, so the NULLs
-- cannot appear silently.
--
-- Returns one row per (race, host constructor, position) held by more than
-- one driver.

{{ config(severity='error') }}

SELECT
    race_year,
    race_id,
    host_constructor_id,
    predicted_finish_position,
    COUNT(*) AS n_drivers
FROM {{ ref('fct_ghost_race_finish') }}
GROUP BY race_year, race_id, host_constructor_id, predicted_finish_position
HAVING COUNT(*) > 1
