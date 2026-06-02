-- Safety-car hazard history: per-lap hazard rates must be valid probabilities
--
-- sc/vsc/any hazard-per-lap (raw and shrunk) are onset counts divided by racing
-- laps, i.e. per-lap probabilities. Each must lie in [0, 1]; the combined
-- "any" hazard must be at least as large as each component (an SC or VSC onset
-- is an "any" onset). A violation means a miscount, a bad denominator, or a
-- shrinkage prior pushing a rate out of range.
-- Tolerance: floating-point epsilon (1e-9).
-- Gate: YES bug if any rows returned.

SELECT
    circuit_slug,
    sc_hazard_per_lap,
    vsc_hazard_per_lap,
    any_hazard_per_lap,
    sc_hazard_per_lap_shrunk,
    vsc_hazard_per_lap_shrunk,
    any_hazard_per_lap_shrunk
FROM {{ ref('int_sc_hazard_history') }}
WHERE sc_hazard_per_lap < 0 OR sc_hazard_per_lap > 1
    OR vsc_hazard_per_lap < 0 OR vsc_hazard_per_lap > 1
    OR any_hazard_per_lap < 0 OR any_hazard_per_lap > 1
    OR sc_hazard_per_lap_shrunk < 0 OR sc_hazard_per_lap_shrunk > 1
    OR vsc_hazard_per_lap_shrunk < 0 OR vsc_hazard_per_lap_shrunk > 1
    OR any_hazard_per_lap_shrunk < 0 OR any_hazard_per_lap_shrunk > 1
    OR any_hazard_per_lap < sc_hazard_per_lap - 1e-9
    OR any_hazard_per_lap < vsc_hazard_per_lap - 1e-9
