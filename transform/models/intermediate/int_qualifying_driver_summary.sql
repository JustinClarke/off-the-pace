-- Driver-weekend qualifying summary, for the ML feature contract.
-- Grain: (race_year, race_id, driver_id) -- one row per driver per race
-- weekend. Work item 02b (Tier 1 of
-- _improvements/work/02-feature-expansion.md).
--
-- WHAT THIS IS FOR. Qualifying is a full session the ML feature contract had
-- never read: ~16.9k decomposed quali push laps 2018-2025 (3,420 driver-weekends),
-- with no fuel correction applied (qualifying fuel load is not observable in our
-- data, so no fuel term is modelled). Qualifying runs strictly before the race, so joining it needs no
-- lag/expanding-window treatment,
-- PROVIDED the columns used are themselves scoped to the qualifying session
-- alone.
--
-- THE DRIVER'S BEST LAP IS THE BEST LAP IN THE TOP SEGMENT REACHED. The
-- starting grid is set by each driver's fastest lap in the highest segment
-- they reached (Q3 for the top 10, Q2 for 11-15, Q1 for the rest). Q1/Q2/Q3
-- are run on an evolving track against a shrinking, self-selected field, and
-- every per-lap baseline upstream is per segment (quali_pace_delta_s =
-- lap_time_s - that segment's median push lap; ratio_to_segment_best likewise).
-- So a minimum taken across segments does NOT find the fastest lap: it finds
-- the lap furthest below its own segment's median, which on the archive is
-- the top segment's fastest lap in only ~6% of Q3 weekends. quali_pace_delta_best_s
-- and quali_ratio_to_segment_best_min are therefore read off ONE lap, the
-- driver's fastest push lap (lowest lap_time_s) in the highest segment they
-- reached (quali_top_segment). The segment reached is itself part of the signal
-- (it is grid position's coarse band); the delta/ratio is the pace within it.
-- Unsegmented sessions: where bronze has no qualifying results / session
-- status for a weekend (2025_6, 99 laps / 20 drivers), int_qualifying_push_laps
-- labels every lap 'Q' (the whole session as one segment). 'Q' ranks below Q1
-- and, being the only segment of that weekend, is every driver's top segment
-- there, so the best lap is the session-best lap per driver -- the right
-- fallback.
--
-- ONE COLUMN FROM THE SOURCE MODEL IS DELIBERATELY NOT CARRIED HERE:
-- quali_vs_race_skill_delta_s. int_qualifying_decomposed computes it as
--   quali_skill_session_avg_s - AVG(driver_skill_residual_s)
-- where the subtracted average (race_driver_race_avg in that model) is taken
-- over the driver's laps in THIS SAME race (GROUP BY race_year, race_id,
-- driver_id against int_lap_residual_decomposed) -- not a prior race, THIS one.
-- That average is not knowable until the race has finished: it pools every lap
-- of the race a feature row would be describing, including every lap after the
-- one in question. Broadcasting it onto the race's own laps is the same
-- forward-reach shape 02a ruled on in int_corner_skill_residuals, on a coarser
-- grain (the whole race, instead of a 5-lap bucket).
-- ml/src/features.py::audit_aggregation_scope confirms the shape mechanically:
-- that CTE groups by (race_year, race_id, driver_id) with no lap-ordinal key
-- alongside it, so it does not pin a lap and would be flagged the moment it
-- entered the mart lineage. Left out rather than declared a known leak: no fix
-- salvages the construct as an ML feature without a genuinely backward-looking
-- race-skill baseline (e.g. a trailing, cross-race measure), which is new
-- feature engineering, not "one join", and is out of scope for this item. See
-- the leaf doc's 02b section for the full ruling.
--
-- WHAT IS CARRIED is scoped to the qualifying session alone -- every input
-- column is read off int_qualifying_decomposed rows whose own grain is a
-- qualifying push lap, all of which happen before the race. Aggregating a
-- driver's Q1/Q2/Q3 laps pools only WITHIN that (strictly prior) session, never
-- into the race being predicted. The GROUP BY below does not pin a single lap
-- either, by the same mechanical test -- it is declared `accepted` in
-- schema.yml on exactly the
-- "qualifying precedes the race" argument, mirroring how int_lap_fuel_state's
-- race-level starting-fuel constant is declared there.
--
-- MECHANISM. The leaf doc names two candidate constructs.
-- constructor_component_s survives: a car's one-lap aero/power level, measured
-- with fuel, strategy and traffic all near-absent, is a genuinely different
-- measurement than anything in the current 32-column contract, which carries no
-- quali-session car term at all. quali_vs_race_skill_delta_s (the other
-- candidate) is the barred column above; quali_skill_session_avg_s and
-- quali_pace_delta_best_s are carried as a SAFE proxy for the same underlying
-- idea -- a driver's one-lap form this weekend -- without subtracting anything
-- from the race being predicted.
--
-- AGGREGATION CHOICES, one join's worth of judgment calls, recorded so they are
-- not re-derived.
--   * quali_pace_delta_best_s, quali_ratio_to_segment_best_min: values on the
--     driver's fastest push lap in the top segment reached (see above), both
--     from the same lap. Positive/higher = slower (see
--     int_lap_residual_decomposed_qualifying's header). The delta is against
--     the top segment's own median, so a Q3 driver is measured against the
--     faster, self-selected Q3 field and a Q1-only driver against the Q1 field;
--     quali_top_segment lets a consumer separate the two.
--   * constructor terms: AVG. constructor_component_s is constant per
--     (constructor, weekend) -- it does not vary by segment or by lap -- so AVG
--     is a value-preserving collapse (it only matters as a guard if that ever
--     changes).
--   * quali_push_laps_n: COUNT of ALL push laps, every segment. It is the
--     coverage indicator for the other columns (0 in the mart = no row here)
--     and a measure of how much running the driver did.
--   * quali_skill_session_avg_s / quali_segments_contested_n: MAX, a
--     value-preserving collapse -- both are computed at this exact grain one level
--     up and repeated on every push-lap row there (the same property 02c's
--     QUALIFY ROW_NUMBER() dedupe relies on).
--
-- COVERAGE. quali_push_laps_n is COALESCEd to 0 downstream (in the mart) for a
-- driver-weekend with no row here at all -- a genuine "no qualifying record"
-- rather than an invented value. See the leaf doc's 02b coverage measurement
-- for whether this is a random subset or a biased one.
--
-- HONEST CEILING. This grain is stint-invariant: every lap of a driver's race
-- sees the same value. Per the leaf doc, 99.06% of the degradation target's
-- variance is within-stint, so this group can only ever address the other
-- 0.94%. Expected to move cliff_classifier and/or stint_life_regressor, not the
-- degradation trio -- the declared arms test that expectation, they do not
-- assume it.

{{ config(materialized='table', tags=['intermediate', 'feature_engineering']) }}

WITH quali AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_id,
        lap_time_s,
        quali_segment,
        -- Q3 > Q2 > Q1 > 'Q' (unsegmented fallback).
        COALESCE(TRY_CAST(SUBSTR(quali_segment, 2) AS INTEGER), 0) AS segment_rank,
        constructor_component_s,
        constructor_component_se_s,
        quali_pace_delta_s,
        ratio_to_segment_best,
        quali_skill_session_avg_s,
        quali_segments_contested_n
    FROM {{ ref('int_qualifying_decomposed') }}
),

-- One row per driver-weekend: the fastest push lap (by lap time, not by
-- delta) in the highest segment the driver reached.
best_lap AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        quali_segment AS quali_top_segment,
        quali_pace_delta_s AS quali_pace_delta_best_s,
        ratio_to_segment_best AS quali_ratio_to_segment_best_min
    FROM quali
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY race_year, race_id, driver_id
        ORDER BY segment_rank DESC, lap_time_s ASC NULLS LAST, lap_id
    ) = 1
),

rolled AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        COUNT(*) AS quali_push_laps_n,
        AVG(constructor_component_s) AS quali_constructor_pace_mean_s,
        AVG(constructor_component_se_s) AS quali_constructor_pace_se_mean_s,
        MAX(quali_skill_session_avg_s) AS quali_skill_session_avg_s,
        MAX(quali_segments_contested_n) AS quali_segments_contested_n
    FROM quali
    GROUP BY race_year, race_id, driver_id
)

SELECT
    r.race_year,
    r.race_id,
    r.driver_id,
    r.quali_push_laps_n,
    r.quali_constructor_pace_mean_s,
    r.quali_constructor_pace_se_mean_s,
    b.quali_pace_delta_best_s,
    b.quali_ratio_to_segment_best_min,
    r.quali_skill_session_avg_s,
    r.quali_segments_contested_n,
    b.quali_top_segment
FROM rolled AS r
INNER JOIN best_lap AS b
    ON
        r.race_year = b.race_year
        AND r.race_id = b.race_id
        AND r.driver_id = b.driver_id
