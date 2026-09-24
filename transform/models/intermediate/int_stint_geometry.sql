-- Layer 03: Foundation for all downstream window functions.
-- Partition key for all physics-layer windows is `stint_id`, not lap_number.
-- age_in_stint uses tyre_life (may exceed lap_in_stint if set used in
-- qualifying).
-- Carries the FULL chronological lap sequence (SC/VSC/pit/invalid laps
-- included) so downstream LAG/EWMA windows decay correctly across those
-- gaps instead of treating the lap before/after a gap as adjacent.
-- `lap_in_stint` is the chronological ordinal (total laps);
-- `valid_lap_in_stint` is the ordinal among valid laps only (NULL on invalid
-- laps) for consumers that fit pace/regression models and need SC/pit laps
-- excluded.
--
-- WI-05 (F24, F25): stint_number, tyre_life (-> age_in_stint) and compound
-- come from stg_lap_tyre_qa, not raw bronze. That model fills the 2018 lap-1
-- stint gap (and the one-lap TyreLife shortfall it causes), cross-checks every
-- race's stint numbering against the pit record, and for a quarantined race or
-- driver-race serves the pit record's stint ordinal with NULL compound and age
-- instead of a boundary that contradicts it. tyre_qa_status and stint_source
-- say which applied to each lap.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT
        l.lap_id,
        l.race_year,
        l.race_id,
        l.driver_id,
        l.lap_number,
        l.is_valid_lap,
        l.is_pit_lap,
        l.is_safety_car_lap,
        l.is_vsc_lap,
        l.is_red_flag_lap,
        q.stint_number,
        q.tyre_life,
        q.compound,
        q.stint_source,
        q.tyre_qa_status
    FROM {{ ref('stg_laps') }} AS l
    INNER JOIN {{ ref('stg_lap_tyre_qa') }} AS q
        ON l.lap_id = q.lap_id
),

tyre_allocations AS (
    SELECT * FROM {{ ref('stg_tyre_allocations') }}
),

-- stg_laps.circuit_key is `CAST(race_id AS VARCHAR)` (stg_laps.sql:22) - a
-- RACE key like '2024_24', NOT a circuit slug. By contrast
-- stg_tyre_allocations.circuit_key is a circuit slug like
-- 'abu_dhabi_grand_prix'. The two domains are disjoint, so joining them
-- directly matches zero rows and fails silently (see 08p). The mart resolves
-- the slug through this seed and so does this model.
race_to_track AS (
    SELECT race_id, track_id AS circuit_slug
    FROM {{ ref('race_to_track') }}
),

with_stint_id AS (
    SELECT
        *,
        CONCAT(
            CAST(race_year AS VARCHAR), '_',
            CAST(race_id AS VARCHAR), '_',
            CAST(driver_id AS VARCHAR), '_',
            CAST(stint_number AS VARCHAR)
        ) AS stint_id,

        ROW_NUMBER() OVER (
            PARTITION BY race_year, race_id, driver_id, stint_number
            ORDER BY lap_number
        ) AS lap_in_stint
    FROM laps
),

with_stint_length AS (
    SELECT
        *,
        COUNT(*) OVER (
            PARTITION BY stint_id
        ) AS stint_length_actual,
        COUNT(*) FILTER (WHERE is_valid_lap) OVER (
            PARTITION BY stint_id
        ) AS stint_length_valid,
        CASE
            WHEN is_valid_lap THEN
                COUNT(*) FILTER (WHERE is_valid_lap) OVER (
                    PARTITION BY stint_id
                    ORDER BY lap_number
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                )
        END AS valid_lap_in_stint
    FROM with_stint_id
),

-- 08p: absolute Pirelli C1-C5 identity for the relative hard/medium/soft
-- label. NULL for all of 2018 by construction (the seed starts at 2019) and
-- for INTERMEDIATE/WET laps in every season (wets are not on the C-scale).
-- Every slick lap 2019-2024 resolves. Provenance is flagged in schema.yml:
-- the seed is user-attested, not archivally sourced, and is NON-QUOTABLE
-- per 08d/08p.
with_compound_code AS (
    SELECT
        wsl.*,
        ta.compound_code
    FROM with_stint_length AS wsl
    LEFT JOIN race_to_track AS rtt
        ON wsl.race_id = rtt.race_id
    LEFT JOIN tyre_allocations AS ta
        ON
            wsl.race_year = ta.race_year
            AND rtt.circuit_slug = ta.circuit_key
            AND LOWER(wsl.compound) = ta.compound_label
)

SELECT
    stint_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    stint_number,
    lap_in_stint,
    valid_lap_in_stint,
    tyre_life AS age_in_stint,
    compound AS compound_in_stint,
    compound_code,
    stint_length_actual,
    stint_length_valid,
    is_valid_lap,
    is_pit_lap,
    is_safety_car_lap,
    is_vsc_lap,
    is_red_flag_lap,
    CAST(NULL AS BOOLEAN) AS planned_vs_actual_flag,
    stint_source,
    tyre_qa_status
FROM with_compound_code
