-- 5-term residual decomposition per lap.
-- Decomposes actual lap_time_s into five additive components, yielding a
-- driver-skill residual stripped of field pace baseline (fuel-, compound-,
-- rubber-, and ambient-neutral), constructor structural pace,
-- and dirty-air tax.
--
-- Residual identity (all terms in seconds, positive = slower):
--   pace_delta_s = lap_time_s - base_track_pace_s
--               =  fuel_component_s
--                + compound_component_s
--                + constructor_component_s
--                + dirty_air_tax_s          ← extracted from
--                driver_skill_residual_s
--                + driver_skill_residual_s
--                + track_unexplained_s      (informational; not in
--                total_explained_s)
--
-- Note (F22): rubber and ambient components are carried in the base_track_pace_s
-- (from int_field_pace_curve's measurement of the field), not subtracted again here.
--
-- base_track_pace_s      : field_pace_smoothed_s from int_field_pace_curve
-- (10%-trimmed field mean of fuel- and compound-corrected laps, 5-lap smoothed)
-- pace_delta_s           : lap_time_s - base_track_pace_s
-- fuel_component_s       : weight_penalty_s from int_lap_fuel_state
-- compound_component_s   : expected_compound_pace_s from
-- int_compound_cliff_predicted
-- rubber_component_s     : rubber_component_s from int_track_evolution
-- (informational only, inside the base)
-- ambient_component_s    : ambient_component_s from int_track_evolution
-- (informational only, inside the base)
-- constructor_component_s: constructor_structural_pace_s from
-- int_constructor_structural_pace (no circuit interaction, F35)
-- dirty_air_tax_s        : per-lap dirty-air tax from
-- int_dirty_air_tax_component
-- driver_skill_residual_s: pace_delta_s minus all above; cleaned of dirty-air
-- signal
--
-- WI-01/F1: NULL propagates through the identity rather than being
-- fabricated. pace_delta_s is NULL when int_field_pace_curve has no measured
-- value for (race_year, race_id, lap_number); compound_component_s is NULL
-- when the tyre age is unknown (F39). Either one makes
-- driver_skill_residual_s and total_explained_s NULL.
--
-- Two terms ARE filled with 0 when their source has no row, and neither
-- fabricates a label:
--   dirty_air_tax_s -- COALESCE(.., 0.0) below. int_dirty_air_tax_component
--     has a row for every lap with a measured base (F23b, T17), so a missing
--     row only happens where pace_delta_s is already NULL and the 0 never
--     reaches driver_skill_residual_s. (The not_null test on this column in
--     schema.yml relies on the fill.)
--   constructor_component_s -- 0 where int_constructor_structural_pace has
--     no (race, constructor) row, mostly all-wet races; see the comment at
--     the column for why that cancels from the labels and what it does not
--     cancel from.
--
-- correction_weight from int_event_corrections is carried but NOT applied here.
{{ config(materialized='table') }}

WITH field_pace AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        field_pace_smoothed_s
    FROM {{ ref('int_field_pace_curve') }}
),

fuel AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        weight_corrected_lap_time,
        fuel_mass_kg,
        weight_penalty_s
    FROM {{ ref('int_lap_fuel_state') }}
),

geom AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        valid_lap_in_stint,
        age_in_stint,
        compound_in_stint AS compound,
        stint_length_actual,
        stint_length_valid
    FROM {{ ref('int_stint_geometry') }}
),

laps_meta AS (
    SELECT
        lap_id,
        constructor_id,
        position
    FROM {{ ref('stg_laps') }}
),

cliff AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        compound,
        age_in_stint,
        expected_compound_pace_s,
        expected_degradation_rate_s_per_lap,
        cliff_onset_passed,
        ambient_temp_delta,
        laps_past_cliff
    FROM {{ ref('int_compound_cliff_predicted') }}
),

evolution AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        rubber_component_s,
        ambient_component_s,
        unexplained_residual_s AS track_unexplained_s,
        track_temp_c,
        rainfall_flag
    FROM {{ ref('int_track_evolution') }}
),

constructor_struct AS (
    -- Grouped-aggregation constructor coefficient (placeholder for the full
    -- panel-regression spec; see int_constructor_structural_pace).
    -- Grain: (race_year, race_id, constructor_id) one row per constructor per
    -- race.
    SELECT
        race_year,
        race_id,
        constructor_id,
        constructor_structural_pace_s,
        constructor_structural_pace_se_s,
        constructor_structural_pace_ci_low_s,
        constructor_structural_pace_ci_high_s,
        panel_observations_n
    FROM {{ ref('int_constructor_structural_pace') }}
),

-- F35 (WI-01): int_circuit_x_constructor_interaction is no longer read here.
-- It used to be added on top of constructor_structural_pace_s, but that is
-- already a per-RACE constructor level, so it already spans this circuit; the
-- interaction was a second per-(team, circuit) shift on top of it. A global
-- re-centring (tried first) only moved every value by the same 0.002 s and
-- left each team-circuit shift in place, so the interaction is dropped, as the
-- audit proposed. Both terms are constant within a stint, so the ML labels
-- never saw it; the fix is to levels (app surfaces, fct_ghost_car_pace).

