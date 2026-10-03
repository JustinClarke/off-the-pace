-- Driver-isolation tyre-age curve (WI-16b, 2026-09-30): the age adjustment
-- of tier 3's relative pace. A thin reader over
-- data/fits/isolation_age_curve.parquet, written by
-- tasks/coefficients/fit_isolation_age_curve.py (`make car-fe-isolation-fit`),
-- which fits
--     lap_time_s ~ spline_G(age_in_stint)
--                  | (race, driver, compound) + (race, lap)
-- per group G = era|compound on the clean-air, non-recovery Ω laps,
-- cross-fitted by race (5 folds): a race's curve uses the other folds only.
--
-- Why it replaced the seed's ΔC: the pre-registered tier-3 check is that the
-- age adjustment reduces the within-pair lap-to-lap variance. The seed's
-- hockey stick (per season x track x compound onset and ramp) raised it by
-- 3.4%. This curve is smooth, rising in every group, and adds far less; it
-- still does not reduce it (WI doc, "As built: eras and the age curve").
--
-- Output grain: one row per (race_year, race_id, compound, age_in_stint) in
-- Ω. Sign: age_effect_s in seconds, POSITIVE = SLOWER than the group's
-- reference age. Only differences inside one (race, compound) are meaningful,
-- which is how fct_driver_isolation_pair_lap uses it (both cars share race
-- and compound).
--
-- Leakage: part of the driver-isolation subtree. No ML-contract mart may depend
-- on it (T48).

{{ config(materialized='table', tags=['driver_isolation']) }}

SELECT
    CONCAT(
        CAST(race_id AS VARCHAR), '_',
        CAST(compound AS VARCHAR), '_',
        CAST(age_in_stint AS VARCHAR)
    ) AS isolation_age_curve_id,
    CAST(race_year AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(compound AS VARCHAR) AS compound,
    CAST(age_in_stint AS INTEGER) AS age_in_stint,
    CAST(age_effect_s AS DOUBLE) AS age_effect_s,
    CAST(fit_group AS VARCHAR) AS fit_group,
    CAST(fold AS INTEGER) AS fold,
    CAST(n_fit_laps_group AS INTEGER) AS n_fit_laps_group,
    CAST(boundary_lo_age AS DOUBLE) AS boundary_lo_age,
    CAST(boundary_hi_age AS DOUBLE) AS boundary_hi_age,
    fit_method,
    fit_timestamp
FROM {{ source('fits', 'isolation_age_curve') }}
