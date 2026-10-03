-- Driver isolation per lap, with the rolling ~5-lap rating (WI-16).
-- Grain: one row per Ω lap, PK lap_id.
--
-- Holds the two ratings on the lap (int_driver_isolation_lap_values), the
-- lap's peer aggregates from fct_driver_isolation_pair_lap (tier 3 and the
-- identity split against all same-strategy peers), and a trailing window per
-- rating over the Ω laps of the SAME STINT with lap_number in
-- [l - (var('isolation_window_laps') - 1), l]. It is a RANGE frame on
-- lap_number, so a window across a safety car just holds fewer laps, and it
-- never reaches forward (T44 recomputes it from laps <= l).
--   pure_skill_5lap_gain_s     mean pure over the window's NON-extrapolated
--                              laps
--   relative_pace_5lap_gain_s  SUM(relative * n_peers) / SUM(n_peers), the
--                              pair-lap mean
-- Each is NULL below var('isolation_window_min_laps') contributing laps
-- (pair-laps for relative). The window is labelled with the current lap's
-- stint_phase; window_mixed_phase says it spans more than one.
--
-- WHAT A 5-LAP WINDOW CAN CARRY: about half signal (reliability ~0.43-0.56 in
-- the WI doc's prototype). It is the "is he on it right now" number, not the
-- "who is better" number; verdicts belong at stint or race grain
-- (fct_driver_isolation_stint / _race).
--
-- CONFIDENCE, per window and rating (macro driver_isolation_reliability):
--   SE, pure      sqrt( sigma_w^2 / (n f) )
--                 The WI doc's formula.
--   SE, relative  SD of the window's pair-lap values
--                 / sqrt(distinct laps with peers)
--   sigma_w, f    per season, from int_driver_isolation_stint_tyre
--   tau^2         per (season, rating) over this grain's non-NULL windows:
--                 GREATEST(VAR_SAMP(raw) - AVG(SE^2), 0), NULL-safe. (The WI
--                 doc's "rows with n >= 6" cannot apply to a window of at
--                 most 5 laps; the window floor does.)
--   lambda = tau^2 / (tau^2 + SE^2); shrunk = lambda * raw; confidence_pct and
--   trust_label from the driver_isolation_method_scores seed ('unvalidated'
--   until WI-16b fills it).
--
-- Context carried: tyre_offset_vs_field_s (the lap's strategy position,
-- team-dominated, not a rating) and lift_coast_excess_share (lift-and-coast
-- share above the same lap's Ω field median; fuel- and tyre-saving are
-- indistinguishable in it, WI doc Limitations).
--
-- Sign: every *_gain_s is seconds per lap, POSITIVE = FASTER / better.
-- Leakage: functions of the residual trajectory. No ML-contract mart may
-- depend on this model (T48).

{{ config(materialized='table', tags=['driver_isolation']) }}

{%- set min_n = var('isolation_window_min_laps') %}

WITH lap_values AS (
    SELECT * FROM {{ ref('int_driver_isolation_lap_values') }}
),

pair_agg AS (
    SELECT
        lap_id,
        COUNT(*) FILTER (WHERE is_teammate) AS n_teammate_peers,
        AVG(relative_pace_gain_s) AS relative_pace_gain_s,
        AVG(relative_pace_raw_gain_s) AS relative_pace_raw_gain_s,
        SUM(relative_pace_gain_s) AS relative_sum_s,
        SUM(relative_pace_gain_s * relative_pace_gain_s) AS relative_sumsq_s2,
        {{ driver_isolation_identity_terms() }}
    FROM {{ ref('fct_driver_isolation_pair_lap') }}
    GROUP BY lap_id
),

lift AS (
    SELECT
        lv.lap_id,
        lv.race_year,
        lv.race_id,
        lv.lap_number,
        t.lift_coast_share
    FROM lap_values AS lv
    LEFT JOIN {{ ref('int_lap_telemetry_aggregates') }} AS t
        ON lv.lap_id = t.lap_id
),

lift_field AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        MEDIAN(lift_coast_share) AS field_median_lift_coast_share
    FROM lift
    GROUP BY race_year, race_id, lap_number
),

