-- Driver isolation, tier 1 per lap: pure_skill_gain_s (WI-16). Grain: one row
-- per Ω lap, PK lap_id.
--
-- TIER 1, PURE PACE:   pure_skill_gain_s = pace_isolated_gain_s
-- His pace against the field on an equal car, equal tyre state, equal traffic
-- and equal fuel. On a tyre past its cliff this is the extrapolated pre-cliff
-- pure line, flagged pure_is_extrapolated: the lap time there is dominated by
-- the tyre, and pure-skill aggregates use early, mid and recovery laps on a
-- pre-cliff tyre only.
--
-- NULL POLICY (never COALESCE a missing rating to 0; that is the F1/F7 class):
--   p NULL (no car term)              -> pure NULL
--
-- Sign: every *_gain_s is seconds per lap, POSITIVE = FASTER / better.
-- Leakage: functions of the residual trajectory. No ML-contract mart may
-- depend on this model (T48).

{{ config(materialized='table', tags=['driver_isolation']) }}

WITH joined AS (
    SELECT
        l.*,
        s.n_line_laps,
        s.line_mean_pace_gain_s,
        s.line_mean_age_laps,
        s.line_ref_age_laps,
        s.line_slope_s_per_lap2,
        s.season_sigma_w_s,
        s.season_neff_factor
    FROM {{ ref('int_driver_isolation_lap_pace') }} AS l
    LEFT JOIN {{ ref('int_driver_isolation_stint_tyre') }} AS s
        ON l.stint_id = s.stint_id
)

SELECT
    lap_id,
    stint_id,
    race_year,
    race_id,
    driver_id,
    constructor_id,
    stint_number,
    lap_number,
    compound,
    age_in_stint,
    lap_in_stint,
    valid_lap_in_stint,
    laps_past_cliff,
    fuel_mass_kg,
    era,
    anomaly_class,
    air_state_dominant,
    is_dirty_air_lap,
    field_n,
    tyre_phase,
    is_recovery,
    stint_phase,

    -- The lap and the modelled terms (s; positive = slower, the residual
    -- convention).
    lap_time_s,
    compound_component_s,
    dirty_air_tax_s,
    x_s,
    y_s,
    tyre_offset_vs_field_s,
    car_iso_s,
    car_term_source,

    -- Ratings (s/lap; positive = faster).
    pace_isolated_gain_s,
    pace_isolated_gain_s AS pure_skill_gain_s,
    tyre_phase = 'cliff' AS pure_is_extrapolated,

    -- Stint context the marts' SEs are built from.
    n_line_laps,
    line_ref_age_laps,
    line_slope_s_per_lap2,
    season_sigma_w_s,
    season_neff_factor
FROM joined
