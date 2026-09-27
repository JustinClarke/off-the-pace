-- T28 (F38, WI-01). The field base is neutral to tyre cost: the residual
-- does not move with how worn the field's tyres are.
--
-- Test: for each (race, lap) with at least 5 measured laps, take the mean
-- driver_skill_residual_s and the field's mean tyre cost
-- (compound_component_s). Demean both within the race and fit the slope of
-- mean residual on field tyre cost. With a compound-neutral base that slope
-- is ~0. With F38's defect (a base that still contains the field's tyre cost,
-- which the residual then subtracts again lap by lap) it is ~-1: every second
-- of field tyre wear shows up as a second of fake driver pace.
--
-- Measured 2026-09-27: pooled slope +0.027 over 8,956 (race, lap) cells;
-- per season -0.10 (2023) to +0.12 (2024). The same statistic on a
-- fuel-only base rebuilt from the same eligible population (the F38 defect,
-- simulated in the WI-01 verification pass) is -0.958. The 0.30 bound sits
-- well clear of both.
--
-- This replaces an earlier T28 that re-implemented int_field_pace_curve's
-- SQL line for line and compared the two: that could only detect an edit to
-- the model, never a wrong model, and it failed the moment the model's
-- eligibility changed (WI-01's unknown-tyre filter) while the base stayed
-- neutral.
--
-- Fails with one row per offending scope ('pooled' or a season), and also if
-- the check has fewer than 1,000 cells to work with (vacuity guard).
{{ config(severity='error') }}

WITH per_lap AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        AVG(driver_skill_residual_s) AS mean_residual_s,
        AVG(compound_component_s) AS field_tyre_cost_s
    FROM {{ ref('int_lap_residual_decomposed') }}
    WHERE driver_skill_residual_s IS NOT NULL
    GROUP BY race_year, race_id, lap_number
    HAVING COUNT(*) >= 5
),

demeaned AS (
    SELECT
        race_year,
        mean_residual_s
        - AVG(mean_residual_s) OVER (PARTITION BY race_year, race_id) AS y,
        field_tyre_cost_s
        - AVG(field_tyre_cost_s) OVER (PARTITION BY race_year, race_id) AS x
    FROM per_lap
),

slopes AS (
    SELECT
        'pooled' AS scope,
        SUM(x * y) / NULLIF(SUM(x * x), 0) AS within_race_slope,
        COUNT(*) AS n_cells
    FROM demeaned
    UNION ALL
    SELECT
        CAST(race_year AS VARCHAR) AS scope,
        SUM(x * y) / NULLIF(SUM(x * x), 0) AS within_race_slope,
        COUNT(*) AS n_cells
    FROM demeaned
    GROUP BY race_year
)

SELECT scope, within_race_slope, n_cells
FROM slopes
WHERE within_race_slope IS NULL
   OR ABS(within_race_slope) > 0.30
   OR (scope = 'pooled' AND n_cells < 1000)
