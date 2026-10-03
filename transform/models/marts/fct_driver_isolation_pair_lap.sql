-- Driver isolation, tier 3 per pair of cars: relative pace against
-- same-strategy peers, and its exact split into driver, car and
-- traffic (WI-16). Grain: one row per (lap, peer lap), PK
-- (lap_id, peer_lap_id). The table the "X vs Y" questions are answered from.
--
-- PEERS. d' is a peer of d on lap l when both have an Ω lap
-- (int_driver_isolation_lap_values) in the same race, on the SAME LAP NUMBER
-- (so the same fuel load, rubber and weather), on the SAME COMPOUND, with
-- |age_d' - age_d| <= var('isolation_peer_age_tolerance'). Teammates are
-- included and flagged is_teammate. Both directions are rows: (d, d') and
-- (d', d) each appear, with every gain column's sign flipped.
--   relative_pace_raw_gain_s  t(d') - t(d)                     (model-free)
--   relative_pace_gain_s      (t(d') - t(d)) - (g(d') - g(d))  (age-adjusted
--                             by the fitted tyre-age curve g,
--                             int_driver_isolation_age_curve, over <= 3 laps)
--   relative_pace_seed_adj_gain_s  (t(d') - t(d)) - (C(d') - C(d)), the
--                             seed-ΔC adjustment tier 3 used until 2026-09-30,
--                             kept for comparison (it raised the within-pair
--                             variance by 3.4%, WI-16b)
-- Sign: seconds per lap, POSITIVE = d (lap_id's driver) FASTER than the peer.
--
-- THE CUMULATIVE IDENTITY. Because p = car_iso - y and y = x - (the lap's
-- field median), which both cars share, and x has the SEED's C removed,
--   relative_pace_gain_s = pace_gap_gain_s + car_advantage_gain_s
--                          + traffic_advantage_gain_s + age_pricing_gain_s
-- with
--   pace_gap_gain_s           p_d - p_d' = pure_gap_gain_s
--   pure_gap_gain_s           pure_d - pure_d'
--   car_advantage_gain_s      car_iso_d' - car_iso_d; > 0 = d's car faster
--                             (0 for teammates)
--   traffic_advantage_gain_s  D_d' - D_d; > 0 = d lost less to dirty air
--   age_pricing_gain_s        (C(d') - C(d)) - (g(d') - g(d)): the part of
--                             the tyre-age gap the seed prices and the fitted
--                             curve does not. Pure is built on the seed, the
--                             relative gap on the curve; this term is the
--                             difference, so the identity stays exact.
-- The terms are computed here and never re-derived downstream. T42 asserts the
-- identity to 1e-6 on every pair row where the car terms exist (both cars have
-- car_iso_s).
--
-- Peers share a lap and a compound, not a situation: a peer fighting for
-- position or under team orders is not neutral, so a pair mean is an average
-- over those situations, not a controlled comparison.
--
-- Leakage: functions of the residual trajectory. No ML-contract mart may
-- depend on this model (T48).

{{ config(materialized='table', tags=['driver_isolation']) }}

SELECT
    a.lap_id,
    b.lap_id AS peer_lap_id,
    a.race_year,
    a.race_id,
    a.lap_number,
    a.compound,
    a.driver_id,
    b.driver_id AS peer_driver_id,
    a.constructor_id,
    b.constructor_id AS peer_constructor_id,
    a.constructor_id = b.constructor_id AS is_teammate,
    a.stint_id,
    b.stint_id AS peer_stint_id,
    a.age_in_stint,
    b.age_in_stint AS peer_age_in_stint,
    a.stint_phase,
    b.stint_phase AS peer_stint_phase,
    a.tyre_phase,
    b.tyre_phase AS peer_tyre_phase,
    a.is_dirty_air_lap,
    b.is_dirty_air_lap AS peer_is_dirty_air_lap,

    -- Tier 3 (s/lap; positive = d faster). A missing curve row leaves
    -- relative_pace_gain_s NULL (its not_null test fails the build), never raw.
    b.lap_time_s - a.lap_time_s AS relative_pace_raw_gain_s,
    (b.lap_time_s - a.lap_time_s)
    - (gb.age_effect_s - ga.age_effect_s) AS relative_pace_gain_s,
    (b.lap_time_s - a.lap_time_s)
    - (b.compound_component_s - a.compound_component_s)
        AS relative_pace_seed_adj_gain_s,

    -- The identity terms (s/lap; positive = in d's favour).
    a.pace_isolated_gain_s - b.pace_isolated_gain_s AS pace_gap_gain_s,
    a.pure_skill_gain_s - b.pure_skill_gain_s AS pure_gap_gain_s,
    b.car_iso_s - a.car_iso_s AS car_advantage_gain_s,
    b.dirty_air_tax_s - a.dirty_air_tax_s AS traffic_advantage_gain_s,
    (b.compound_component_s - a.compound_component_s)
    - (gb.age_effect_s - ga.age_effect_s) AS age_pricing_gain_s
FROM {{ ref('int_driver_isolation_lap_values') }} AS a
INNER JOIN {{ ref('int_driver_isolation_lap_values') }} AS b
    ON
        a.race_year = b.race_year
        AND a.race_id = b.race_id
        AND a.lap_number = b.lap_number
        AND a.compound = b.compound
        AND a.driver_id != b.driver_id
        AND ABS(b.age_in_stint - a.age_in_stint)
        <= {{ var('isolation_peer_age_tolerance') }}
LEFT JOIN {{ ref('int_driver_isolation_age_curve') }} AS ga
    ON
        a.race_id = ga.race_id
        AND a.compound = ga.compound
        AND a.age_in_stint = ga.age_in_stint
LEFT JOIN {{ ref('int_driver_isolation_age_curve') }} AS gb
    ON
        b.race_id = gb.race_id
        AND b.compound = gb.compound
        AND b.age_in_stint = gb.age_in_stint