dirty_air AS (
    -- Per-lap dirty-air tax extracted from
    -- driver_skill_residual_s.
    SELECT
        lap_id,
        dirty_air_tax_s,
        dirty_air_tax_se_s,
        dirty_air_intensity_lag1,
        tax_calibration_confidence,
        cumulative_dirty_air_tax_race_s,
        dirtiest_air_lap_in_race_flag
    FROM {{ ref('int_dirty_air_tax_component') }}
),

corrections AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        correction_class,
        correction_weight,
        is_safety_car_lap,
        is_vsc_lap,
        is_red_flag_lap,
        is_restart_lap,
        is_pre_controlled_lap,
        is_lap_after_restart,
        is_local_yellow_lap,
        is_major_outlier_lap
    FROM {{ ref('int_event_corrections') }}
),

-- Combine all physical components onto the lap grain
combined AS (
    SELECT
        f.lap_id,
        f.stint_id,
        f.race_year,
        f.race_id,
        f.driver_id,
        f.lap_number,
        lm.constructor_id,
        lm.position,
        f.lap_time_s,
        f.weight_corrected_lap_time,
        f.fuel_mass_kg,
        f.weight_penalty_s AS fuel_component_s,
        c.compound,
        c.age_in_stint,
        c.expected_compound_pace_s AS compound_component_s,
        c.expected_degradation_rate_s_per_lap,
        c.cliff_onset_passed,
        c.laps_past_cliff,
        c.ambient_temp_delta,
        g.lap_in_stint,
        g.valid_lap_in_stint,
        g.stint_length_actual,
        g.stint_length_valid,

        -- Field pace baseline (trimmed-mean field pace, smoothed 5-lap centred
        -- window)
        fp.field_pace_smoothed_s AS base_track_pace_s,

        -- Track evolution components (NULL for low-sample laps, filled 0 to
        -- preserve row)
        COALESCE(e.rubber_component_s, 0.0) AS rubber_component_s,
        COALESCE(e.ambient_component_s, 0.0) AS ambient_component_s,
        e.track_unexplained_s,
        e.track_temp_c,
        e.rainfall_flag,

        -- Constructor structural pace: the per-race grouped-aggregation
        -- coefficient alone (F35: no circuit interaction on top, see above).
        --
        -- The COALESCE to 0 is deliberate and is the one place this identity
        -- prices an unmeasured term at 0. It fires where
        -- int_constructor_structural_pace has no row for (race, constructor):
        -- its panel keeps only dry, full-weight laps, so an all-wet race has
        -- no constructor row at all (2021_16, 2024_21, 2020_14, 2019_11,
        -- 2025_1, 2022_18), and a few constructors in mixed races have no dry
        -- clean lap. 4,548 laps with a measured residual on the 2026-09-27
        -- build, most of them rain laps (anomaly_class 'conditions', so not
        -- training-eligible anyway). Why 0 and not NULL: the term is one
        -- constant per (race, constructor), so it cancels exactly from both
        -- ML labels (every label differences laps within one stint). What it
        -- does NOT cancel from is the LEVEL of driver_skill_residual_s on
        -- those laps, which carries the car's pace there: app surfaces that
        -- average residual levels over wet races read car + driver, not
        -- driver alone.
        COALESCE(cs.constructor_structural_pace_s, 0.0)
            AS constructor_component_s,
        COALESCE(cs.constructor_structural_pace_se_s, 0.0)
            AS constructor_component_se_s,
        cs.constructor_structural_pace_ci_low_s
            AS constructor_component_ci_low_s,
        cs.constructor_structural_pace_ci_high_s
            AS constructor_component_ci_high_s,
        cs.panel_observations_n AS constructor_panel_n,

        -- Dirty-air tax: per-lap seconds attributable to following another
        -- car. Filled with 0 only where int_dirty_air_tax_component has no
        -- row, which is only where the base is unmeasured (pace_delta_s NULL),
        -- so the fill never reaches driver_skill_residual_s (header note).
        COALESCE(da.dirty_air_tax_s, 0.0) AS dirty_air_tax_s,
        COALESCE(da.dirty_air_tax_se_s, 0.0) AS dirty_air_tax_se_s,
        da.dirty_air_intensity_lag1,
        COALESCE(da.tax_calibration_confidence, 0.0)
            AS dirty_air_tax_confidence,
        COALESCE(da.cumulative_dirty_air_tax_race_s, 0.0)
            AS cumulative_dirty_air_tax_race_s,
        COALESCE(da.dirtiest_air_lap_in_race_flag, FALSE)
            AS dirtiest_air_lap_in_race_flag,

        -- Correction metadata
        cor.correction_class,
        cor.correction_weight,
        cor.is_safety_car_lap,
        cor.is_vsc_lap,
        cor.is_red_flag_lap,
        cor.is_restart_lap,
        cor.is_pre_controlled_lap,
        -- FD2 (WI-01): excluded from is_training_eligible downstream
        -- (fct_cliff_prediction_features), alongside anomaly_class
        -- 'event_driven'.
        COALESCE(cor.is_lap_after_restart, FALSE) AS is_lap_after_restart,
        cor.is_local_yellow_lap,
        cor.is_major_outlier_lap

    FROM fuel AS f
    INNER JOIN geom AS g ON f.lap_id = g.lap_id
    INNER JOIN laps_meta AS lm ON f.lap_id = lm.lap_id
    LEFT JOIN cliff AS c ON f.lap_id = c.lap_id
    LEFT JOIN field_pace AS fp
        ON
            f.race_year = fp.race_year
            AND f.race_id = fp.race_id
            AND f.lap_number = fp.lap_number
    LEFT JOIN evolution AS e
        ON
            f.race_year = e.race_year
            AND f.race_id = e.race_id
            AND f.lap_number = e.lap_number
    LEFT JOIN constructor_struct AS cs
        ON
            f.race_year = cs.race_year
            AND f.race_id = cs.race_id
            AND lm.constructor_id = cs.constructor_id
    LEFT JOIN dirty_air AS da ON f.lap_id = da.lap_id
    LEFT JOIN corrections AS cor ON f.lap_id = cor.lap_id
),

