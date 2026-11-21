-- stg_telemetry_position.sql · staging · grain: one row per POSITION-channel
-- telemetry sample per driver per lap (~369 samples/lap/driver).
--
-- The channel split. `raw_telemetry` interleaves three FastF1
-- sample provenances in one file: 'car' (the true car-channel cadence),
-- 'pos' (the true positional-channel cadence) and 'interpolation' (a handful
-- of synthesised joins). `stg_telemetry` projects all three un-filtered and
-- `int_lap_telemetry_aggregates` then filters to 'car', which is why the 'pos'
-- rows had no consumer for a long time: 75.2M 'pos' rows of 233.8M in the file.
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

-- Lap length in metres, per driver-lap, from the position samples' own
-- distance_m. Used only where FastF1 left RelativeDistance NULL (16,708 rows).
-- Those rows fall in 41 driver-laps whose every distance_m is 0.0, so the lap
-- max is 0 and NO row can be derived today (a measured fact, not an assumption).
-- The derivation is kept for a future lap that has NULL RelativeDistance but a
-- positive max distance; it applies only when the lap max is greater than 0.
-- Where it does not (max is 0 or NULL), the row is kept with relative_distance
-- NULL and relative_distance_source 'unavailable': the value is unknown, and 0.0
-- would be a false position. On rows where both measures exist, distance_m / the
-- lap max differs from RelativeDistance by 0.002 on average (p99 0.008); treat
-- derived values as approximate and filter on relative_distance_source if
-- precision matters.
lap_extent AS (
    SELECT
        season, race_id, driver_id, lap_number,
        MAX(CAST(distance_m AS DOUBLE)) AS lap_max_distance_m
    FROM source
    GROUP BY season, race_id, driver_id, lap_number
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

        -- Lap fraction in [0, 1), or NULL. FastF1's RelativeDistance is used when
        -- present; out-of-range FastF1 values are clamped, not dropped, so the
        -- start/finish bin keeps its samples (relative_clamp says which ones were
        -- clamped). Where FastF1 left it NULL, it is derived from distance_m over
        -- the lap's max distance ONLY when that max is greater than 0 (flagged
        -- below). Otherwise it stays NULL, never coerced to 0.
        CASE
            WHEN relativedistance IS NOT NULL
                THEN LEAST(GREATEST(CAST(relativedistance AS DOUBLE), 0.0), 0.999999)
            WHEN lap_extent.lap_max_distance_m > 0
                THEN LEAST(
                    GREATEST(
                        CAST(source.distance_m AS DOUBLE) / lap_extent.lap_max_distance_m,
                        0.0
                    ),
                    0.999999
                )
        END AS relative_distance,

        CASE
            WHEN relativedistance IS NOT NULL THEN 'fastf1'
            WHEN lap_extent.lap_max_distance_m > 0 THEN 'derived_from_distance_m'
            ELSE 'unavailable'
        END AS relative_distance_source,

        -- Clamp flags. FastF1 has 25,526 samples below 0 and 158,831 at or above 1
        -- (not a handful: about 0.3% of pos rows). Samples at the boundary sit in the
        -- first or last bin, so consumers can exclude them.
        CASE
            WHEN CAST(relativedistance AS DOUBLE) < 0 THEN 'low'
            WHEN CAST(relativedistance AS DOUBLE) >= 1 THEN 'high'
        END AS relative_clamp,

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
    LEFT JOIN lap_extent USING (season, race_id, driver_id, lap_number)
    -- Keep a row when either position measure exists. Both NULL is 0 rows today.
    WHERE relativedistance IS NOT NULL OR source.distance_m IS NOT NULL
)

SELECT * FROM renamed