laps AS (
    SELECT
        lv.*,
        -- A count of peers is 0 when there are none; the ratings themselves
        -- stay NULL.
        COALESCE(pa.n_pair_laps, 0) AS n_peers,
        COALESCE(pa.n_teammate_peers, 0) AS n_teammate_peers,
        pa.relative_pace_gain_s,
        pa.relative_pace_raw_gain_s,
        pa.relative_sum_s,
        pa.relative_sumsq_s2,
        pa.identity_n_pair_laps,
        pa.identity_relative_pace_gain_s,
        pa.identity_pace_gap_gain_s,
        pa.identity_car_advantage_gain_s,
        pa.identity_traffic_advantage_gain_s,
        pa.identity_age_pricing_gain_s,
        li.lift_coast_share,
        li.lift_coast_share
        - lf.field_median_lift_coast_share AS lift_coast_excess_share
    FROM lap_values AS lv
    LEFT JOIN pair_agg AS pa
        ON lv.lap_id = pa.lap_id
    LEFT JOIN lift AS li
        ON lv.lap_id = li.lap_id
    LEFT JOIN lift_field AS lf
        ON
            li.race_year = lf.race_year
            AND li.race_id = lf.race_id
            AND li.lap_number = lf.lap_number
),

windowed AS (
    SELECT
        *,
        COUNT(*) OVER w AS window_n_laps,
        MIN(lap_number) OVER w AS window_first_lap_number,
        MIN(stint_phase) OVER w
        != MAX(stint_phase) OVER w AS window_mixed_phase,

        COUNT(CASE WHEN NOT pure_is_extrapolated THEN pure_skill_gain_s END)
            OVER w
            AS window_n_pure_laps,
        AVG(CASE WHEN NOT pure_is_extrapolated THEN pure_skill_gain_s END)
            OVER w
            AS w_pure_mean,

        SUM(n_peers) OVER w AS window_n_pair_laps,
        COUNT(CASE WHEN n_peers > 0 THEN 1 END)
            OVER w
            AS window_n_relative_laps,
        SUM(relative_sum_s) OVER w AS w_relative_sum_s,
        SUM(relative_sumsq_s2) OVER w AS w_relative_sumsq_s2
    FROM laps
    WINDOW w AS (
        PARTITION BY stint_id
        ORDER BY lap_number
        RANGE BETWEEN {{ var('isolation_window_laps') - 1 }} PRECEDING
        AND CURRENT ROW
    )
),

window_values AS (
    SELECT
        *,
        CASE WHEN window_n_pure_laps >= {{ min_n }} THEN w_pure_mean END
            AS pure_skill_5lap_gain_s,
        CASE
            WHEN window_n_pure_laps >= {{ min_n }}
                THEN SQRT(
                    season_sigma_w_s * season_sigma_w_s
                    / (window_n_pure_laps * season_neff_factor)
                )
        END AS pure_skill_5lap_se_s,

        CASE
            WHEN window_n_pair_laps >= {{ min_n }}
                THEN w_relative_sum_s / window_n_pair_laps
        END AS relative_pace_5lap_gain_s,
        CASE
            WHEN
                w_relative_sum_s IS NULL
                OR w_relative_sumsq_s2 IS NULL
                OR window_n_pair_laps IS NULL
                THEN NULL
            WHEN window_n_pair_laps >= {{ min_n }}
                THEN SQRT(
                    GREATEST(
                        (
                            w_relative_sumsq_s2
                            - w_relative_sum_s
                            * w_relative_sum_s
                            / window_n_pair_laps
                        )
                        / (window_n_pair_laps - 1),
                        0.0
                    )
                ) / SQRT(window_n_relative_laps)
        END AS relative_pace_5lap_se_s
    FROM windowed
),

