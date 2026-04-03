-- mart_degradation_history_envelope.sql · marts
-- Grain: (circuit_id, era, compound, lap_in_stint)
--
-- Pre-aggregated historical stint envelope that powers the Degradation
-- Simulator's
-- physically-correct recomposition. For each physical circuit × regulation era
-- × compound
-- it captures, at every lap-in-stint, the observed *fuel-removed* pace
-- distribution, the
-- corresponding tyre-degradation-from-fresh band, and the isotonic-fitted
-- monotone deg
-- columns + modulation coefficients (from
-- data/fits/degradation_isotonic.parquet).
--
-- The app headline formula (post-P2.2):
--   M(k) = clamp(1 + air_bump·𝟙[dirty_air] + temp_penalty·max(0,
--   temp_delta−headroom), 1, 1.5)
--   tyre(k)   = obs_deg_from_fresh_p50_mono_s(k) × M(k)    [monotone by
--   construction]
--   net(k)    = ref_green_pace_s + fuel_component(k) + tyre(k)
--   band(k)   = ref + fuel + obs_deg_from_fresh_{p10,p90}_mono_s(k) × M(k)
--
-- Source: int_lap_residual_decomposed (weight_corrected_lap_time = lap_time −
-- fuel;
-- so the fuel term is already removed and we re-add it deterministically
-- downstream).
-- Joined to the race_to_track seed (numeric race_id) → dim_circuits for the
-- physical circuit_id.
--
-- ref_green_pace_s: per (circuit_id, era, compound) median
-- weight_corrected_lap_time over
-- fresh-tyre clean laps (age_in_stint ≤ 2). Carries field pace + compound +
-- fresh-tyre
-- baseline with fuel removed; repeated on every lap_in_stint row for that cell.
--
-- Era split matches int_driver_circuit_era_affinity /
-- int_era_normalized_driver_rating:
--   pre2022 = 2018–2021 (last-gen aero), post2022 = 2022–2024 (ground-effect).
--
-- A compound='_all' rollup is emitted for fallback when a specific compound has
-- no history.
{{ config(materialized='table', tags=['marts']) }}

{% set era_boundary = 2022 %}

WITH clean AS (
    SELECT
        dc.circuit_id,
        dc.circuit_name,
        CASE
            WHEN lrd.race_year < {{ era_boundary }} THEN 'pre2022' ELSE
                'post2022'
        END
            AS era,
        lrd.compound,
        lrd.lap_in_stint,
        lrd.age_in_stint,
        lrd.weight_corrected_lap_time AS wclt
    FROM {{ ref('int_lap_residual_decomposed') }} AS lrd
    INNER JOIN {{ ref('race_to_track') }} AS rt
        ON CAST(REPLACE(lrd.race_id, '_', '') AS INTEGER) = rt.race_id
    INNER JOIN {{ ref('dim_circuits') }} AS dc
        ON rt.track_id = dc.circuit_key
    WHERE
        lrd.weight_corrected_lap_time IS NOT NULL
        AND lrd.compound IS NOT NULL
        AND lrd.lap_in_stint IS NOT NULL
        AND lrd.lap_in_stint BETWEEN 1 AND 50
        AND COALESCE(lrd.correction_weight, 0) = 1
        AND NOT lrd.is_safety_car_lap
        AND NOT lrd.is_vsc_lap
        AND NOT lrd.is_major_outlier_lap
),

-- One canonical display name per physical circuit (names identical across event
-- slugs).
circuit_name_map AS (
    SELECT circuit_id, MIN(circuit_name) AS circuit_name
    FROM clean
    GROUP BY circuit_id
),

-- Per-compound and rollup laps share the same shape; UNION the rollup ('_all')
-- in.
laps AS (
    SELECT circuit_id, era, compound, lap_in_stint, age_in_stint, wclt
    FROM clean
    UNION ALL
    SELECT circuit_id, era, '_all' AS compound, lap_in_stint, age_in_stint, wclt
    FROM clean
),

-- Fuel-removed fresh-tyre anchor per cell.
ref AS (
    SELECT
        circuit_id, era, compound,
        MEDIAN(wclt) AS ref_green_pace_s
    FROM laps
    WHERE age_in_stint <= 2
    GROUP BY circuit_id, era, compound
),

envelope AS (
    SELECT
        l.circuit_id,
        l.era,
        l.compound,
        l.lap_in_stint,
        COUNT(*) AS n_observations,
        r.ref_green_pace_s,
        QUANTILE_CONT(l.wclt, 0.10) AS obs_fuel_removed_pace_p10_s,
        QUANTILE_CONT(l.wclt, 0.50) AS obs_fuel_removed_pace_p50_s,
        QUANTILE_CONT(l.wclt, 0.90) AS obs_fuel_removed_pace_p90_s,
        QUANTILE_CONT(l.wclt, 0.10)
        - r.ref_green_pace_s AS obs_deg_from_fresh_p10_s,
        QUANTILE_CONT(l.wclt, 0.50)
        - r.ref_green_pace_s AS obs_deg_from_fresh_p50_s,
        QUANTILE_CONT(l.wclt, 0.90)
        - r.ref_green_pace_s AS obs_deg_from_fresh_p90_s
    FROM laps AS l
    INNER JOIN
        ref AS r
        ON
            l.circuit_id = r.circuit_id
            AND l.era = r.era
            AND l.compound = r.compound
    GROUP BY l.circuit_id, l.era, l.compound, l.lap_in_stint, r.ref_green_pace_s
)

SELECT
    e.circuit_id,
    cnm.circuit_name,
    e.era,
    e.compound,
    e.lap_in_stint,
    e.n_observations,
    e.ref_green_pace_s,
    e.obs_fuel_removed_pace_p10_s,
    e.obs_fuel_removed_pace_p50_s,
    e.obs_fuel_removed_pace_p90_s,
    e.obs_deg_from_fresh_p10_s,
    e.obs_deg_from_fresh_p50_s,
    e.obs_deg_from_fresh_p90_s,
    -- Isotonic-fitted monotone degradation columns (from
    -- degradation_isotonic.parquet)
    iso.obs_deg_from_fresh_p10_mono_s,
    iso.obs_deg_from_fresh_p50_mono_s,
    iso.obs_deg_from_fresh_p90_mono_s,
    -- Modulation coefficients (constant within each circuit/era/compound cell)
    COALESCE(iso.dirty_air_deg_mult, 1.0) AS dirty_air_deg_mult,
    COALESCE(iso.temp_headroom_c, 8.0) AS temp_headroom_c,
    COALESCE(iso.temp_penalty_s_per_deg, 0.010) AS temp_penalty_s_per_deg
FROM envelope AS e
INNER JOIN circuit_name_map AS cnm ON e.circuit_id = cnm.circuit_id
LEFT JOIN {{ source('fits', 'degradation_isotonic') }} AS iso
    ON
        e.circuit_id = iso.circuit_id
        AND e.era = iso.era
        AND e.compound = iso.compound
        AND e.lap_in_stint = iso.lap_in_stint
WHERE e.n_observations >= 3
ORDER BY e.circuit_id, e.era, e.compound, e.lap_in_stint
