-- stg_telemetry.sql · staging · grain: one row per telemetry sample (10 Hz)
-- Renames Bronze telemetry columns to snake_case, casts Distance from int →
-- double.
-- Source: raw_telemetry Bronze Parquet (race sessions only). No
-- aggregations.
-- Qualifying telemetry is excluded on purpose (the source glob matches race
-- files only); TX-23 handles it as stg_telemetry_qualifying.
-- Projects the powertrain channels (rpm / n_gear / drs_active) needed by the
-- per-lap
-- telemetry aggregates (int_lap_telemetry_aggregates). FastF1 DRS
-- codes:
-- 0/1 = off, 8 = eligible-but-inactive, 10/12/14 = active → drs_active.
-- drs_state (DA-02P, _roadmap/_dirty-air) keeps code 8 as its own state
-- instead of folding it into "not active": 'off' (0, 1), 'eligible' (8: the
-- car was within 1 s at the detection line and may open in the next zone),
-- 'open' (10, 12, 14), 'unknown' (any other code: 2, 3, 9, 11, 13, 15 occur
-- in bronze, a few thousand samples a season), NULL when the code is NULL.
-- drs_active is unchanged. The same decode is in stg_telemetry_position.
{{ config(materialized='view') }}

-- Plausibility bound on distance_m (TX-20, HD16). Genuine FastF1 laps run to
-- the circuit length (plus a little overrun at the line); a few laps at other
-- circuits carry runaway distance (up to ~25,000 m) and must stay out.
-- Bound = official lap length x 1.10, floored at the historic 6500 m cut so
-- that no circuit shorter than that changes. Bronze circuit_info has corner
-- geometry only, no lap length, so the lengths below are the published
-- circuit lengths, cross-checked against Bronze (per-lap max distance, p99):
-- Spa 7004 m (p99 7009, max 7164), Las Vegas 6201 m (6181, 6226), Saudi 6174 m
-- (6135, 6161), Baku 6003 m (6003, 6071). Every other circuit is under 6000 m,
-- so 6500 m already clears it with margin. A new long circuit needs a row
-- here; the test assert_stg_telemetry_distance_bound fails until it has one.
-- Before this, a fixed 6500 m cut dropped ~10% of every Spa race (Turn 18 and
-- Turn 19 at 6668 m / 6738 m).
WITH circuit_bound AS (
    SELECT
        race_slug,
        GREATEST(6500.0, CEIL(lap_length_m * 1.10)) AS max_distance_m
    FROM (
        VALUES
        ('belgian_grand_prix', 7004.0),
        ('las_vegas_grand_prix', 6201.0),
        ('saudi_arabian_grand_prix', 6174.0),
        ('azerbaijan_grand_prix', 6003.0)
    ) AS t (race_slug, lap_length_m)
),

source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_telemetry') }}
),

renamed AS (
    SELECT
        CONCAT(
            CAST(season AS VARCHAR), '_',
            CAST(race_id AS VARCHAR), '_',
            CAST(driver_id AS VARCHAR), '_',
            CAST(lap_number AS INTEGER)
        ) AS telemetry_id,

        CAST(season AS INTEGER) AS race_year,
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(driver_id AS VARCHAR) AS driver_id,
        CAST(lap_number AS INTEGER) AS lap_number,

        CAST(distance_m AS DOUBLE) AS distance_m,
        -- Sample clock. distance_m alone is NOT a total order within a lap:
        -- 1,073,311 car-channel samples (1.4% of 75.4M) share a
        -- (race, driver, lap, distance) key, because a stationary or crawling
        -- car keeps sampling at 10 Hz while distance does not advance. Any
        -- LAG/LEAD ordered on distance alone therefore picks an arbitrary
        -- neighbour, and the choice moves with DuckDB's scan parallelism.
        -- Adding this column makes (distance_m, session_time_s) unique across
        -- all 151.0M race rows (all source channels), with zero NULLs.
        CAST(sessiontime AS DOUBLE) / 1e9 AS session_time_s,
        CAST(speed_kph AS DOUBLE) AS speed_kph,
        CAST(throttle_pct AS DOUBLE) AS throttle_pct,
        CAST(brake AS BOOLEAN) AS brake_applied,

        CAST(rpm AS DOUBLE) AS rpm,
        CAST(ngear AS INTEGER) AS n_gear,
        (CAST(drs AS INTEGER) IN (10, 12, 14)) AS drs_active,
        CAST(drs AS INTEGER) AS drs_code,
        CASE
            WHEN CAST(drs AS INTEGER) IN (0, 1) THEN 'off'
            WHEN CAST(drs AS INTEGER) = 8 THEN 'eligible'
            WHEN CAST(drs AS INTEGER) IN (10, 12, 14) THEN 'open'
            WHEN drs IS NOT NULL THEN 'unknown'
        END AS drs_state,

        -- FastF1 merges 'car' (true channel cadence) with forward-filled 'pos'
        -- /
        -- 'interpolation' samples. Projected un-filtered so existing consumers
        -- are
        -- unchanged; sample-level event detection filters to 'car' downstream.
        CAST(source AS VARCHAR) AS source_channel
    FROM source
    LEFT JOIN circuit_bound ON source.race = circuit_bound.race_slug
    WHERE
        distance_m > 0
        AND distance_m < COALESCE(circuit_bound.max_distance_m, 6500.0)
)

SELECT * FROM renamed
