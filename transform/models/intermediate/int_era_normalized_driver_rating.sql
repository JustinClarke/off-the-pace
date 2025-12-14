-- Era-normalised driver rating model: Era-normalised driver rating (cross-season comparable).
--
-- Two-part hierarchy:
--   First part: Per-(driver, season) shrunk residual from int_driver_season_ratings.
--   Second part: Cross-era calibration anchored on "bridge drivers" drivers with
--            ≥8 clean races in both pre-2022 and post-2022 eras. The average
--            shift in their shrunk residual across the 2022 regulation boundary
--            is the era offset applied to all pre-2022 seasons.
--
-- Regulation boundary: 2022 (ground-effect regulation change). Pre-era: 2018–2021.
-- Post-era: 2022–2024. If fewer than 3 bridge drivers are found the era offset
-- is set to 0 and low_anchor_sample_flag = TRUE.
--
-- Output grain: (driver_id, season). One row per driver-season.
-- PK: driver_season_id (same surrogate as int_driver_season_ratings).
--
-- era_adjusted_rating: negative = faster than era-normalised field average.
-- bridge_driver_anchor_flag: TRUE if this driver-season was used to estimate the offset.

{{ config(materialized='table', tags=['driver_rating', 'era_rating']) }}

WITH season_ratings AS (
    SELECT
        driver_season_id,
        driver_id,
        season,
        n_races,
        total_clean_laps_n,
        raw_residual_mean_s,
        shrunk_residual_s,
        shrunk_residual_se_s,
        shrunk_residual_ci_low_s,
        shrunk_residual_ci_high_s,
        rating_confidence
    FROM {{ ref('int_driver_season_ratings') }}
),

-- Bridge driver identification:
-- Drivers with ≥8 races in pre-era (2018–2021) AND ≥8 races in post-era (2022–2024).
driver_era_counts AS (
    SELECT
        driver_id,
        SUM(CASE WHEN season < 2022 THEN n_races ELSE 0 END)  AS pre_era_races,
        SUM(CASE WHEN season >= 2022 THEN n_races ELSE 0 END) AS post_era_races
    FROM season_ratings
    GROUP BY driver_id
),

bridge_drivers AS (
    SELECT driver_id
    FROM driver_era_counts
    WHERE pre_era_races  >= 8
      AND post_era_races >= 8
),

-- For each bridge driver, compute average shrunk residual per era
bridge_era_means AS (
    SELECT
        sr.driver_id,
        AVG(CASE WHEN sr.season < 2022  THEN sr.shrunk_residual_s END) AS pre_era_mean_s,
        AVG(CASE WHEN sr.season >= 2022 THEN sr.shrunk_residual_s END) AS post_era_mean_s
    FROM season_ratings sr
    JOIN bridge_drivers  bd USING (driver_id)
    GROUP BY sr.driver_id
),

-- Per bridge driver: era shift = pre-era mean − post-era mean
-- Positive shift means pre-era looks slower (different car-era baseline)
bridge_shifts AS (
    SELECT
        driver_id,
        pre_era_mean_s -post_era_mean_s    AS era_shift_s
    FROM bridge_era_means
    WHERE pre_era_mean_s  IS NOT NULL
      AND post_era_mean_s IS NOT NULL
),

-- Global era offset: mean shift across all bridge drivers
era_offset AS (
    SELECT
        AVG(era_shift_s)                            AS era_shift_global_s,
        STDDEV(era_shift_s)                         AS era_shift_stddev_s,
        COUNT(*)                                    AS n_bridge_drivers,
        STDDEV(era_shift_s)
            / NULLIF(SQRT(COUNT(*)), 0)             AS era_shift_se_s,
        COUNT(*) < 3                                AS low_anchor_sample_flag
    FROM bridge_shifts
),

-- Apply the era offset to every pre-2022 driver-season
-- Post-2022 seasons are the reference; pre-2022 are shifted down
with_era_adjustment AS (
    SELECT
        sr.driver_season_id,
        sr.driver_id,
        sr.season,
        sr.n_races,
        sr.total_clean_laps_n,
        sr.raw_residual_mean_s,
        sr.shrunk_residual_s,
        sr.shrunk_residual_se_s,
        sr.rating_confidence,

        eo.era_shift_global_s,
        eo.era_shift_se_s,
        eo.n_bridge_drivers,
        eo.low_anchor_sample_flag,

        -- Apply offset only to pre-2022 seasons; if low anchor, offset is 0
        sr.shrunk_residual_s
         -CASE
              WHEN sr.season < 2022 AND NOT eo.low_anchor_sample_flag
              THEN COALESCE(eo.era_shift_global_s, 0)
              ELSE 0
            END                               AS era_adjusted_rating,

        -- Propagate SE: sqrt(shrunk_se² + era_shift_se² [if pre-era])
        CASE
            WHEN sr.season < 2022 AND NOT eo.low_anchor_sample_flag
            THEN SQRT(
                POWER(COALESCE(sr.shrunk_residual_se_s, 0), 2)
              + POWER(COALESCE(eo.era_shift_se_s, 0), 2)
            )
            ELSE COALESCE(sr.shrunk_residual_se_s, 0)
        END                                   AS era_adjusted_rating_se_s,

        bd.driver_id IS NOT NULL              AS bridge_driver_anchor_flag

    FROM season_ratings    sr
    CROSS JOIN era_offset  eo
    LEFT JOIN bridge_drivers bd              ON sr.driver_id = bd.driver_id
)

SELECT
    driver_season_id,
    driver_id,
    season,
    n_races,
    total_clean_laps_n,
    raw_residual_mean_s,
    shrunk_residual_s,
    shrunk_residual_se_s,
    era_adjusted_rating,
    era_adjusted_rating_se_s,

    -- 95% CI on era-adjusted rating
    era_adjusted_rating-1.96 * era_adjusted_rating_se_s    AS era_adjusted_rating_ci_low_s,
    era_adjusted_rating + 1.96 * era_adjusted_rating_se_s    AS era_adjusted_rating_ci_high_s,

    rating_confidence,
    bridge_driver_anchor_flag,

    -- Audit columns
    era_shift_global_s,
    era_shift_se_s,
    n_bridge_drivers,
    low_anchor_sample_flag

FROM with_era_adjustment
ORDER BY season DESC, era_adjusted_rating ASC
