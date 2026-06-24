-- Informational check (non-blocking) on stint cliffs and pace degradation.
-- Documents stints where cliff_lap_in_stint is detected but end-of-stint pace falloff is minimal.
-- This can occur when cliffs are early in the stint and the driver recovers, or when cliff
-- detection itself is noise. Not a failure condition, but useful for validation.
-- Placeholder: returns empty (passes) until this is wired up as an active warning/error check.
{{ config(tags=['placeholder']) }}

SELECT 1 WHERE FALSE
