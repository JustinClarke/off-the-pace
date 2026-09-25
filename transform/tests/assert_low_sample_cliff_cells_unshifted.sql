-- WI-13 (T29's data half for cliff_onset_shift_laps). A constructor-season-compound
-- cell without enough post-onset evidence (is_low_sample_cliff) has
-- cliff_onset_shift_laps = 0: it keeps the field's cliff timing, as
-- int_constructor_deg_sensitivity documents ("non-qualifying cells get
-- cliff_onset_shift_laps = 0 (field-timed cliff)"). Never NULL: the ghost-car
-- recombination reads it for every cell.
--
-- A compound-season with no post-onset clean laps at all has no ref_depth, so the
-- shift's mapping is NULL there. The clip used to be LEAST(GREATEST(..., -3.0), 3.0),
-- and DuckDB's GREATEST skips a NULL argument, so such a cell came out at -3.0 --
-- the HARSHEST shift, a cliff three laps early -- instead of 0: 2018 Renault HARD
-- on the 2026-09-24 dev build, 1 of 233 cells. -3.0 is inside the documented
-- clip, so no range test could see it.

SELECT
    deg_sensitivity_id,
    is_low_sample_cliff,
    cliff_ref_depth_laps,
    cliff_onset_shift_laps
FROM {{ ref('int_constructor_deg_sensitivity') }}
WHERE
    is_low_sample_cliff
    AND (cliff_onset_shift_laps IS NULL OR cliff_onset_shift_laps <> 0.0)
