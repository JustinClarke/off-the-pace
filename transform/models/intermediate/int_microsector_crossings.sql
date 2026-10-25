-- int_microsector_crossings.sql · intermediate · grain: one row per
-- (race, driver, lap, boundary m), m = 0 .. var('microsector_n') - 1.
-- DA-02 (_roadmap/_dirty-air/wi/DA-02-tables.md), the bridge from the ~68M
-- position samples to the micro-sector panel.
--
-- WHAT IT IS. The session clock at which a driver reaches each of
-- var('microsector_n') fixed track positions per lap (DD8, owner 2026-10-24:
-- 20, fixed for every circuit; 10 is the pre-registered sensitivity check).
-- Boundary m of lap L sits at lap fraction L + m / N on the unwrapped
-- coordinate u = lap_number + relative_distance, so boundary 0 of lap L+1 is
-- the lap line and the micro-sector m = N - 1 closes into the next lap.
--
-- WHY INTERPOLATED, NOT "FIRST SAMPLE IN THE BIN". int_lap_proximity takes the
-- first sample inside a 1/100 bin as the crossing time. The position channel
-- runs at 0.30 s (2018-19), 0.22 s (2020-21) or ~0.24 s jittered (2022+)
-- (DA-01 section 1), so that crossing is late by up to a whole sample, and the
-- bands the dirty-air cost is priced in are 0.5 s wide. Here the crossing is
-- linearly interpolated between the two samples that straddle the boundary
-- (the design note's "interpolated time at r_i"; DA-01 validated this against
-- the timing feed's sector lines, median absolute error 0.053-0.078 s).
--
-- bracket_s is the width of the straddling pair, kept so a crossing taken
-- across a data gap can be dropped downstream
-- (var('microsector_max_bracket_s'), the design note's 1 s cap on dt_i).
-- on_track is TRUE when both straddling samples have pos Status 'OnTrack'.
--
-- A boundary crossed twice (relative_distance is not strictly monotone: 203 of
-- 406,619 samples on 2023_4 step backwards) keeps its FIRST crossing. A pair
-- that jumps over more than one boundary (a data gap of more than one
-- micro-sector, 4-5 s) yields no crossing for the skipped boundary; it shows
-- up downstream as a missing next crossing, never as a made-up time.
--
-- Times are ROUNDed to 6 dp and the key is total (a driver crosses a boundary
-- of a lap at most once after the QUALIFY), so a rebuild is byte-stable.
{{ config(materialized='table', tags=['dirty_air_dynamic']) }}

{%- set n = var('microsector_n') %}

WITH pairs AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        session_time_s AS t0,
        CAST(lap_number AS DOUBLE) + relative_distance AS u0,
        track_status AS status0,
        LEAD(session_time_s) OVER w AS t1,
        LEAD(CAST(lap_number AS DOUBLE) + relative_distance) OVER w AS u1,
        LEAD(track_status) OVER w AS status1
    FROM {{ ref('stg_telemetry_position') }}
    WINDOW w AS (
        PARTITION BY race_year, race_id, driver_id
        ORDER BY session_time_s, lap_number, relative_distance
    )
),

-- Exactly one boundary between the two samples: floor(u * N) steps by 1.
straddling AS (
    SELECT
        *,
        CAST(FLOOR(u1 * {{ n }}) AS BIGINT) AS boundary_k
    FROM pairs
    WHERE
        u1 > u0
        AND t1 > t0
        AND CAST(FLOOR(u1 * {{ n }}) AS BIGINT)
        = CAST(FLOOR(u0 * {{ n }}) AS BIGINT) + 1
),

crossed AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        boundary_k // {{ n }} AS lap_number,
        boundary_k % {{ n }} AS microsector,
        boundary_k,
        ROUND(
            t0 + (boundary_k * 1.0 / {{ n }} - u0) / (u1 - u0) * (t1 - t0), 6
        ) AS crossing_time_s,
        ROUND(t1 - t0, 6) AS bracket_s,
        status0 = 'OnTrack' AND status1 = 'OnTrack' AS on_track
    FROM straddling
)

SELECT
    race_year,
    race_id,
    driver_id,
    lap_number,
    microsector,
    boundary_k,
    crossing_time_s,
    bracket_s,
    on_track
FROM crossed
QUALIFY
    ROW_NUMBER() OVER (
        PARTITION BY race_year, race_id, driver_id, boundary_k
        ORDER BY crossing_time_s, bracket_s
    ) = 1
ORDER BY race_year, race_id, driver_id, boundary_k
