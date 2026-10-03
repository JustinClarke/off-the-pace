-- Driver isolation per driver-race (WI-16).
-- Grain: one row per driver-race with at least one Ω lap, PK driver_race_id.
-- The key is built with the SAME surrogate-key recipe as
-- fct_driver_skill_features (generate_surrogate_key of race_year, race_id,
-- driver_id), so the two join directly. fct_driver_skill_features is
-- deliberately NOT changed: it is a trained model's input, and an unvalidated
-- rating must not enter that contract (T48).
--
-- The two ratings rolled up over the race with lap weighting:
--   pure_skill     mean pure over the race's non-extrapolated laps
--   relative_pace  mean over the race's pair-laps
-- SEs combine stints, which are independent. For pure,
--   SE^2 = sigma_w^2 / (n f)
-- relative is the SD of the pair-lap values over sqrt(distinct laps with
-- peers). tau^2 per (season, rating) at this grain from rows with n >= 6,
-- NULL-safe. There is no minimum-race floor: lambda does that job. One-stint
-- races (about 5%) need no special case; the roll-up is that stint.
--
-- Also the tier-3 identity split (identity_*), and context:
-- number of stints, mean tyre_offset_vs_field_s, mean lift_coast_excess_share,
-- dirty_air_lap_share, the car term and its source.
--
-- Sign: every *_gain_s is seconds per lap, positive = faster / better.
-- Leakage: functions of the residual trajectory. No ML-contract mart may
-- depend on this model (T48).

{{ config(materialized='table', tags=['driver_isolation']) }}

WITH laps AS (
    SELECT * FROM {{ ref('fct_driver_isolation_lap') }}
),

stint AS (
    SELECT * FROM {{ ref('int_driver_isolation_stint_tyre') }}
),

-- Per-stint partial sums (not needed for race-level SE without slope terms).
stint_parts AS (
    SELECT
        l.race_year,
        l.race_id,
        l.driver_id,
        l.stint_id,
        COUNT(
            CASE WHEN NOT l.pure_is_extrapolated THEN l.pure_skill_gain_s END
        ) AS n_pure
    FROM laps AS l
    GROUP BY l.race_year, l.race_id, l.driver_id, l.stint_id
),

race_se_parts AS (
    SELECT
        p.race_year,
        p.race_id,
        p.driver_id,
        COUNT(*) AS n_stints
    FROM stint_parts AS p
    GROUP BY p.race_year, p.race_id, p.driver_id
),

lap_agg AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        constructor_id,
        era,
        car_iso_s,
        car_term_source,
        season_sigma_w_s,
        season_neff_factor,
        COUNT(*) AS n_laps,
        AVG(pace_isolated_gain_s) AS pace_isolated_gain_s,
        COUNT(CASE WHEN NOT pure_is_extrapolated THEN pure_skill_gain_s END)
            AS n_pure_laps,
        AVG(CASE WHEN NOT pure_is_extrapolated THEN pure_skill_gain_s END)
            AS pure_skill_gain_s,
        AVG(tyre_offset_vs_field_s) AS tyre_offset_vs_field_s,
        AVG(lift_coast_excess_share) AS lift_coast_excess_share,
        AVG(CASE WHEN is_dirty_air_lap THEN 1.0 ELSE 0.0 END)
            AS dirty_air_lap_share
    FROM laps
    -- Constant within a driver-race (one car, one race, one season), so grouped
    -- on, not picked: a second value would duplicate the row and fail the PK
    -- test (the F16 lesson).
    GROUP BY
        race_year,
        race_id,
        driver_id,
        constructor_id,
        era,
        car_iso_s,
        car_term_source,
        season_sigma_w_s, season_neff_factor
),

pair_agg AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        COUNT(DISTINCT lap_id) AS n_relative_laps,
        COUNT(*) FILTER (WHERE is_teammate) AS n_teammate_pair_laps,
        AVG(relative_pace_gain_s) AS relative_pace_gain_s,
        AVG(relative_pace_raw_gain_s) AS relative_pace_raw_gain_s,
        STDDEV_SAMP(relative_pace_gain_s) AS relative_pair_sd_s,
        {{ driver_isolation_identity_terms() }}
    FROM {{ ref('fct_driver_isolation_pair_lap') }}
    GROUP BY race_year, race_id, driver_id
),

rated AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(
            ['la.race_year', 'la.race_id', 'la.driver_id']
        ) }}
            AS driver_race_id,
        la.race_year,
        la.race_id,
        la.driver_id,
        la.constructor_id,
        la.era,
        la.car_iso_s,
        la.car_term_source,
        se.n_stints,
        la.n_laps,
        la.pace_isolated_gain_s,

        la.n_pure_laps,
        la.pure_skill_gain_s,
        -- The season offset already inside pure_skill_gain_s (W33; see
        -- int_driver_isolation_lap_values), carried so a reader can see it.
        {{ driver_isolation_pure_season_offset('la.race_year') }}
            AS pure_season_offset_gain_s,
        CASE
            WHEN la.n_pure_laps > 0
                THEN SQRT(
                    la.season_sigma_w_s * la.season_sigma_w_s
                    / (la.n_pure_laps * la.season_neff_factor)
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
        pa.identity_age_pricing_gain_s,

        la.tyre_offset_vs_field_s,
        la.lift_coast_excess_share,
        la.dirty_air_lap_share
    FROM lap_agg AS la
    INNER JOIN race_se_parts AS se
        ON
            la.race_year = se.race_year
            AND la.race_id = se.race_id
            AND la.driver_id = se.driver_id
    LEFT JOIN pair_agg AS pa
        ON
            la.race_year = pa.race_year
            AND la.race_id = pa.race_id
            AND la.driver_id = pa.driver_id
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
