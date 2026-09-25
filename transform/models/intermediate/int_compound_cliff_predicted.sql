-- Layer 04: Expected compound pace and cliff prediction.
-- Hockey-stick pace model: grip_peak + linear wear + a SATURATING post-onset
-- cliff ramp, bounded, + a temperature offset.
--
-- All coefficients are sourced from dim_compounds_season, which is FITTED by
-- transform/tasks/coefficients/fit_compound_cliff.py + survival.py (Kaplan-Meier
-- survival for cliff onset, wind-controlled OLS for the wear gradient, a pre/post
-- window mean difference for severity). The header note that stood here until
-- 2026-09-16 -- "placeholder values until Python RANSAC estimation rewrites the
-- seed" -- was stale: the seed was refit on 2026-07-30 and again on 2026-09-08,
-- and nobody updated the comment. Removed per work item 08l's correction.
-- ambient_temp_delta = track_temp-compound_optimal_temp_low, clipped [0,30].
{{ config(materialized='table') }}

-- 08m. compound_cliff_severity is FIT as a level shift, not as a rate:
-- survival.py::estimate_cliff_severity returns post.mean() - pre.mean() over
--   pre  = age in [onset-5, onset-1]  (5 laps, centroid onset - 3.0)
--   post = age in [onset,   onset+5]  (6 laps, centroid onset + 2.5)
-- i.e. the TOTAL pace change across onset between two centroids 5.5 laps apart.
-- Until 08m this model multiplied that number by laps_past_cliff -- unbounded,
-- reaching 48 -- which charged a ~5.5-lap magnitude once per lap. That single
-- term was 60.4% of the seed's contribution to the ML target (08l).

WITH geom AS (
    SELECT
        stint_id,
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        age_in_stint,
        compound_in_stint AS compound
    FROM {{ ref('int_stint_geometry') }}
    -- int_stint_geometry now carries the full chronological sequence
    -- (SC/VSC/pit/invalid laps included); this model outputs expected
    -- pace so it must stay valid-lap-only, or it prices SC/pit laps as if
    -- they were racing laps.
    WHERE is_valid_lap = TRUE
),

race_map AS (
    SELECT race_id, track_id FROM {{ ref('race_to_track') }}
),

compound_params AS (
    SELECT * FROM {{ ref('dim_compounds_season') }}
),

weather AS (
    -- stg_weather is per-driver (one row per lap_id); multiple drivers share
    -- a (race_year, race_id, lap_number) but can ASOF-match different weather
    -- samples near a sample boundary, so ties on the DISTINCT ON key are real
    -- (verified: up to 20 rows per key, ~46% with differing track_temp_c).
    -- Tiebreak explicitly or DuckDB's pick varies with scan order/parallelism.
    SELECT DISTINCT ON (race_year, race_id, lap_number)
        race_year,
        race_id,
        lap_number,
        track_temp_c
    FROM {{ ref('stg_weather') }}
    ORDER BY
        race_year ASC,
        race_id ASC,
        lap_number ASC,
        weather_session_time_s DESC,
        driver_id ASC
),

combined AS (
    SELECT
        g.stint_id,
        g.lap_id,
        g.race_year,
        g.race_id,
        g.driver_id,
        g.lap_number,
        g.lap_in_stint,
        g.age_in_stint,
        g.compound,
        rm.track_id,
        w.track_temp_c,
        cp.compound_cliff_onset_laps,
        cp.compound_cliff_severity,
        cp.compound_wear_gradient,
        cp.compound_grip_peak,
        cp.compound_optimal_temp_low
    FROM geom AS g
    -- INNER on purpose, and never a silent drop (F8): a race with no track
    -- slug has no seed cell to price. assert_race_to_track_covers_all_races
    -- (T4) fails the build if any stg_laps race is missing from race_to_track
    -- -- as 2018_14 (927 laps) was until WI-05.
    INNER JOIN race_map AS rm
        ON g.race_id = rm.race_id
    LEFT JOIN compound_params AS cp
        ON
            rm.track_id = cp.circuit_key
            AND g.race_year = cp.season
            AND g.compound = cp.compound_code
    LEFT JOIN weather AS w
        ON
            g.race_year = w.race_year
            AND g.race_id = w.race_id
            AND g.lap_number = w.lap_number
),

with_pace AS (
    SELECT
        *,
        -- Temperature delta from compound optimum, clipped to [0, 30]
        LEAST(
            GREATEST(
                COALESCE(track_temp_c, 30.0)
                - COALESCE(compound_optimal_temp_low, 20.0),
                0.0
            ),
            30.0
        )
            AS ambient_temp_delta,
        -- Laps past cliff onset (0 before onset). NULL when the tyre age is
        -- unknown (F39): DuckDB's GREATEST skips NULL, so the bare
        -- GREATEST(NULL - onset, 0.0) read "no cliff yet" instead of "unknown".
        CASE
            WHEN age_in_stint IS NULL THEN NULL
            ELSE GREATEST(
                CAST(age_in_stint AS DOUBLE)
                - COALESCE(compound_cliff_onset_laps, 999.0),
                0.0
            )
        END
            AS laps_past_cliff,
        age_in_stint > COALESCE(compound_cliff_onset_laps, 999.0)
            AS cliff_onset_passed
    FROM combined
)

