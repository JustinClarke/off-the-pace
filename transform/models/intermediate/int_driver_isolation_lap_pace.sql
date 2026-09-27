-- Driver isolation, the car removed: p(d,l), the isolated pace per Ω lap
-- (WI-16a). Grain: one row per Ω lap, PK lap_id (every
-- int_driver_isolation_lap_panel row).
--
--   pace_isolated_gain_s  p(d,l) = -( y_s - car_iso_s )
--
-- y_s is the lap's field-centred time with compound and dirty air removed
-- (int_driver_isolation_lap_panel); car_iso_s is the car term fitted on that
-- same scale (int_constructor_car_fe_isolation). What is left is the driver
-- plus noise, with everything modelled taken out: car, tyre state, traffic,
-- and, through the field centring, fuel, rubber, ambient and the field base.
--
-- Sign: pace_isolated_gain_s in seconds per lap, POSITIVE = FASTER than the
-- field on an equal car. The upstream chain (y_s, car_iso_s) uses the opposite
-- convention; the flip happens here, once, and every published column carries
-- the sign in its name (_gain_s). T43 pins it from raw lap times.
--
-- This model exists so that the stint model (int_driver_isolation_stint_tyre)
-- and the lap model (int_driver_isolation_lap_values) subtract the car the same
-- way, instead of two copies of the expression drifting apart.
--
-- NULL policy: when the car term is missing (car_term_source 'unidentified' or
-- 'not_estimated', or no fit row), pace_isolated_gain_s is NULL. It is never
-- COALESCEd to a car term of 0 -- that would publish the car's pace as the
-- driver's (the F1/F7 defect class).
--
-- Leakage: a function of the residual trajectory. No ML-contract mart may
-- depend on it (T48).

{{ config(materialized='table', tags=['driver_isolation']) }}

SELECT
    p.lap_id,
    p.stint_id,
    p.race_year,
    p.race_id,
    p.driver_id,
    p.constructor_id,
    p.stint_number,
    p.lap_number,
    p.compound,
    p.age_in_stint,
    p.lap_in_stint,
    p.valid_lap_in_stint,
    p.laps_past_cliff,
    p.fuel_mass_kg,
    p.era,
    p.anomaly_class,
    p.air_state_dominant,
    p.is_dirty_air_lap,
    p.field_n,
    p.lap_time_s,
    p.compound_component_s,
    p.dirty_air_tax_s,
    p.x_s,
    p.y_s,
    p.tyre_offset_vs_field_s,
    p.tyre_phase,
    p.is_recovery,
    p.stint_phase,
    c.car_iso_s,
    COALESCE(c.car_term_source, 'no_fit_row') AS car_term_source,
    -(p.y_s - c.car_iso_s) AS pace_isolated_gain_s
FROM {{ ref('int_driver_isolation_lap_panel') }} AS p
LEFT JOIN {{ ref('int_constructor_car_fe_isolation') }} AS c
    ON
        p.race_year = c.race_year
        AND p.race_id = c.race_id
        AND p.constructor_id = c.constructor_id
