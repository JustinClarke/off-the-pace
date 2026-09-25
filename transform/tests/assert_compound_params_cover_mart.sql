-- T5 (WI-02, F7). Every (venue, season, compound) a valid lap is priced on has
-- a compound seed cell -- refuse to build otherwise.
--
-- int_compound_cliff_predicted LEFT JOINs dim_compounds_season on
-- (track, season, compound). A lap with no cell used to be priced as an
-- invented one -- onset 999, severity 0, wear 0 -- so it read "never cliffs,
-- never wears", and that entered the label through compound_component_s: 1,624
-- valid 2025 laps (all of 2025_21's slicks, 2025_4's MEDIUM, 2025_13's
-- INTERMEDIATE), because no 2024 cell existed to carry forward for those pairs.
-- The fallback hierarchy is now explicit and marked in the seed
-- (fit_compound_cliff.py --fill-gaps: the latest earlier season's cell for the
-- venue and compound, else the class default, with per-parameter provenance),
-- and this test is what stops a new season reaching the marts before it has run.
--
-- Laps whose compound is itself unknown (stg_lap_tyre_qa's quarantine NULLs it)
-- have no cell to find and are out of scope; the curve prices them as NULL.

WITH needed AS (
    SELECT
        rt.track_id AS circuit_key,
        g.race_year AS season,
        g.compound_in_stint AS compound_code,
        COUNT(*) AS valid_laps
    FROM {{ ref('int_stint_geometry') }} AS g
    INNER JOIN {{ ref('race_to_track') }} AS rt ON g.race_id = rt.race_id
    WHERE g.is_valid_lap AND g.compound_in_stint IS NOT NULL
    GROUP BY 1, 2, 3
)

SELECT
    n.circuit_key,
    n.season,
    n.compound_code,
    n.valid_laps
FROM needed AS n
LEFT JOIN {{ ref('dim_compounds_season') }} AS cp
    ON
        n.circuit_key = cp.circuit_key
        AND n.season = cp.season
        AND n.compound_code = cp.compound_code
WHERE cp.circuit_key IS NULL
