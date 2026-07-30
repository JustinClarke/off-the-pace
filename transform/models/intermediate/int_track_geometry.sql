-- int_track_geometry.sql · intermediate · grain: one row per (track_id,
-- race_year, distance_bin)
-- Circuit geometry from raw X/Y/Z telemetry (unused everywhere else in the
-- warehouse): per season+circuit, median X/Y/Z in 25m distance bins, then
-- gradient (dZ/ds) and curvature (Menger, from 3 consecutive binned points).
-- lateral_accel_proxy_ms2 = v^2 * curvature (median speed at the bin).
--
-- Grain is per-season, not collapsed to a single per-circuit geometry: spot
-- checked at Bahrain, 2019's X/Y trace is offset ~300-600 units from every
-- 2020-2024 sample at the same distance bin (different GPS origin/heading
-- convention), while 2020-2024 agree with each other. Averaging across that
-- discontinuity would blend two different coordinate frames into a corrupted
-- shape. Collapsing to a single per-circuit geometry (once per-season data
-- confirms which seasons agree) is left as later work, not done here.
--
-- Start/finish-line bin has no predecessor within a season (no wraparound
-- across the lap boundary), so its gradient/curvature are NULL by construction
-- -- a deliberate edge-case simplification, not a bug.
--
-- Z is FastF1's raw telemetry unit, not verified as literal SI meters (a
-- known FastF1 quirk) -- treat gradient_dz_ds as a relative/proxy signal.
-- Shape validated at Monaco 2023: the elevation profile's climb/descent
-- matches the real circuit (rise from start/finish to Casino Square, descent
-- through the tunnel), and the single highest curvature_per_m bin coincides
-- with the lowest bin_speed_ms (~45 km/h) -- the Fairmont Hairpin, correctly
-- identified as the sharpest, slowest corner on the lap.
{{ config(materialized='table') }}

WITH race_map AS (
    SELECT * FROM {{ ref('race_to_track') }}
),

telemetry AS (
    SELECT
        t.race_id,
        CAST(t.season AS INTEGER) AS race_year,
        r.track_id,
        t.distance_m,
        t.X AS x,
        t.Y AS y,
        t.Z AS z,
        t.speed_kph
    FROM {{ source('bronze_f1', 'raw_telemetry') }} AS t
    INNER JOIN race_map AS r ON t.race_id = r.race_id
    -- Generous upper bound: real circuit lengths top out under 7100m (Spa);
    -- excludes rare out-of-range telemetry noise without clipping any track.
    WHERE t.distance_m > 0 AND t.distance_m < 8000
),

binned AS (
    SELECT
        race_year,
        track_id,
        FLOOR(distance_m / 25) * 25 AS distance_bin,
        MEDIAN(x) AS bin_x,
        MEDIAN(y) AS bin_y,
        MEDIAN(z) AS bin_z,
        MEDIAN(speed_kph) / 3.6 AS bin_speed_ms,
        COUNT(*) AS sample_count
    FROM telemetry
    GROUP BY race_year, track_id, FLOOR(distance_m / 25) * 25
),

with_neighbors AS (
    SELECT
        *,
        LAG(distance_bin) OVER w AS prev_bin,
        LAG(bin_x) OVER w AS prev_x,
        LAG(bin_y) OVER w AS prev_y,
        LAG(bin_z) OVER w AS prev_z,
        LEAD(bin_x) OVER w AS next_x,
        LEAD(bin_y) OVER w AS next_y
    FROM binned
    WINDOW w AS (PARTITION BY race_year, track_id ORDER BY distance_bin)
),

geometry AS (
    SELECT
        race_year,
        track_id,
        distance_bin,
        bin_x,
        bin_y,
        bin_z,
        bin_speed_ms,
        sample_count,
        -- Gradient dZ/ds over the actual bin spacing (usually 25m; wider where
        -- a bin had no samples).
        CASE
            WHEN prev_bin IS NOT NULL AND distance_bin > prev_bin
                THEN (bin_z - prev_z) / (distance_bin - prev_bin)
        END AS gradient_dz_ds,
        -- Menger curvature from 3 consecutive points (prev, current, next):
        -- kappa = 4*Area(triangle) / (|P1P2| * |P2P3| * |P1P3|).
        -- NULL at the first/last bin of a season (no prev/next) or where the
        -- three points are collinear/coincident (denominator 0).
        CASE
            WHEN prev_x IS NOT NULL AND next_x IS NOT NULL THEN
                (4 * ABS(
                    (bin_x - prev_x) * (next_y - prev_y)
                    - (next_x - prev_x) * (bin_y - prev_y)
                ) / 2)
                / NULLIF(
                    SQRT(POW(bin_x - prev_x, 2) + POW(bin_y - prev_y, 2))
                    * SQRT(POW(next_x - bin_x, 2) + POW(next_y - bin_y, 2))
                    * SQRT(POW(next_x - prev_x, 2) + POW(next_y - prev_y, 2)),
                    0
                )
        END AS curvature_per_m
    FROM with_neighbors
)

SELECT
    race_year,
    track_id,
    distance_bin,
    bin_x,
    bin_y,
    bin_z,
    bin_speed_ms,
    sample_count,
    gradient_dz_ds,
    curvature_per_m,
    -- Lateral-accel proxy v^2*kappa (m/s^2); NULL where curvature is NULL.
    POW(bin_speed_ms, 2) * curvature_per_m AS lateral_accel_proxy_ms2
FROM geometry
