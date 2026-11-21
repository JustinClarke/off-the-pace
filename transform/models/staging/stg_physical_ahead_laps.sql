-- stg_physical_ahead_laps.sql · staging · grain: one row per recorded race lap (driver x lap_number)
-- The ONLY lap input of int_lap_physical_ahead and int_physical_ahead_pairs (pit windows and the reference-lap
-- choice); the Python no longer reads bronze raw_laps directly.
--
-- Raw values are passed through unchanged under stable names (lap_time_ns, pit_in_time_ns, pit_out_time_ns,
-- deleted, compound_raw) so the pit windows and the default 'legacy' reference rule behave exactly as before.
-- The stg_laps cleaning rules are carried as FLAGS, not filters, because pit windows need pit laps and every
-- lap row must stay:
--   is_stg_valid_lap     stg_laps.is_valid_lap (timed, no pit, not deleted, accurate from 2019, no SC/VSC/red,
--                        not lap 1, and not a manual exclusion)
--   is_manual_excluded   a seed_manual_lap_exceptions row with event_type 'exclude' (HD22), which the raw
--                        Python read never saw. Used by the reference-lap rules.
--   compound_clean       stg_laps.compound (None / nan / UNKNOWN / '' -> NULL); raw 'nan' strings pass the legacy
--                        raw-compound test, which is why compound_raw is also kept.
{{ config(materialized='view') }}

SELECT
    CAST(l.season AS INTEGER) AS race_year,
    CAST(l.race_id AS VARCHAR) AS race_id,
    CAST(l.Driver AS VARCHAR) AS driver_id,
    CAST(l.LapNumber AS INTEGER) AS lap_number,
    l.LapTime AS lap_time_ns,
    l.PitInTime AS pit_in_time_ns,
    l.PitOutTime AS pit_out_time_ns,
    l.Deleted AS deleted,
    l.Compound AS compound_raw,
    l.TrackStatus AS track_status,
    s.compound AS compound_clean,
    COALESCE(s.is_valid_lap, FALSE) AS is_stg_valid_lap,
    EXISTS (
        SELECT 1
        FROM {{ ref('seed_manual_lap_exceptions') }} AS x
        WHERE x.event_type = 'exclude'
            AND x.race_year = CAST(l.season AS INTEGER)
            AND x.race_id = CAST(l.race_id AS VARCHAR)
            AND x.driver_id = CAST(l.Driver AS VARCHAR)
            AND x.lap_number = CAST(l.LapNumber AS INTEGER)
    ) AS is_manual_excluded
FROM {{ source('bronze_f1', 'raw_laps') }} AS l
LEFT JOIN {{ ref('stg_laps') }} AS s
    ON CAST(l.race_id AS VARCHAR) = s.race_id
        AND CAST(l.Driver AS VARCHAR) = s.driver_id
        AND CAST(l.LapNumber AS INTEGER) = s.lap_number