with_residual AS (
    SELECT
        *,
        -- Driver delta vs trimmed field pace (the closure base)
        lap_time_s - base_track_pace_s AS pace_delta_s,

        -- Total physics offsets subtracted from pace_delta_s (5-term identity).
        -- rubber/ambient are already in the base_track_pace_s (field measurement),
        -- so they are NOT subtracted again here (F22 fix).
        -- dirty_air_tax_s is accounted for separately, so
        -- driver_skill_residual_s carries no dirty-air signal.
        -- compound_component_s is NOT COALESCEd (F1's acceptance covers every
        -- fabricated component, not only the base): a lap with an unknown tyre
        -- age (F39) has an unknown compound cost, and NULL propagates through
        -- this sum rather than being priced as a free 0.0 s tyre.
        fuel_component_s
        + compound_component_s
        + constructor_component_s
        + dirty_air_tax_s AS total_explained_s,

        -- Driver skill residual: pace_delta_s minus all 5 physics components.
        -- rubber/ambient are already in the base, not subtracted again (F22 fix).
        -- Identity: pace_delta_s = total_explained_s + driver_skill_residual_s
        -- + track_unexplained_s
        (lap_time_s - base_track_pace_s)
        - fuel_component_s
        - compound_component_s
        - constructor_component_s
        - dirty_air_tax_s AS driver_skill_residual_s

    FROM combined
    WHERE lap_time_s IS NOT NULL
)

SELECT
    lap_id,
    stint_id,
    race_year,
    race_id,
    driver_id,
    constructor_id,
    lap_number,
    position,
    compound,
    age_in_stint,
    lap_in_stint,
    valid_lap_in_stint,
    stint_length_actual,
    stint_length_valid,
    cliff_onset_passed,
    laps_past_cliff,
    fuel_mass_kg,

    -- Raw time, weight-corrected time, and field-pace baseline
    lap_time_s,
    weight_corrected_lap_time,
    base_track_pace_s,
    pace_delta_s,

    -- Additive components (all in seconds, positive = slower contribution)
    -- First 5 terms in the residual identity
    fuel_component_s,
    compound_component_s,
    constructor_component_s,
    dirty_air_tax_s,
    -- Informational only (contained in base_track_pace_s, not subtracted again)
    rubber_component_s,
    ambient_component_s,
    -- Total of the 5 explained components in the identity
    total_explained_s,

    -- Residuals
    driver_skill_residual_s,
    track_unexplained_s,

    -- Physics metadata (informational, not part of residual identity)
    expected_degradation_rate_s_per_lap,
    ambient_temp_delta,
    track_temp_c,
    rainfall_flag,
    constructor_component_se_s,
    constructor_component_ci_low_s,
    constructor_component_ci_high_s,
    constructor_panel_n,
    dirty_air_tax_se_s,
    dirty_air_intensity_lag1,
    dirty_air_tax_confidence,
    cumulative_dirty_air_tax_race_s,
    dirtiest_air_lap_in_race_flag,

    -- Correction metadata (for downstream masking decisions)
    correction_class,
    correction_weight,
    is_safety_car_lap,
    is_vsc_lap,
    is_red_flag_lap,
    is_restart_lap,
    is_pre_controlled_lap,
    is_lap_after_restart,
    is_local_yellow_lap,
    is_major_outlier_lap

FROM with_residual
ORDER BY race_year, race_id, driver_id, lap_number
