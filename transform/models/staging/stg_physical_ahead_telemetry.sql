-- stg_physical_ahead_telemetry.sql · staging · grain: one row per position-channel ('pos') telemetry sample
-- per driver per lap, race sessions. The ONLY telemetry input of int_lap_physical_ahead and
-- int_physical_ahead_pairs (via python_lib/physical_ahead_core.read_race_inputs); the Python no longer reads
-- bronze raw_telemetry directly.
--
-- Stable column contract (renames only, no value changes): session_time_s is SessionTime / 1e9, x / y are the
-- raw X / Y (units 1/10 m), sample_index is FastF1's row index (the tiebreak for equal timestamps).
-- is_zero_xy marks X = Y = 0 placeholder rows. Nothing is dropped here: the guard that removes them is the
-- model's drop_zero_xy setting (default off, unvalidated, see the core header), so default output is unchanged.
-- Not stg_telemetry_position: that view derives lap fractions and filters rows, and has no sample_index.
{{ config(materialized='view') }}

SELECT
    CAST(season AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(driver_id AS VARCHAR) AS driver_id,
    CAST(lap_number AS INTEGER) AS lap_number,
    SessionTime / 1e9 AS session_time_s,
    X AS x,
    Y AS y,
    "index" AS sample_index,
    COALESCE(X = 0 AND Y = 0, FALSE) AS is_zero_xy
FROM {{ source('bronze_f1', 'raw_telemetry') }}
WHERE Source = 'pos'
