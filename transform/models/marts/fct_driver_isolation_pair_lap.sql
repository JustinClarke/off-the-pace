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
--   relative_pace_gain_s      t(d') - t(d)  (model-free, raw pace; no tyre-age
--                             adjustment, the peer match on tyre age within
--                             var('isolation_peer_age_tolerance') laps controls
--                             for it instead: W63 design 2, 2026-10-03)
--   relative_pace_raw_gain_s  the same value, kept under its old name for the
--                             readers that compare the two
-- Sign: seconds per lap, POSITIVE = d (lap_id's driver) FASTER than the peer.
--
-- THE CUMULATIVE IDENTITY. Because p = car_iso - y and y = x - (the lap's
-- field median), which both cars share, and x has the compound seed's C removed,
--   relative_pace_gain_s = pace_gap_gain_s + car_advantage_gain_s
--                          + traffic_advantage_gain_s + (C(d') - C(d))
-- with
--   pace_gap_gain_s           p_d - p_d' = pure_gap_gain_s
--   pure_gap_gain_s           pure_d - pure_d'
--   car_advantage_gain_s      car_iso_d' - car_iso_d; > 0 = d's car faster
--                             (0 for teammates)
--   traffic_advantage_gain_s  D_d' - D_d; > 0 = d lost less to dirty air
-- The last term is the tyre-age bias the peer match leaves: the seed's pricing
-- of an age gap of at most the tolerance. It is not published as a column. It
-- is exactly 0 when the two cars are on the same tyre age, so the three-term
-- identity is exact there and T42 asserts it to 1e-6 on those pair rows where
-- the car terms exist (both cars have car_iso_s). The terms are computed here
-- and never re-derived downstream.
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

    -- Tier 3 (s/lap; positive = d faster). Raw, matched on tyre age.
    b.lap_time_s - a.lap_time_s AS relative_pace_gain_s,
    b.lap_time_s - a.lap_time_s AS relative_pace_raw_gain_s,

    -- The identity terms (s/lap; positive = in d's favour).
    a.pace_isolated_gain_s - b.pace_isolated_gain_s AS pace_gap_gain_s,
    a.pure_skill_gain_s - b.pure_skill_gain_s AS pure_gap_gain_s,
    b.car_iso_s - a.car_iso_s AS car_advantage_gain_s,
    b.dirty_air_tax_s - a.dirty_air_tax_s AS traffic_advantage_gain_s
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
