-- Driver-season rating on one scale across the 2022 regulation boundary.
--
-- era_adjusted_rating = shrunk_residual_s from int_driver_season_ratings,
-- with NO era offset (WI-14b, F45). The rating is teammate-relative: each
-- race's input is the driver's median lap-by-lap gap to his teammate in the
-- same car (int_driver_race_skill_loro, F40). A change of car era moves both
-- teammates alike and cancels inside every pair, so there is no era level to
-- remove, and the scale is the same on both sides of 2022 without one.
--
-- What was removed, and why. The model used to subtract a "bridge driver"
-- offset (mean pre-minus-post shift of drivers with >= 8 races in both eras)
-- from every pre-2022 driver-season whenever >= 3 bridge drivers existed,
-- with no significance gate. It was -0.1153 s at t = -1.5 (driven by one
-- driver's change of teammate, MSC), and it moved the field-mean gap across
-- the boundary from -0.044 s to +0.071 s: it inverted the gap it claimed to
-- remove. assert_era_offset_shrinks_gap (T35) fails if an offset comes back
-- ungated (|t| < 2) or widens / inverts the field-mean gap.
--
-- The bridge-driver shift is still MEASURED and published as diagnostics
-- (era_shift_global_s, era_shift_se_s, n_bridge_drivers,
-- low_anchor_sample_flag) so the "is there an era step?" question stays
-- visible; none of them moves era_adjusted_rating.
--
-- Regulation boundary: var('era_boundary', 2022). Pre-era: seasons < 2022.
-- Post-era: seasons >= 2022.
--
-- Output grain: (driver_id, season). One row per driver-season.
-- PK: driver_season_id (same surrogate as int_driver_season_ratings).
--
-- era_adjusted_rating: seconds, negative = faster than his teammate(s),
-- season average, shrunk toward the season mean.
-- bridge_driver_anchor_flag: TRUE if the driver raced >= 8 races on each side
-- of the boundary (the population behind the diagnostic shift).

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
-- Drivers with ≥8 races before the boundary AND ≥8 races from it on.
driver_era_counts AS (
    SELECT
        driver_id,
        SUM(
            CASE
                WHEN season < {{ var('era_boundary', 2022) }} THEN n_races ELSE
                    0
            END
        )
            AS pre_era_races,
        SUM(
            CASE
                WHEN season >= {{ var('era_boundary', 2022) }} THEN n_races ELSE
                    0
            END
        )
            AS post_era_races
    FROM season_ratings
    GROUP BY driver_id
),

bridge_drivers AS (
    SELECT driver_id
    FROM driver_era_counts
    WHERE
        pre_era_races >= 8
        AND post_era_races >= 8
),

-- For each bridge driver, compute average shrunk residual per era
bridge_era_means AS (
    SELECT
        sr.driver_id,
        AVG(
            CASE
                WHEN
                    sr.season < {{ var('era_boundary', 2022) }}
                    THEN sr.shrunk_residual_s
            END
        )
            AS pre_era_mean_s,
        AVG(
            CASE
                WHEN
                    sr.season >= {{ var('era_boundary', 2022) }}
                    THEN sr.shrunk_residual_s
            END
        )
            AS post_era_mean_s
    FROM season_ratings AS sr
    INNER JOIN bridge_drivers ON sr.driver_id = bridge_drivers.driver_id
    GROUP BY sr.driver_id
),

-- Per bridge driver: era shift = pre-era mean − post-era mean
-- Positive shift means pre-era looks slower (different car-era baseline)
bridge_shifts AS (
    SELECT
        driver_id,
        pre_era_mean_s - post_era_mean_s AS era_shift_s
    FROM bridge_era_means
    WHERE
        pre_era_mean_s IS NOT NULL
        AND post_era_mean_s IS NOT NULL
),

-- Diagnostic only (F45): mean shift across all bridge drivers. Measured and
-- published, never applied.
era_offset AS (
    SELECT
        AVG(era_shift_s) AS era_shift_global_s,
        STDDEV(era_shift_s) AS era_shift_stddev_s,
        COUNT(*) AS n_bridge_drivers,
        STDDEV(era_shift_s)
        / NULLIF(SQRT(COUNT(*)), 0) AS era_shift_se_s,
        COUNT(*) < 3 AS low_anchor_sample_flag
    FROM bridge_shifts
),

-- No era offset (F45): the rating is teammate-relative, so a car-era shift
-- cancels inside each pair. era_adjusted_rating is the season rating as is,
-- and its SE is the season rating's own (no offset uncertainty to add).
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

        sr.shrunk_residual_s AS era_adjusted_rating,

        COALESCE(sr.shrunk_residual_se_s, 0) AS era_adjusted_rating_se_s,

        bd.driver_id IS NOT NULL AS bridge_driver_anchor_flag

    FROM season_ratings AS sr
    CROSS JOIN era_offset AS eo
    LEFT JOIN bridge_drivers AS bd ON sr.driver_id = bd.driver_id
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
    era_adjusted_rating
    - 1.96 * era_adjusted_rating_se_s AS era_adjusted_rating_ci_low_s,
    era_adjusted_rating
    + 1.96 * era_adjusted_rating_se_s AS era_adjusted_rating_ci_high_s,

    rating_confidence,
    bridge_driver_anchor_flag,

    -- Diagnostic columns: the measured bridge-driver shift. NOT applied to
    -- era_adjusted_rating (F45).
    era_shift_global_s,
    era_shift_se_s,
    n_bridge_drivers,
    low_anchor_sample_flag

FROM with_era_adjustment
ORDER BY season DESC, era_adjusted_rating ASC
