-- Corner-level DRIFT from the driver's own early-stint baseline.
-- Grain: (lap_id, corner_name) -- same physical grain as int_corner_skill_residuals,
-- which this model residualizes a SECOND time.
-- PK: corner_id = lap_id || '_C_' || corner_name (same convention).
--
-- Item 02h (_improvements/work/02-feature-expansion.md), built directly from the
-- audit that closed 02c: the nine corner residual aggregates do not persist
-- lap-to-lap (measured lag-1 within-stint autocorrelation 0.032-0.176) while the
-- columns that survive ablation all sit at .27-.42 (proximity .421, thermal's
-- push_residual .343, dirty_air .266). (field trailing-5 median - own), which is
-- what int_corner_skill_residuals measures, is a RELATIVE-PACE construct -- a
-- driver/car trait the feature contract already holds three ways -- and pace does
-- not have to persist within a stint the way a STATE does.
--
-- CONSTRUCT. For each (stint_id, corner_name), take the mean of
-- int_corner_skill_residuals' three phase residuals over the stint's own first 6
-- VALID laps (valid_lap_in_stint 1-6) as a BASELINE -- the driver's own reference
-- level for that corner, early in the stint, before much tyre wear has
-- accumulated. Every later lap's residual, minus that baseline, is DRIFT. A
-- driver 0.05s worse than the field on entry at lap 3 and still 0.05s worse at
-- lap 30 has zero drift: that is pace, and pace is already in the contract three
-- times over. A driver 0.05s worse at lap 3 and 0.35s worse at lap 30 has +0.30s
-- of drift -- the thing tyre degradation should show up as, and the thing a pace
-- residual cannot distinguish from a driver who is simply slow-but-stable in that
-- corner all race.
--
-- LEAKAGE. The baseline window (valid_lap_in_stint 1-6) is FIXED per stint -- it
-- is not a trailing window relative to the query lap the way int_corner_skill_
-- residuals' field median is. Every lap this baseline is broadcast to that
-- carries a non-NULL drift value has valid_lap_in_stint >= 7, strictly after the
-- baseline window, so the baseline never draws on a lap at or after the one it is
-- subtracted from. Laps 1-6 THEMSELVES -- the baseline-defining window -- get
-- drift = NULL: they define the reference rather than measuring a departure from
-- it, so they carry no information for the model to leak. Declared in
-- schema.yml's aggregation_scope_exemptions and verified before the ablation ran
-- (zero rows with valid_lap_in_stint <= 6 carry a non-NULL drift value; see the
-- leaf doc).
--
-- NULL IF THE STINT HAS FEWER THAN 7 VALID LAPS. A stint that never reaches
-- valid_lap_in_stint = 7 has no lap to report a drift value FOR, so the whole
-- stint's drift columns are NULL rather than partially populated from an
-- under-powered baseline. Within a long-enough stint, a baseline is only
-- reported for a (stint, corner, phase) with >= 3 non-NULL observations inside
-- the 6-lap window -- int_corner_skill_residuals' own field-median gate already
-- NULLs a corner's residual when the trailing field sample is thin, so 6
-- opportunities can yield fewer than 6 usable baseline observations even before
-- this gate.
{{ config(materialized='table', tags=['intermediate', 'feature_engineering']) }}

WITH corner_residuals AS (
    SELECT
        cr.lap_id,
        cr.stint_id,
        cr.driver_id,
        cr.race_id,
        cr.race_year,
        cr.corner_name,
        cr.lap_number,
        cr.braking_loss_s,
        cr.mid_corner_residual_s,
        cr.exit_residual_s,
        sg.valid_lap_in_stint,
        sg.stint_length_valid
    FROM {{ ref('int_corner_skill_residuals') }} AS cr
    INNER JOIN {{ ref('int_stint_geometry') }} AS sg
        ON cr.lap_id = sg.lap_id
    -- int_corner_skill_residuals is already confined to is_valid_lap = TRUE
    -- laps (its own lap_keys CTE filters upstream), so valid_lap_in_stint is
    -- defined for every row here.
),

-- BASELINE. GROUP BY (stint_id, corner_name) does not pin a lap on its own --
-- declared in schema.yml, not hidden. Safe because the FILTER clause fixes the
-- window to valid_lap_in_stint <= 6 regardless of which lap ends up reading the
-- result; see the model header.
baseline AS (
    SELECT
        stint_id,
        corner_name,
        MAX(stint_length_valid) AS stint_length_valid,
        AVG(braking_loss_s) FILTER (
            WHERE valid_lap_in_stint <= 6
        ) AS baseline_braking_loss_s,
        AVG(mid_corner_residual_s) FILTER (
            WHERE valid_lap_in_stint <= 6
        ) AS baseline_mid_residual_s,
        AVG(exit_residual_s) FILTER (
            WHERE valid_lap_in_stint <= 6
        ) AS baseline_exit_residual_s,
        COUNT(braking_loss_s) FILTER (
            WHERE valid_lap_in_stint <= 6
        ) AS baseline_braking_n,
        COUNT(mid_corner_residual_s) FILTER (
            WHERE valid_lap_in_stint <= 6
        ) AS baseline_mid_n,
        COUNT(exit_residual_s) FILTER (
            WHERE valid_lap_in_stint <= 6
        ) AS baseline_exit_n
    FROM corner_residuals
    GROUP BY stint_id, corner_name
)

SELECT
    CONCAT(cr.lap_id, '_C_', cr.corner_name) AS corner_id,
    cr.lap_id,
    cr.stint_id,
    cr.driver_id,
    cr.race_id,
    cr.race_year,
    cr.corner_name,
    cr.lap_number,
    cr.valid_lap_in_stint,
    (b.stint_length_valid < 7 OR cr.valid_lap_in_stint <= 6) AS drift_in_baseline_window,
    CASE
        WHEN
            b.stint_length_valid < 7
            OR cr.valid_lap_in_stint <= 6
            OR b.baseline_braking_n < 3
            OR cr.braking_loss_s IS NULL
            THEN NULL
        ELSE cr.braking_loss_s - b.baseline_braking_loss_s
    END AS braking_drift_s,
    CASE
        WHEN
            b.stint_length_valid < 7
            OR cr.valid_lap_in_stint <= 6
            OR b.baseline_mid_n < 3
            OR cr.mid_corner_residual_s IS NULL
            THEN NULL
        ELSE cr.mid_corner_residual_s - b.baseline_mid_residual_s
    END AS mid_drift_s,
    CASE
        WHEN
            b.stint_length_valid < 7
            OR cr.valid_lap_in_stint <= 6
            OR b.baseline_exit_n < 3
            OR cr.exit_residual_s IS NULL
            THEN NULL
        ELSE cr.exit_residual_s - b.baseline_exit_residual_s
    END AS exit_drift_s
FROM corner_residuals AS cr
INNER JOIN baseline AS b
    ON cr.stint_id = b.stint_id AND cr.corner_name = b.corner_name
