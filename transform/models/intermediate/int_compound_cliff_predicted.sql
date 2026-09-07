-- Layer 04: Expected compound pace and cliff prediction.
-- Hockey-stick polynomial: β₀ + β₁×age + β₂×age² + β₃×GREATEST(0,
-- age-cliff_onset)²
-- All β coefficients sourced from dim_compounds_season (placeholder values
-- until
-- Python RANSAC estimation rewrites the seed).
-- ambient_temp_delta = track_temp-compound_optimal_temp_low, clipped [0,30].
{{ config(materialized='table') }}

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
        -- Laps past cliff onset (0 before onset)
        GREATEST(
            CAST(age_in_stint AS DOUBLE)
            - COALESCE(compound_cliff_onset_laps, 999.0),
            0.0
        )
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
    -- (host/ego onset shift):
    -- onset (laps) and post-onset severity (s/lap^2) from dim_compounds_season.
    COALESCE(compound_cliff_onset_laps, 999.0) AS compound_cliff_onset_laps,
    COALESCE(compound_cliff_severity, 0.0) AS compound_cliff_severity,
    -- The age-dependent wear portion, bounded. Exposed as its own column so
    -- the bound is assertable without re-deriving it from the pace total.
    LEAST(
        COALESCE(compound_wear_gradient, 0.0) * age_in_stint
        + 0.002 * POWER(age_in_stint, 2)
        + COALESCE(compound_cliff_severity, 0.0) * laps_past_cliff,
        {{ var('compound_wear_max_s_per_lap', 10.0) }}
    ) AS compound_wear_s,
    -- Hockey-stick pace model:
    -- grip_peak baseline + linear wear + quadratic age term (rubber
    -- accumulation)
    -- + cliff_severity * laps_past_cliff (linear post-cliff
    -- acceleration-severity
    --   is the empirically fitted average s/lap rate of post-cliff degradation)
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
    COALESCE(compound_grip_peak, 0.0)
    + LEAST(
        COALESCE(compound_wear_gradient, 0.0) * age_in_stint
        + 0.002 * POWER(age_in_stint, 2)
        + COALESCE(compound_cliff_severity, 0.0) * laps_past_cliff,
        {{ var('compound_wear_max_s_per_lap', 10.0) }}
    )
    + 0.005 * ambient_temp_delta AS expected_compound_pace_s,
    -- First derivative: rate of pace loss at current age
    COALESCE(compound_wear_gradient, 0.0)
    + 0.004 * age_in_stint
    + COALESCE(compound_cliff_severity, 0.0)
        AS expected_degradation_rate_s_per_lap,
    ambient_temp_delta,
    laps_past_cliff
FROM with_pace
