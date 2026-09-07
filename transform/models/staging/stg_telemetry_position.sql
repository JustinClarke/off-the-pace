-- stg_telemetry_position.sql · staging · grain: one row per POSITION-channel
-- telemetry sample per driver per lap (~369 samples/lap/driver).
--
-- The channel split (Phase 10c). `raw_telemetry` interleaves three FastF1
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
-- downstream with a reason rather than silently.
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
        -- (Phase 10a: "run the ablation against both rather than asserted").
        -- driver_ahead is a car NUMBER, not the three-letter code driver_id
        -- uses; int_lap_proximity resolves it through stg_results.
        NULLIF(TRIM(CAST(driverahead AS VARCHAR)), '') AS driver_ahead_number,
        CAST(distancetodriverahead AS DOUBLE) AS distance_to_ahead_m
    FROM source
    WHERE relativedistance IS NOT NULL
)

SELECT * FROM renamed
