-- TX-02. Race coverage: one row per race_to_track race, saying what was
-- measured and, when a race has no rating or thin residuals, why. Grain:
-- race_id. Every column is derived from the warehouse, never from a hand list
-- of race ids.
--
-- has_telemetry: share of int_lap_air_state laps with a measured air state
--   above var('isolation_thin_min_air_measured_share') (0.5). 2018_1 and
--   2018_2 are about 6% (no telemetry in bronze, KNOWN_TELEMETRY_GAPS in
--   ingestion/src/bronze_checks.py); every other race is 94% or more.
-- tyre_qa_status: 'quarantined_race' when stg_lap_tyre_qa quarantines the
--   race, 'partial' when any driver-race is quarantined, else 'ok'.
-- bronze_tyre_life_share: share of race laps with a bronze TyreLife. Below
--   0.90 (bronze_checks MIN_LAP_KEY_SHARE) the load is thin; the owner
--   accepted 2022_7 and 2022_11 as exceptions (KNOWN_THIN, 2026-10-22).
--
-- coverage_reason, first match wins:
--   SOURCE_UNAVAILABLE    no stg_laps rows at all: Bronze holds no race laps
--                         because the source could not deliver the session
--                         (ingestion/known_gaps.txt; HD15 option B, TX-16:
--                         2018_14 Italian GP). Shown as unavailable with this
--                         reason, never as zero laps.
--   NO_RACING_LAPS        no fct_lap_residuals rows at all.
--   NO_USABLE_LAPS        lap rows exist but none is ml_eligible and none
--                         carries a driver_skill_residual_s, so nothing can be
--                         rated. Never labelled OK. 2021_12 (Spa) is the
--                         example: it has 20 fct_lap_residuals rows (60
--                         stg_laps rows, only lap 1 has a lap time, and
--                         stg_laps.is_valid_lap excludes lap 1), 0 ml-eligible
--                         laps and 0 residuals.
--   ALL_WET_NO_DRY_PAIRS  no rating and a majority of laps under rainfall:
--                         the rating's clean panel drops rain laps (2021_16).
--                         Other wet races that still have a rating are OK.
--   NO_TELEMETRY          has_telemetry FALSE.
--   TYRE_QA_QUARANTINED   tyre_qa_status = 'quarantined_race'.
--   TYRE_LIFE_PARTIAL     bronze_tyre_life_share < 0.90.
--   OK                    none of the above.
{{ config(materialized='table') }}

{% set min_tyre_life_share = 0.90 %}

WITH races AS (
    SELECT
        race_id,
        track_id AS circuit_key,
        CAST(SPLIT_PART(race_id, '_', 1) AS INTEGER) AS race_year
    FROM {{ ref('race_to_track') }}
),

-- TX-16: laps Bronze delivered for the race, before any filter. 0 means the
-- source delivered nothing (SOURCE_UNAVAILABLE), not that filters removed it.
bronze_laps AS (
    SELECT
        race_id,
        COUNT(*) AS n_bronze_lap_rows
    FROM {{ ref('stg_laps') }}
    GROUP BY race_id
),

laps AS (
    SELECT
        race_id,
        COUNT(*) AS n_lap_rows,
        COUNT(*) FILTER (WHERE ml_eligible) AS n_ml_eligible_laps,
        AVG(CASE WHEN base_track_pace_s IS NOT NULL THEN 1.0 ELSE 0.0 END)
            AS base_measured_share,
        AVG(
            CASE WHEN driver_skill_residual_s IS NOT NULL THEN 1.0 ELSE 0.0 END
        ) AS residual_measured_share,
        AVG(CASE WHEN rainfall_flag THEN 1.0 ELSE 0.0 END) AS rain_lap_share
    FROM {{ ref('fct_lap_residuals') }}
    GROUP BY race_id
),

air AS (
    SELECT
        race_id,
        AVG(CASE WHEN air_state_dominant IS NOT NULL THEN 1.0 ELSE 0.0 END)
            AS air_measured_share
    FROM {{ ref('int_lap_air_state') }}
    GROUP BY race_id
),

tyre AS (
    SELECT
        race_id,
        COUNT(*) FILTER (WHERE tyre_qa_status = 'quarantined_race')
            AS n_quarantined_race_laps,
        COUNT(*) FILTER (WHERE tyre_qa_status = 'quarantined_driver')
            AS n_quarantined_driver_laps,
        AVG(CASE WHEN bronze_tyre_life IS NOT NULL THEN 1.0 ELSE 0.0 END)
            AS bronze_tyre_life_share
    FROM {{ ref('stg_lap_tyre_qa') }}
    GROUP BY race_id
),

-- Rated drivers: the rows mart_race_driver_summary keeps (its ratings CTE).
-- Read from the intermediate, not the mart, because the mart reads this
-- model for its residual_unavailable_reason.
rated AS (
    SELECT
        race_id,
        COUNT(*) AS n_rated_drivers
    FROM {{ ref('int_driver_race_skill_loro') }}
    WHERE driver_skill_loro_s IS NOT NULL
    GROUP BY race_id
),

joined AS (
    SELECT
        r.race_id,
        r.race_year,
        dc.circuit_id,
        COALESCE(bl.n_bronze_lap_rows, 0) AS n_bronze_lap_rows,
        COALESCE(l.n_lap_rows, 0) AS n_lap_rows,
        COALESCE(l.n_ml_eligible_laps, 0) AS n_ml_eligible_laps,
        l.base_measured_share,
        l.residual_measured_share,
        l.rain_lap_share,
        a.air_measured_share,
        t.bronze_tyre_life_share,
        CASE
            WHEN t.n_quarantined_race_laps > 0 THEN 'quarantined_race'
            WHEN t.n_quarantined_driver_laps > 0 THEN 'partial'
            WHEN t.race_id IS NOT NULL THEN 'ok'
        END AS tyre_qa_status,
        COALESCE(a.air_measured_share, 0.0)
        > {{ var('isolation_thin_min_air_measured_share') }} AS has_telemetry,
        COALESCE(rt.n_rated_drivers, 0) AS n_rated_drivers,
        rt.race_id IS NOT NULL AS has_rating
    FROM races AS r
    LEFT JOIN bronze_laps AS bl ON r.race_id = bl.race_id
    LEFT JOIN laps AS l ON r.race_id = l.race_id
    LEFT JOIN air AS a ON r.race_id = a.race_id
    LEFT JOIN tyre AS t ON r.race_id = t.race_id
    LEFT JOIN rated AS rt ON r.race_id = rt.race_id
    LEFT JOIN {{ ref('dim_circuits') }} AS dc
        ON r.circuit_key = dc.circuit_key
)

SELECT
    *,
    CASE
        WHEN n_bronze_lap_rows = 0 THEN 'SOURCE_UNAVAILABLE'
        WHEN n_lap_rows = 0 THEN 'NO_RACING_LAPS'
        WHEN n_ml_eligible_laps = 0 AND COALESCE(residual_measured_share, 0) = 0
            THEN 'NO_USABLE_LAPS'
        WHEN NOT has_rating AND rain_lap_share > 0.5
            THEN 'ALL_WET_NO_DRY_PAIRS'
        WHEN NOT has_telemetry THEN 'NO_TELEMETRY'
        WHEN tyre_qa_status = 'quarantined_race' THEN 'TYRE_QA_QUARANTINED'
        WHEN bronze_tyre_life_share < {{ min_tyre_life_share }}
            THEN 'TYRE_LIFE_PARTIAL'
        ELSE 'OK'
    END AS coverage_reason
FROM joined
ORDER BY race_year, race_id
