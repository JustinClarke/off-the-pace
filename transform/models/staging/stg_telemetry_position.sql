-- stg_telemetry_position.sql · staging · grain: one row per POSITION-channel
-- telemetry sample per driver per lap (~369 samples/lap/driver).
--
-- The channel split. `raw_telemetry` interleaves three FastF1
-- sample provenances in one file: 'car' (the true car-channel cadence),
-- 'pos' (the true positional-channel cadence) and 'interpolation' (a handful
-- of synthesised joins). `stg_telemetry` projects all three un-filtered and
-- `int_lap_telemetry_aggregates` then filters to 'car', which is why the 'pos'
-- rows have never had a consumer despite being 58.8M of the 118.7M rows.
-- This model is that consumer: it is the ONLY place the 'pos' channel is
-- read, and it projects the positional columns (relative_distance, x, y) that
-- the car-channel path does not use at all.
--
-- Why 'pos' and not the merged stream: relative_distance and x/y originate on
-- the positional channel. On 'car' rows FastF1 back-fills them by
-- interpolation, so a crossing time measured off a 'car' row is a resampled
-- estimate of a number this channel already holds natively. 'pos' rows are the
-- measurement; 'car' rows are its interpolation onto a different clock.
--
-- No distance_m filter here (contrast stg_telemetry's `distance_m > 0 AND
-- < 6500`): this model's position column is relative_distance, which is a
-- 0..1 lap fraction and carries its own bound. Applying the car-channel's
-- absolute-distance guard would drop pit-lane and out-lap samples that the
-- proximity measure specifically needs to see in order to *exclude* them
-- downstream with a reason rather than silently. That exclusion lives in
-- int_lap_proximity's pit_windows / crossings_on_track (F43, WI-15a): a
-- crossing inside the driver's own stg_pits window is dropped before the
-- car-ahead ordering.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_telemetry') }}
    WHERE source = 'pos'
),

renamed AS (
    SELECT
        CAST(season AS INTEGER) AS race_year,
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(driver_id AS VARCHAR) AS driver_id,
        CAST(lap_number AS INTEGER) AS lap_number,

        -- Common session clock. Every driver on track shares it, which is what
        -- makes a cross-driver comparison possible at all: the gap between two
        -- cars is a difference of two readings of THIS column, never a
        -- difference of two distances.
        CAST(sessiontime AS DOUBLE) / 1e9 AS session_time_s,

        -- Lap fraction in [0, 1). Clamped rather than filtered: FastF1 emits a
        -- handful of samples at -3e-6 and at 1.0000004 from floating-point
        -- error at the lap boundary, and dropping them would punch a hole in
        -- exactly the bin (the start/finish line) where the gap matters most.
        LEAST(
            GREATEST(CAST(relativedistance AS DOUBLE), 0.0), 0.999999
        ) AS relative_distance,

        CAST(x AS DOUBLE) AS pos_x,
        CAST(y AS DOUBLE) AS pos_y,
        CAST(speed_kph AS DOUBLE) AS speed_kph,
        CAST(status AS VARCHAR) AS track_status,

        -- FastF1's own answer to "who is ahead and how far", kept so the new
        -- measure can be scored AGAINST it rather than merely replacing it
        -- (the ablation runs against both rather than asserting one better).
        -- driver_ahead is a car NUMBER, not the three-letter code driver_id
        -- uses; int_lap_proximity resolves it through stg_results.
        NULLIF(TRIM(CAST(driverahead AS VARCHAR)), '') AS driver_ahead_number,
        CAST(distancetodriverahead AS DOUBLE) AS distance_to_ahead_m,

        -- DA-02P (_roadmap/_dirty-air). The lap distance (m) FastF1 assigns to
        -- the sample, unfiltered (stg_telemetry cuts at 6500 m, which loses
        -- the end of a Spa lap). distance_m / relative_distance is the lap
        -- length the lap fraction was computed against;
        -- int_microsector_corner_class reads it to place the micro-sector
        -- boundaries in metres.
        CAST(distance_m AS DOUBLE) AS distance_m,

        -- DRS state of the sample. FastF1 merges the car-channel DRS code onto
        -- the position samples. Same decode as stg_telemetry.drs_state: 'off'
        -- (0, 1), 'eligible' (8: within 1 s at the detection line, may open
        -- in the next zone), 'open' (10, 12, 14), 'unknown' (any other code),
        -- NULL when the code is NULL.
        CAST(drs AS INTEGER) AS drs_code,
        CASE
            WHEN CAST(drs AS INTEGER) IN (0, 1) THEN 'off'
            WHEN CAST(drs AS INTEGER) = 8 THEN 'eligible'
            WHEN CAST(drs AS INTEGER) IN (10, 12, 14) THEN 'open'
            WHEN drs IS NOT NULL THEN 'unknown'
        END AS drs_state
    FROM source
    WHERE relativedistance IS NOT NULL
)

SELECT * FROM renamed
