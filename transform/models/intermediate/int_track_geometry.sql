-- int_track_geometry.sql · intermediate · grain: one row per (track_id,
-- race_year, distance_bin)
-- Circuit geometry from raw X/Y/Z telemetry (unused everywhere else in the
-- warehouse): per season+circuit, median X/Y/Z in 25m distance bins, then
-- gradient (dZ/ds) and curvature (Menger, from 3 consecutive binned points).
-- lateral_accel_proxy_ms2 = v^2 * curvature (median speed at the bin).
--
-- Grain is per-season, not collapsed to a single per-circuit geometry: spot
-- checked at Bahrain, 2019's X/Y trace is offset ~300-600 raw units (30-60 m) from every
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
-- Units: Bronze X, Y and Z are in 1/10 metre (FastF1 position data), not
-- metres (ingestion/SCHEMA.md says metres for X/Y; that is wrong). Checked at
-- Bahrain 2023 (VER lap 10): X/Y path 53,388 raw units over 5,360 m of lap
-- distance, ratio 9.96. Z is confirmed 1/10 m as well: the 1-99 percentile
-- raw Z range is 167 at Bahrain, 416 Monaco, 1020 Spa, 634 Austria, 22 Saudi
-- (flat), and Mexico sits at ~22,270 raw, i.e. ~2,227 m altitude -- all match
-- real elevation only when divided by 10. The telemetry CTE converts x, y, z
-- to metres once, so bin_x/bin_y/bin_z, gradient_dz_ds, curvature_per_m and
-- lateral_accel_proxy_ms2 are all in SI units. (Z absolute level is a GPS
-- datum, so use gradient/relative height, not absolute altitude.)
-- Shape validated at Monaco 2023: the elevation profile's climb/descent
-- matches the real circuit (rise from start/finish to Casino Square, descent
-- through the tunnel), and the single highest curvature_per_m bin coincides
-- with the lowest bin_speed_ms (~45 km/h) -- the Fairmont Hairpin, correctly
-- identified as the sharpest, slowest corner on the lap.
--
-- SEASON SCOPE (G4). Only seasons in var('model_seasons') (dbt_project.yml,
-- default 2018-2025) are modelled. Bronze telemetry also holds 2026 races,
-- which have no race_to_track rows; they used to vanish through the INNER JOIN
-- to race_to_track without a trace. The exclusion is now the explicit season
-- filter in the telemetry CTE below. The race_to_track seed is unchanged and
-- must carry a row for every race of a modelled season.
--
-- CURVATURE GUARDS (G3), both thresholds computed from the data in this
-- model, not fixed numbers:
--   (a) low_sample_count: a bin with sample_count below the lower decile (10th
--       percentile) of sample_count over ALL bins in this table has an
--       unreliable median position; its curvature and lateral acceleration
--       are NULL.
--   (b) small_side_product: the Menger denominator is the product of the three
--       side lengths. Where it is below the 1st percentile of that product
--       over all bins where it is defined, the three points are nearly
--       coincident and the ratio explodes; curvature is NULL.
-- curvature_guard_reason names the guard(s) that NULLed the bin
-- ('low_sample_count', 'small_side_product' or
-- 'low_sample_count+small_side_product'); it is NULL where no guard fired
-- (including bins whose curvature is NULL for lack of a neighbour).
-- Gradient is the change in Z from the PREVIOUS bin to the current bin,
-- divided by the bin spacing.
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
        -- Source X/Y/Z are in 1/10 m; convert to metres here, once.
        t.x / 10.0 AS x,
        t.y / 10.0 AS y,
        t.z / 10.0 AS z,
        t.speed_kph
    FROM {{ source('bronze_f1', 'raw_telemetry') }} AS t
    INNER JOIN race_map AS r ON t.race_id = r.race_id
    -- G4: explicit season scope (see header), not an accident of the join.
    -- Generous upper bound: real circuit lengths top out under 7100m (Spa);
    -- excludes rare out-of-range telemetry noise without clipping any track.
    WHERE
        CAST(t.season AS INTEGER) IN ({{ var('model_seasons') | join(', ') }})
        AND t.distance_m > 0 AND t.distance_m < 8000
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

sided AS (
    SELECT
        *,
        -- Product of the three side lengths P1P2, P2P3, P1P3: the Menger
        -- denominator. NULL without both neighbours.
        CASE
            WHEN prev_x IS NOT NULL AND next_x IS NOT NULL THEN
                SQRT(POW(bin_x - prev_x, 2) + POW(bin_y - prev_y, 2))
                * SQRT(POW(next_x - bin_x, 2) + POW(next_y - bin_y, 2))
                * SQRT(POW(next_x - prev_x, 2) + POW(next_y - prev_y, 2))
        END AS side_product_m3
    FROM with_neighbors
),

-- G3: data-derived thresholds over every bin in the table.
guard_limits AS (
    SELECT
        QUANTILE_CONT(sample_count, 0.10) AS min_sample_count,
        QUANTILE_CONT(side_product_m3, 0.01) AS min_side_product_m3
    FROM sided
),

geometry AS (
    SELECT
        s.race_year,
        s.track_id,
        s.distance_bin,
        s.bin_x,
        s.bin_y,
        s.bin_z,
        s.bin_speed_ms,
        s.sample_count,
        -- Gradient dZ/ds from the PREVIOUS bin to the current bin, over the
        -- actual bin spacing (usually 25m; wider where a bin had no samples).
        CASE
            WHEN s.prev_bin IS NOT NULL AND s.distance_bin > s.prev_bin
                THEN (s.bin_z - s.prev_z) / (s.distance_bin - s.prev_bin)
        END AS gradient_dz_ds,
        -- Menger curvature from 3 consecutive points (prev, current, next):
        -- kappa = 4*Area(triangle) / (|P1P2| * |P2P3| * |P1P3|).
        -- NULL at the first/last bin of a season (no prev/next), where the
        -- three points are coincident (denominator 0), or where a G3 guard
        -- fires (see header).
        CASE
            WHEN
                s.prev_x IS NOT NULL AND s.next_x IS NOT NULL
                AND s.sample_count >= g.min_sample_count
                AND s.side_product_m3 >= g.min_side_product_m3
                THEN
                    (4 * ABS(
                        (s.bin_x - s.prev_x) * (s.next_y - s.prev_y)
                        - (s.next_x - s.prev_x) * (s.bin_y - s.prev_y)
                    ) / 2)
                    / NULLIF(s.side_product_m3, 0)
        END AS curvature_per_m,
        CASE
            WHEN s.prev_x IS NULL OR s.next_x IS NULL THEN NULL
            WHEN
                s.sample_count < g.min_sample_count
                AND s.side_product_m3 < g.min_side_product_m3
                THEN 'low_sample_count+small_side_product'
            WHEN s.sample_count < g.min_sample_count THEN 'low_sample_count'
            WHEN s.side_product_m3 < g.min_side_product_m3
                THEN 'small_side_product'
        END AS curvature_guard_reason
    FROM sided AS s
    CROSS JOIN guard_limits AS g
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
    curvature_guard_reason,
    -- Lateral-accel proxy v^2*kappa (m/s^2); NULL where curvature is NULL.
    POW(bin_speed_ms, 2) * curvature_per_m AS lateral_accel_proxy_ms2
FROM geometry
