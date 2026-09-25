-- A silently failed seed join must be catchable on the priced output, not just on the
-- seed table's own coverage.
--
-- F34: the old body flagged `expected_compound_pace_s = 0.0 OR = 0.5` -- two sentinels
-- left over from 08m's COALESCE(999, 0, 0) fallback, which was removed when F7 landed
-- (int_compound_cliff_predicted.sql now passes seed columns through as NULL when a lap
-- has no cell, per its own header note). No row has been exactly 0.0 or 0.5 since, so
-- the old body has been vacuously green regardless of whether a join actually works.
--
-- It also could never have been reliably fixed by widening the literal to a range:
-- `expected_compound_pace_s` is NOT a stable sentinel to test even for a genuinely
-- cell-less lap -- it is COALESCE(grip_peak, 0.0) + wear + 0.005*ambient_temp_delta,
-- so a cell-less row's value moves with the weather (grip/wear terms drop to 0, but
-- the temperature term does not). Checking IT directly was tried and produces false
-- positives besides: on a lap with a real seed cell but an UNKNOWN tyre age,
-- expected_compound_pace_s is correctly NULL by F39's own NULL-safety design (age
-- unknown -> wear unknown -> total unknown), which is a different, already-covered
-- condition (assert_no_cap_valued_wear, T29) and not a failed join at all -- 19 such
-- rows exist on the 2026-09-25 dev build (2025_13 SAI, 2025_1 BEA) with real fitted
-- onset/severity/gradient values but a NULL age.
--
-- What is stable, and what actually distinguishes "no cell" from "cell, unknown age",
-- is the seed-derived columns themselves: a slick-compound lap (SOFT/MEDIUM/HARD -- the
-- only compounds this model prices, per int_compound_cliff_predicted.sql's header)
-- whose compound_cliff_onset_laps comes back NULL has no seed cell at all, independent
-- of whether the tyre age is known. assert_compound_params_cover_mart (T5, WI-02, F7)
-- already guarantees dim_compounds_season itself has a cell for every (venue, season,
-- compound) a valid lap needs; this test guards the JOIN that is supposed to reach it,
-- catching a key mismatch even when the seed table is, by that other test's own
-- measure, complete.
SELECT
    compound,
    race_id,
    lap_id
FROM {{ ref('int_compound_cliff_predicted') }}
WHERE
    compound IN ('SOFT', 'MEDIUM', 'HARD')
    AND compound_cliff_onset_laps IS NULL
