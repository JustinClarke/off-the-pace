-- Driver isolation per stint and stint phase (WI-16). Grain: one row per
-- (stint_id, stint_phase), PK stint_phase_id, with stint_phase in early / mid /
-- cliff / recovery (the lap's phase, int_driver_isolation_lap_panel) plus one
-- 'all' row per stint. The 'all' row is built with UNION ALL, not GROUPING
-- SETS, so a NULL phase can never be mistaken for the rollup.
--
-- PER RATING (raw, n, SE, lambda, shrunk, confidence_pct, trust_label):
--   pure_skill     mean pure over the group's NON-extrapolated laps (a tyre
--                  past its cliff is not a driver measurement);
--                  n = n_pure_laps
--   relative_pace  mean over the group's pair-laps (fct_driver_isolation_
--                  pair_lap rows whose focal lap is in the group);
--                  n = n_pair_laps
-- SEs as in fct_driver_isolation_lap (pure: sigma_w^2/(n f);
-- relative: SD of pair-lap values over sqrt(distinct laps with peers)). tau^2
-- per (season, rating) at this grain from the 'all' rows with n >= 6 (one row
-- per stint, so no stint counts twice): GREATEST(VAR_SAMP(raw) - AVG(SE^2), 0),
-- NULL-safe. lambda, shrunk, confidence and trust come from the
-- driver_isolation_reliability macro and the method-scores seed.
--
-- ALSO:
--   identity_*           the tier-3 identity split over the group's pair-laps
--                        (macro driver_isolation_identity_terms): the
--                        contributions sum exactly to
--                        identity_relative_pace_gain_s
--   context              not ratings: strategy_verdict and opportunity_cost_s
--                        (int_pit_strategy_value; staying out is the pit
--                        wall's call), stint_end_cause and is_censored_stint
--                        (int_stint_end_regime), mean tyre_offset_vs_field_s
--                        (strategy position), mean lift_coast_excess_share,
--                        dirty_air_lap_share
--
-- Sign: every *_gain_s is seconds per lap, positive = faster / better.
-- Leakage: functions of the residual trajectory. No ML-contract mart may
-- depend on this model (T48).

{{ config(materialized='table', tags=['driver_isolation']) }}

WITH laps AS (
    SELECT * FROM {{ ref('fct_driver_isolation_lap') }}
),

lap_groups AS (
    SELECT stint_phase AS group_phase, * FROM laps
    UNION ALL
    SELECT 'all' AS group_phase, * FROM laps
),

lap_agg AS (
    SELECT
        stint_id,
        group_phase,
        COUNT(*) AS n_laps,
        MIN(lap_number) AS first_lap_number,
        MAX(lap_number) AS last_lap_number,
        MIN(age_in_stint) AS min_age_in_stint,
        MAX(age_in_stint) AS max_age_in_stint,
        AVG(pace_isolated_gain_s) AS pace_isolated_gain_s,

        COUNT(CASE WHEN NOT pure_is_extrapolated THEN pure_skill_gain_s END)
            AS n_pure_laps,
        AVG(CASE WHEN NOT pure_is_extrapolated THEN pure_skill_gain_s END)
            AS pure_skill_gain_s,

        AVG(tyre_offset_vs_field_s) AS tyre_offset_vs_field_s,
        AVG(lift_coast_excess_share) AS lift_coast_excess_share,
        AVG(CASE WHEN is_dirty_air_lap THEN 1.0 ELSE 0.0 END)
            AS dirty_air_lap_share
    FROM lap_groups
    GROUP BY stint_id, group_phase
),

pairs AS (
    SELECT * FROM {{ ref('fct_driver_isolation_pair_lap') }}
),

pair_groups AS (
    SELECT stint_phase AS group_phase, * FROM pairs
    UNION ALL
    SELECT 'all' AS group_phase, * FROM pairs
),

pair_agg AS (
    SELECT
        stint_id,
        group_phase,
        COUNT(DISTINCT lap_id) AS n_relative_laps,
        COUNT(*) FILTER (WHERE is_teammate) AS n_teammate_pair_laps,
        AVG(relative_pace_gain_s) AS relative_pace_gain_s,
        AVG(relative_pace_raw_gain_s) AS relative_pace_raw_gain_s,
        STDDEV_SAMP(relative_pace_gain_s) AS relative_pair_sd_s,
        {{ driver_isolation_identity_terms() }}
    FROM pair_groups
    GROUP BY stint_id, group_phase
),

stint AS (
    SELECT * FROM {{ ref('int_driver_isolation_stint_tyre') }}
),

rated AS (
    SELECT
        s.stint_id,
        la.group_phase AS stint_phase,
        s.race_year,
        s.race_id,
        s.driver_id,
        s.constructor_id,
        s.stint_number,
        s.compound,
        s.era,
        la.n_laps,
        la.first_lap_number,
        la.last_lap_number,
        la.min_age_in_stint,
        la.max_age_in_stint,
        la.pace_isolated_gain_s,

        la.n_pure_laps,
        la.pure_skill_gain_s,
        CASE
            WHEN la.n_pure_laps > 0
                THEN SQRT(
                    s.season_sigma_w_s * s.season_sigma_w_s
                    / (la.n_pure_laps * s.season_neff_factor)
                )
        END AS pure_skill_se_s,

        COALESCE(pa.n_pair_laps, 0) AS n_pair_laps,
        COALESCE(pa.n_relative_laps, 0) AS n_relative_laps,
        COALESCE(pa.n_teammate_pair_laps, 0) AS n_teammate_pair_laps,
        pa.relative_pace_gain_s,
        pa.relative_pace_raw_gain_s,
        pa.relative_pair_sd_s / SQRT(pa.n_relative_laps) AS relative_pace_se_s,
        pa.identity_n_pair_laps,
        pa.identity_relative_pace_gain_s,
        pa.identity_pace_gap_gain_s,
        pa.identity_car_advantage_gain_s,
        pa.identity_traffic_advantage_gain_s,

        -- The stint's tyre model (int_driver_isolation_stint_tyre).
        s.n_line_laps,
        s.line_slope_s_per_lap2,

        -- Context, not ratings.
        la.tyre_offset_vs_field_s,
        la.lift_coast_excess_share,
        la.dirty_air_lap_share,
        er.stint_end_cause,
        er.is_censored_stint,
        ps.strategy_verdict,
        ps.opportunity_cost_s
    FROM lap_agg AS la
    INNER JOIN stint AS s
        ON la.stint_id = s.stint_id
    LEFT JOIN pair_agg AS pa
        ON
            la.stint_id = pa.stint_id
            AND la.group_phase = pa.group_phase
    LEFT JOIN {{ ref('int_stint_end_regime') }} AS er
        ON la.stint_id = er.stint_id
    LEFT JOIN {{ ref('int_pit_strategy_value') }} AS ps
        ON la.stint_id = ps.stint_id
),

-- tau^2 before its floor at 0 is kept NULL-safe: GREATEST(NULL, 0.0) is 0.0 in
-- DuckDB, which would publish "no signal" for a season with too few rows to
-- measure (T29).
tau_raw AS (
    SELECT
        race_year,
        VAR_SAMP(CASE WHEN n_pure_laps >= 6 THEN pure_skill_gain_s END)
        - AVG(
            CASE
                WHEN n_pure_laps >= 6 THEN pure_skill_se_s * pure_skill_se_s
            END
        )
            AS pure_tau2_raw,
        VAR_SAMP(CASE WHEN n_pair_laps >= 6 THEN relative_pace_gain_s END)
        - AVG(
            CASE
                WHEN
                    n_pair_laps >= 6
                    THEN relative_pace_se_s * relative_pace_se_s
            END
        )
            AS relative_tau2_raw
    FROM rated
    WHERE stint_phase = 'all'
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
    r.stint_id || '|' || r.stint_phase AS stint_phase_id,
    -- EXCLUDE takes bare column names; the four are re-selected below, each next
    -- to its confidence columns.
    -- noqa: disable=RF02
    r.* EXCLUDE (
        pure_skill_gain_s, pure_skill_se_s,
        relative_pace_gain_s, relative_pace_se_s
    ),
    -- noqa: enable=RF02

    r.pure_skill_gain_s,
    r.pure_skill_se_s,
    {{ driver_isolation_reliability(
        'pure_skill', 'r.pure_skill_gain_s', 'r.pure_skill_se_s',
        't.pure_tau2', 'm.pure_score', 'm.pure_grade') }},

    r.relative_pace_gain_s,
    r.relative_pace_se_s,
    {{ driver_isolation_reliability(
        'relative_pace', 'r.relative_pace_gain_s', 'r.relative_pace_se_s',
        't.relative_tau2', 'm.relative_score', 'm.relative_grade') }}
FROM rated AS r
LEFT JOIN tau AS t
    ON r.race_year = t.race_year
CROSS JOIN method AS m
