-- Second iteration: Informational check (non-blocking) on stint cliffs and pace degradation.
-- Documents stints where cliff_lap_in_stint is detected but end-of-stint pace falloff is minimal.
-- This can occur when cliffs are early in the stint and driver recovers, or when
-- cliff detection is noise. Not a failure condition, but useful for validation.
-- Placeholder: returns empty (passes) for second iteration. Will be upgraded to warning/error in fourth iteration.

SELECT 1 WHERE FALSE