-- tau^2 before its floor at 0 is kept NULL-safe: GREATEST(NULL, 0.0) is 0.0 in
-- DuckDB, which would publish "no signal" for a season with too few windows to
-- measure (T29).
tau_raw AS (
    SELECT
        race_year,
        VAR_SAMP(pure_skill_5lap_gain_s)
        - AVG(pure_skill_5lap_se_s * pure_skill_5lap_se_s) AS pure_tau2_raw,
        VAR_SAMP(relative_pace_5lap_gain_s)
        - AVG(relative_pace_5lap_se_s * relative_pace_5lap_se_s)
            AS relative_tau2_raw
    FROM window_values
    GROUP BY race_year
),

tau AS (
    SELECT
        race_year,
        CASE
            WHEN pure_tau2_raw IS NULL THEN NULL ELSE
                GREATEST(pure_tau2_raw, 0.0)
        END
            AS pure_tau2,
        CASE
            WHEN relative_tau2_raw IS NULL THEN NULL ELSE
                GREATEST(relative_tau2_raw, 0.0)
        END
            AS relative_tau2
    FROM tau_raw
),

method AS (
    SELECT
        MAX(CASE WHEN rating = 'pure' THEN method_score END) AS pure_score,
        MAX(CASE WHEN rating = 'pure' THEN grade END) AS pure_grade,
        MAX(CASE WHEN rating = 'relative' THEN method_score END)
            AS relative_score,
        MAX(CASE WHEN rating = 'relative' THEN grade END) AS relative_grade
    FROM {{ ref('driver_isolation_method_scores') }}
)

SELECT
    v.lap_id,
    v.stint_id,
    v.race_year,
    v.race_id,
    v.driver_id,
    v.constructor_id,
    v.stint_number,
    v.lap_number,
    v.compound,
    v.age_in_stint,
    v.valid_lap_in_stint,
    v.laps_past_cliff,
    v.era,
    v.tyre_phase,
    v.is_recovery,
    v.stint_phase,
    v.air_state_dominant,
    v.is_dirty_air_lap,
    v.field_n,

    -- The lap (s; positive = slower, residual convention) and its context.
    v.lap_time_s,
    v.compound_component_s,
    v.dirty_air_tax_s,
    v.y_s,
    v.car_iso_s,
    v.car_term_source,
    v.tyre_offset_vs_field_s,
    v.lift_coast_share,
    v.lift_coast_excess_share,

    -- Ratings on this lap (s/lap; positive = faster).
    v.pace_isolated_gain_s,
    v.pure_skill_gain_s,
    v.pure_is_extrapolated,
    v.season_sigma_w_s,
    v.season_neff_factor,

    -- Tier 3 against this lap's peers.
    v.n_peers,
    v.n_teammate_peers,
    v.relative_pace_gain_s,
    v.relative_pace_raw_gain_s,
    v.identity_n_pair_laps,
    v.identity_relative_pace_gain_s,
    v.identity_pace_gap_gain_s,
    v.identity_car_advantage_gain_s,
    v.identity_traffic_advantage_gain_s,
    v.identity_age_pricing_gain_s,

    -- The trailing window.
    v.window_first_lap_number,
    v.window_n_laps,
    v.window_mixed_phase,
    v.window_n_pure_laps,
    v.window_n_pair_laps,
    v.window_n_relative_laps,

    v.pure_skill_5lap_gain_s,
    v.pure_skill_5lap_se_s,
    {{ driver_isolation_reliability(
        'pure_skill_5lap', 'v.pure_skill_5lap_gain_s', 'v.pure_skill_5lap_se_s',
        't.pure_tau2', 'm.pure_score', 'm.pure_grade') }},

    v.relative_pace_5lap_gain_s,
    v.relative_pace_5lap_se_s,
    {{ driver_isolation_reliability(
        'relative_pace_5lap', 'v.relative_pace_5lap_gain_s', 'v.relative_pace_5lap_se_s',
        't.relative_tau2', 'm.relative_score', 'm.relative_grade') }}
FROM window_values AS v
LEFT JOIN tau AS t
    ON v.race_year = t.race_year
CROSS JOIN method AS m