SELECT
    stint_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    lap_in_stint,
    age_in_stint,
    compound,
    cliff_onset_passed,
    -- Field cliff parameters exposed for the ghost-car cliff interaction term
    -- (host/ego onset shift): onset (laps) and severity from dim_compounds_season.
    -- NOTE (08m): compound_cliff_severity is in SECONDS -- a level shift across
    -- the onset, measured over a ~5.5-lap window. It is NOT s/lap^2, as this
    -- comment claimed until 2026-09-16, and consumers must not multiply it by a
    -- lap count. See the with_cliff CTE above for the licensed consumption.
    --
    -- F7: passed through as-is, NULL when the lap has no seed cell. They were
    -- COALESCEd to 999 / 0 / 0, which published an invented cell ("never
    -- cliffs, never wears") for every lap the seed did not cover. Every
    -- (venue, season, compound) a valid lap needs now has a cell or the build
    -- stops (assert_compound_params_cover_mart), so the only cell-less laps
    -- left are those whose compound is itself unknown (stg_lap_tyre_qa's
    -- quarantine), and unknown is what they now say.
    compound_cliff_onset_laps,
    compound_cliff_severity,
    -- 08m: exposed deliberately alongside severity. Any consumer that needs a
    -- post-onset RATE needs BOTH -- severity alone is a level shift and the
    -- de-double-count against wear_gradient is what turns it into one. Use the
    -- cliff_ramp_slope_s_per_lap() macro rather than re-deriving it.
    compound_wear_gradient,
    -- The age-dependent wear portion, bounded. Exposed as its own column so
    -- the bound is assertable without re-deriving it from the pace total.
    -- NULL exactly when the tyre age is unknown (F39; see the macro), never
    -- the bound: assert_no_cap_valued_wear holds it there.
    {{ compound_cliff_wear_s('compound_wear_gradient',
                             'compound_cliff_severity',
                             'age_in_stint',
                             'laps_past_cliff') }} AS compound_wear_s,
    -- Hockey-stick pace model:
    -- grip_peak baseline + linear wear + the saturating post-onset cliff ramp.
    --
    -- 08m removed two terms that were never entitled to be here:
    --   * the 0.002*age^2 quadratic -- a literal constant, identical across all
    --     438 circuit x compound x season cells, never fitted against anything,
    --     and 18.9% of the seed's contribution to the ML target. It is already
    --     absorbed by the linear term: _fit_wear_slope_with_wind fits
    --     pace ~ [1, age, wind] with NO quadratic in the design matrix, so the
    --     fitted slope carries whatever average curvature its window contains.
    --     Charging a second curvature term on top double-counts by construction.
    --     It was worth 1.8 s at age 30 and 4.5 s at age 50, identically for a
    --     HARD and a HYPERSOFT tyre.
    --   * cliff_severity * laps_past_cliff -- see macros/compound_cliff_wear.sql.
    --
    -- BOUNDED at var('compound_wear_max_s_per_lap') on the age-dependent terms
    -- only -- grip_peak and the temperature offset are per-lap constants and do
    -- not run away. Unbounded, this polynomial emitted up to 93.5 s/lap on laps
    -- that were actually run (p99 30.8, 12,575 rows over the bound across 1,604
    -- of 7,094 stints, mean excess 8.6 s).
    --
    -- This is not a cosmetic bound. expected_compound_pace_s is subtracted into
    -- driver_skill_residual_s in int_lap_residual_decomposed, so an over-large
    -- wear term over-explains the lap and *depresses* the residual. Both ML
    -- targets are built on that residual as a forward difference:
    --   * laps_until_cliff_class scans for the residual RISING > 1.0 s, so a
    --     depressed future lap hides a crossing that happened. Re-deriving the
    --     label under this bound moves 6,825 rows (4.97%), and 99.5% of them
    --     move out of 'none_in_stint' into a real cliff class -- the tail was
    --     erasing cliffs into the majority class, not inventing them.
    --   * next_lap_degradation_jump_detrended_s moves on 9.05% of rows, max
    --     9.08 s, and its sd falls 2.5321 -> 2.4948.
    --
    -- The wear term is the same macro as compound_wear_s, so this total is
    -- NULL when the tyre age is unknown (F39) rather than grip + 10 s + temp.
    COALESCE(compound_grip_peak, 0.0)
    + {{ compound_cliff_wear_s('compound_wear_gradient',
                               'compound_cliff_severity',
                               'age_in_stint',
                               'laps_past_cliff') }}
    + 0.005 * ambient_temp_delta AS expected_compound_pace_s,
    -- First derivative: rate of pace loss at current age.
    -- 08m: this column carried a THIRD defect 08l did not report -- it added the
    -- full compound_cliff_severity on EVERY lap, with no hinge at all, so a
    -- fresh tyre on lap 1 was charged the whole cliff severity as its current
    -- degradation rate. It is now the actual derivative of the pace curve above:
    -- the wear gradient, plus the ramp's slope only while the ramp is climbing
    -- (0 before onset, 0 once it has saturated at onset + sev_span).
    -- NULL when the tyre age is unknown: where on the curve the lap sits, and
    -- so whether the ramp is climbing, is unknown too (F39).
    COALESCE(compound_wear_gradient, 0.0)
    + CASE
        WHEN laps_past_cliff IS NULL THEN NULL
        WHEN
            laps_past_cliff > 0.0
            AND laps_past_cliff < {{ cliff_severity_span() }}
            THEN {{ cliff_ramp_slope_s_per_lap('compound_cliff_severity',
                                               'compound_wear_gradient') }}
        ELSE 0.0
    END AS expected_degradation_rate_s_per_lap,
    ambient_temp_delta,
    laps_past_cliff
FROM with_pace
