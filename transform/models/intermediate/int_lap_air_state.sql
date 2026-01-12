-- Layer 03: Air state classification and dirty-air thermal load.
-- Gap-to-car-ahead is taken directly from telemetry DistanceToDriverAhead (meters),
-- converted to seconds using point speed: gap_s = distance_m / (speed_kph / 3.6).
-- Sectors are approximated by relative distance thirds (S1: 0–33%, S2: 33–67%, S3: 67–100%)
-- since precise sector boundary distances are not available in telemetry.
-- EW thermal loads use finite weighted sums partitioned on stint_id so load resets at each stop.
{{ config(materialized='table') }}

WITH geom AS (
    SELECT stint_id, lap_id, race_year, race_id, driver_id, lap_number, lap_in_stint
    FROM {{ ref('int_stint_geometry') }}
),

telemetry AS (
    SELECT
        race_id,
        CAST(season AS INTEGER)             AS race_year,
        driver_id,
        CAST(lap_number AS INTEGER)         AS lap_number,
        speed_kph,
        distance_m,
        RelativeDistance                    AS relative_distance,
        DistanceToDriverAhead               AS distance_to_ahead_m,
        -- Convert to time gap (s); null when car is stationary or gap unavailable
        CASE
            WHEN DistanceToDriverAhead IS NOT NULL AND speed_kph > 1.0
                THEN DistanceToDriverAhead / (speed_kph / 3.6)
            ELSE NULL
        END                                 AS gap_to_ahead_s,
        -- Sector proxy by relative distance thirds
        CASE
            WHEN RelativeDistance < 0.33 THEN 1
            WHEN RelativeDistance < 0.67 THEN 2
            ELSE 3
        END                                 AS sector_proxy,
        DRS
    FROM {{ source('bronze_f1', 'raw_telemetry') }}
    WHERE speed_kph > 0
),

-- Aggregate per lap × sector_proxy: median gap and DRS state
sector_agg AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        sector_proxy                        AS sector,
        -- Median gap per sector (robust to outliers from backmarker passes)
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gap_to_ahead_s)
            FILTER (WHERE gap_to_ahead_s IS NOT NULL)
                                            AS gap_median_s,
        COUNT(*) FILTER (WHERE gap_to_ahead_s IS NOT NULL) AS gap_sample_count,
        -- DRS active: FastF1 encodes active DRS as values 10, 12, 14
        MAX(CASE WHEN DRS IN (10, 12, 14) THEN 1 ELSE 0 END) AS drs_active
    FROM telemetry
    GROUP BY race_year, race_id, driver_id, lap_number, sector_proxy
),

-- Classify each sector by air state
sector_classified AS (
    SELECT
        *,
        CASE
            WHEN gap_median_s IS NULL OR gap_median_s > 2.0 THEN 'free_air'
            WHEN gap_median_s < 1.0 AND drs_active = 1      THEN 'drs_train'
            WHEN gap_median_s < 1.0 AND sector != 2          THEN 'tow_zone'
            WHEN gap_median_s < 1.5 AND sector = 2           THEN 'dirty_air'
            ELSE 'free_air'
        END AS sector_air_state,
        -- Dirty air intensity (S2 only): inverse distance, floored at 0.3s gap
        CASE
            WHEN sector = 2 AND gap_median_s IS NOT NULL AND gap_median_s < 1.5
                THEN 1.0 / GREATEST(gap_median_s, 0.3)
            ELSE 0.0
        END AS dirty_air_intensity_sector
    FROM sector_agg
),

-- Aggregate to lap level
lap_air AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        -- Share of S2 sectors classified as dirty air (0 or 1 since one S2 per lap)
        MAX(CASE WHEN sector = 2 AND sector_air_state = 'dirty_air' THEN 1.0 ELSE 0.0 END)
                                            AS dirty_air_share_lap,
        -- Tow benefit: negative (saves time) when in tow_zone on straight sectors
        SUM(CASE WHEN sector_air_state = 'tow_zone' THEN -0.15 ELSE 0.0 END)
                                            AS tow_benefit_lap_s,
        MAX(dirty_air_intensity_sector)     AS dirty_air_intensity,
        -- Modal sector state
        MODE() WITHIN GROUP (ORDER BY sector_air_state) AS air_state_dominant,
        MIN(gap_median_s)                   AS min_gap_s
    FROM sector_classified
    GROUP BY race_year, race_id, driver_id, lap_number
),

-- Join lap-level air state back to stint geometry for ordered windows
with_stint AS (
    SELECT
        g.stint_id,
        g.lap_id,
        g.race_year,
        g.race_id,
        g.driver_id,
        g.lap_number,
        g.lap_in_stint,
        COALESCE(a.dirty_air_share_lap, 0.0)    AS dirty_air_share_lap,
        COALESCE(a.tow_benefit_lap_s, 0.0)      AS tow_benefit_lap_s,
        COALESCE(a.dirty_air_intensity, 0.0)    AS dirty_air_intensity,
        COALESCE(a.air_state_dominant, 'free_air') AS air_state_dominant,
        a.min_gap_s
    FROM geom g
    LEFT JOIN lap_air a
        ON g.race_year  = a.race_year
        AND g.race_id   = a.race_id
        AND g.driver_id = a.driver_id
        AND g.lap_number = a.lap_number
),

-- EW thermal loads finite weighted sum approximation partitioned by stint.
-- Surface: α=0.6, 5-lap lookback. Bulk: α=0.25, 10-lap lookback.
thermal AS (
    SELECT
        *,
        -- Surface load (α=0.6): weights = 0.6, 0.24, 0.096, 0.038, 0.015
        ROUND(
            0.600 * dirty_air_intensity
            + 0.240 * COALESCE(LAG(dirty_air_intensity, 1) OVER w, 0)
            + 0.096 * COALESCE(LAG(dirty_air_intensity, 2) OVER w, 0)
            + 0.038 * COALESCE(LAG(dirty_air_intensity, 3) OVER w, 0)
            + 0.015 * COALESCE(LAG(dirty_air_intensity, 4) OVER w, 0),
        4) AS dirty_air_thermal_load_surface,

        -- Bulk load (α=0.25): weights decay slowly-0.25, 0.1875, 0.141, ...
        ROUND(
            0.2500 * dirty_air_intensity
            + 0.1875 * COALESCE(LAG(dirty_air_intensity,  1) OVER w, 0)
            + 0.1406 * COALESCE(LAG(dirty_air_intensity,  2) OVER w, 0)
            + 0.1055 * COALESCE(LAG(dirty_air_intensity,  3) OVER w, 0)
            + 0.0791 * COALESCE(LAG(dirty_air_intensity,  4) OVER w, 0)
            + 0.0593 * COALESCE(LAG(dirty_air_intensity,  5) OVER w, 0)
            + 0.0445 * COALESCE(LAG(dirty_air_intensity,  6) OVER w, 0)
            + 0.0334 * COALESCE(LAG(dirty_air_intensity,  7) OVER w, 0)
            + 0.0250 * COALESCE(LAG(dirty_air_intensity,  8) OVER w, 0)
            + 0.0188 * COALESCE(LAG(dirty_air_intensity,  9) OVER w, 0),
        4) AS dirty_air_thermal_load_bulk

    FROM with_stint
    WINDOW w AS (
        PARTITION BY stint_id
        ORDER BY lap_in_stint
        ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
    )
)

SELECT
    stint_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    lap_in_stint,
    dirty_air_share_lap,
    tow_benefit_lap_s,
    dirty_air_thermal_load_surface,
    dirty_air_thermal_load_bulk,
    air_state_dominant,
    min_gap_s
FROM thermal
