-- Driver-weekend qualifying summary, for the ML feature contract.
-- Grain: (race_year, race_id, driver_id) -- one row per driver per race weekend.
-- Work item 02b (Tier 1 of _improvements/work/02-feature-expansion.md).
--
-- WHAT THIS IS FOR. Qualifying is a full session the ML feature contract has never
-- read: 14,165 decomposed quali laps 2018-2024, already fuel-corrected
-- (int_lap_fuel_state_qualifying assumes a flat 12kg burn, defensible because a
-- quali push lap's fuel burn is ~0.006s -- see the leaf doc §2). Qualifying runs
-- strictly before the race, so joining it needs no lag/expanding-window treatment,
-- PROVIDED the columns used are themselves scoped to the qualifying session alone.
--
-- ONE COLUMN FROM THE SOURCE MODEL IS DELIBERATELY NOT CARRIED HERE:
-- quali_vs_race_skill_delta_s. int_qualifying_decomposed computes it as
--   quali_skill_session_avg_s - AVG(driver_skill_residual_s)
-- where the subtracted average (race_driver_race_avg in that model) is taken over
-- the driver's laps in THIS SAME race (GROUP BY race_year, race_id, driver_id
-- against int_lap_residual_decomposed) -- not a prior race, THIS one. That average
-- is not knowable until the race has finished: it pools every lap of the race a
-- feature row would be describing, including every lap after the one in question.
-- Broadcasting it onto the race's own laps is the same forward-reach shape 02a
-- ruled on in int_corner_skill_residuals, on a coarser grain (the whole race,
-- instead of a 5-lap bucket). ml/src/features.py::audit_aggregation_scope confirms
-- the shape mechanically: that CTE groups by (race_year, race_id, driver_id) with
-- no lap-ordinal key alongside it, so it does not pin a lap and would be flagged
-- the moment it entered the mart lineage. Left out rather than declared a known
-- leak: no fix salvages the construct as an ML feature without a genuinely
-- backward-looking race-skill baseline (e.g. a trailing, cross-race measure),
-- which is new feature engineering, not "one join", and is out of scope for this
-- item. See the leaf doc's 02b section for the full ruling.
--
-- WHAT IS CARRIED is scoped to the qualifying session alone -- every input column
-- is read off int_qualifying_decomposed rows whose own grain is a qualifying push
-- lap, all of which happen before the race. Aggregating a driver's Q1/Q2/Q3 laps
-- pools only WITHIN that (strictly prior) session, never into the race being
-- predicted. The GROUP BY below does not pin a single lap either, by the same
-- mechanical test -- it is declared `accepted` in schema.yml on exactly the
-- "qualifying precedes the race" argument, mirroring how int_lap_fuel_state's
-- race-level starting-fuel constant is declared there.
--
-- MECHANISM. The leaf doc names two candidate constructs. constructor_component_s
-- survives: a car's one-lap aero/power level, measured with fuel, strategy and
-- traffic all near-absent, is a genuinely different measurement than anything in
-- the current 32-column contract, which carries no quali-session car term at all.
-- quali_vs_race_skill_delta_s (the other candidate) is the barred column above;
-- quali_skill_session_avg_s and quali_pace_delta_best_s are carried as a SAFE
-- proxy for the same underlying idea -- a driver's one-lap form this weekend --
-- without subtracting anything from the race being predicted.
--
-- AGGREGATION CHOICES, one join's worth of judgment calls, recorded so they are
-- not re-derived. MEAN for the constructor terms (smooths Q1/Q2/Q3 segment-to-
-- segment noise in a term that should be near-stable across one weekend). MIN for
-- quali_pace_delta_s and ratio_to_segment_best (both "positive/higher = slower"
-- by construction -- see int_lap_residual_decomposed_qualifying's header -- so
-- MIN is the driver's single best push lap of the weekend). MAX for
-- quali_skill_session_avg_s / quali_segments_contested_n: both are already
-- computed at this exact (race_year, race_id, driver_id) grain one level up and
-- repeated on every push-lap row there, so MAX is a value-preserving collapse of
-- an already-constant column, not a real aggregation -- the same property 02c's
-- QUALIFY ROW_NUMBER() dedupe relies on for its own repeated-value rows.
--
-- COVERAGE. quali_push_laps_n is COALESCEd to 0 downstream (in the mart) for a
-- driver-weekend with no row here at all -- a genuine "no qualifying record"
-- rather than an invented value. See the leaf doc's 02b coverage measurement for
-- whether this is a random subset or a biased one.
--
-- HONEST CEILING. This grain is stint-invariant: every lap of a driver's race sees
-- the same value. Per the leaf doc's §1, 99.06% of the degradation target's
-- variance is within-stint, so this group can only ever address the other 0.94%.
-- Expected to move cliff_classifier and/or stint_life_regressor, not the
-- degradation trio -- the pre-registered arms test that expectation, they do not
-- assume it.

{{ config(materialized='table', tags=['intermediate', 'feature_engineering']) }}

WITH quali AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        constructor_component_s,
        constructor_component_se_s,
        quali_pace_delta_s,
        ratio_to_segment_best,
        quali_skill_session_avg_s,
        quali_segments_contested_n
    FROM {{ ref('int_qualifying_decomposed') }}
)

SELECT
    race_year,
    race_id,
    driver_id,
    COUNT(*) AS quali_push_laps_n,
    AVG(constructor_component_s) AS quali_constructor_pace_mean_s,
    AVG(constructor_component_se_s) AS quali_constructor_pace_se_mean_s,
    MIN(quali_pace_delta_s) AS quali_pace_delta_best_s,
    MIN(ratio_to_segment_best) AS quali_ratio_to_segment_best_min,
    MAX(quali_skill_session_avg_s) AS quali_skill_session_avg_s,
    MAX(quali_segments_contested_n) AS quali_segments_contested_n
FROM quali
GROUP BY race_year, race_id, driver_id
