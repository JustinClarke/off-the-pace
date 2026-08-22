-- stg_pits.sql · staging · grain: one row per pit stop (race sessions)
-- A stop is a lap carrying PitInTime. Bronze splits each stop across two lap
-- rows — PitInTime on the in-lap, PitOutTime on the following out-lap — so the
-- exit side is resolved with a LEAD over the driver's own pit laps rather than
-- read off the in-lap row, and out-lap-only rows (including the 107 pit-lane
-- race starts) are not stops and do not survive to the output.
--
-- pit_in_lap_number: lap on which the car entered the pit lane.
-- pit_out_lap_number: lap on which it exited, always pit_in_lap_number + 1
--   where an out-lap exists at all; NULL for the 227 stops where none does
--   (car retired in the pit lane, or the race ended under the stop).
-- pit_duration_s: pit entry to pit exit, so it spans the whole pit lane, not
--   just the stationary time. Red-flag stoppages and garage returns are inside
--   the car's pit window and inflate it — 388 of 5,109 stops exceed 60 s.
--   Consumers wanting a green-flag service time must filter.
-- No joins, no aggregations; the LEAD reads only this model's own rows.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_laps') }}
),

pit_laps AS (
    SELECT
        CONCAT(
            CAST(season AS VARCHAR), '_',
            CAST(race_id AS VARCHAR), '_',
            CAST(driver AS VARCHAR), '_',
            CAST(CAST(lapnumber AS INTEGER) AS VARCHAR)
        ) AS lap_id,

        CAST(season AS INTEGER) AS race_year,
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(driver AS VARCHAR) AS driver_id,
        CAST(lapnumber AS INTEGER) AS lap_number,
        CAST(stint AS INTEGER) AS stint_number,
        UPPER(CAST(compound AS VARCHAR)) AS compound,

        -- Pit times (nanoseconds → seconds)
        CASE
            WHEN
                pitintime IS NOT NULL
                THEN CAST(pitintime AS DOUBLE) / 1e9
        END AS pit_in_time_s,
        CASE
            WHEN
                pitouttime IS NOT NULL
                THEN CAST(pitouttime AS DOUBLE) / 1e9
        END AS pit_out_time_s

    FROM source
    WHERE pitintime IS NOT NULL OR pitouttime IS NOT NULL
),

-- Pair each pit lap with the driver's next one. A row is the in-lap of a real
-- stop when it carries PitInTime and its successor is the very next lap with
-- an exit stamp; a successor further away means the out-lap was never
-- recorded, and the exit side stays NULL rather than being assumed.
with_exit AS (
    SELECT
        *,
        LEAD(lap_number) OVER (
            PARTITION BY race_year, race_id, driver_id ORDER BY lap_number
        ) AS next_pit_lap_number,
        LEAD(pit_out_time_s) OVER (
            PARTITION BY race_year, race_id, driver_id ORDER BY lap_number
        ) AS next_pit_out_time_s,
        LEAD(compound) OVER (
            PARTITION BY race_year, race_id, driver_id ORDER BY lap_number
        ) AS next_compound
    FROM pit_laps
),

resolved AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number AS pit_in_lap_number,
        stint_number,
        pit_in_time_s,
        -- The set removed at this stop. Bronze reports each lap's own rubber,
        -- so the in-lap carries the tyre coming off, not the one going on —
        -- the two differ on 3,844 of 5,109 stops. The tyre fitted is
        -- compound_out below, read from the out-lap.
        compound AS compound_in,
        CASE
            WHEN next_pit_lap_number = lap_number + 1
                THEN next_pit_lap_number
        END AS pit_out_lap_number,
        CASE
            WHEN next_pit_lap_number = lap_number + 1
                THEN next_pit_out_time_s
        END AS pit_out_time_s,
        CASE
            WHEN next_pit_lap_number = lap_number + 1
                THEN next_compound
        END AS compound_out,
        CASE
            WHEN next_pit_lap_number = lap_number + 1
                THEN next_pit_out_time_s - pit_in_time_s
        END AS pit_duration_s
    FROM with_exit
    WHERE pit_in_time_s IS NOT NULL
)

SELECT * FROM resolved
