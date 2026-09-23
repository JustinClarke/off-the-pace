-- Corner drift from the driver's own early-stint baseline, aggregated to lap grain.
-- Grain: lap_id -- one row per race lap that has at least one measured corner.
-- Item 02h (Tier 2 follow-on) in _improvements/work/02-feature-expansion.md.
--
-- Same three phases and the same mean/sd/max shape int_lap_corner_inputs (02c)
-- uses, applied to int_corner_drift_from_early_stint's DRIFT columns instead of
-- 02c's PACE residuals. See that model's header for the mechanism: a pace
-- residual does not have to persist lap-to-lap and measurably does not
-- (lag-1 autocorrelation 0.032-0.176); a drift against the driver's own
-- early-stint baseline persists by construction, because it accumulates with
-- tyre wear across the remainder of the stint.
--
-- COVERAGE HERE IS TWO THINGS AT ONCE, and that is deliberate, not sloppy. A lap
-- can be missing a drift value because its OWN corner telemetry / field baseline
-- is unmapped -- the same reason 02c's corner_input_coverage exists -- OR because
-- the lap sits inside the baseline-defining window (valid_lap_in_stint <= 6) or
-- its stint never reached 7 valid laps. The second reason is new and entirely
-- mechanical: it is a function of lap_in_stint / age_in_stint, both already in
-- the 32-column contract, so a model handed corner_drift_coverage as a bare
-- number is free to relearn "how far into the stint am I" through it rather than
-- through the drift values themselves. That is exactly the shape 02c's confound
-- arm (arm C) existed to isolate, and this item's own arm C repeats the test
-- against the new confound.
{{ config(materialized='table', tags=['intermediate', 'feature_engineering']) }}

WITH corner_rows AS (
    SELECT
        lap_id,
        braking_drift_s,
        mid_drift_s,
        exit_drift_s
    FROM {{ ref('int_corner_drift_from_early_stint') }}
)

SELECT
    lap_id,

    -- Coverage. corners_total_n is every corner the lineage placed on this lap
    -- (whether or not a drift value could be formed for it);
    -- corners_drift_mapped_n is the subset with at least one non-NULL phase
    -- drift. The ratio is what enters the contract, for the same reason 02c's
    -- corner_input_coverage uses a ratio rather than a raw count: the raw count
    -- conflates coverage with circuit corner count, and circuit identity is
    -- already in the feature set three times over.
    COUNT(*) AS corners_total_n,
    COUNT(*) FILTER (
        WHERE
            braking_drift_s IS NOT NULL
            OR mid_drift_s IS NOT NULL
            OR exit_drift_s IS NOT NULL
    ) AS corners_drift_mapped_n,
    COUNT(*) FILTER (
        WHERE
            braking_drift_s IS NOT NULL
            OR mid_drift_s IS NOT NULL
            OR exit_drift_s IS NOT NULL
    ) / NULLIF(CAST(COUNT(*) AS DOUBLE), 0) AS corner_drift_coverage,

    -- Per-phase measured counts, mirroring int_lap_corner_inputs' companion
    -- columns -- not contract features, diagnostics only.
    COUNT(braking_drift_s) AS corner_braking_drift_n,
    COUNT(mid_drift_s) AS corner_mid_drift_n,
    COUNT(exit_drift_s) AS corner_exit_drift_n,

    -- Braking phase drift.
    AVG(braking_drift_s) AS corner_braking_drift_mean_s,
    STDDEV_SAMP(braking_drift_s) AS corner_braking_drift_sd_s,
    MAX(braking_drift_s) AS corner_braking_drift_max_s,

    -- Mid-corner phase drift.
    AVG(mid_drift_s) AS corner_mid_drift_mean_s,
    STDDEV_SAMP(mid_drift_s) AS corner_mid_drift_sd_s,
    MAX(mid_drift_s) AS corner_mid_drift_max_s,

    -- Exit phase drift.
    AVG(exit_drift_s) AS corner_exit_drift_mean_s,
    STDDEV_SAMP(exit_drift_s) AS corner_exit_drift_sd_s,
    MAX(exit_drift_s) AS corner_exit_drift_max_s

FROM corner_rows
-- Keyed on lap_id: the group is confined to one lap, so it has no forward reach
-- to have -- the shape ml/src/features.py::_pins_one_lap accepts without an
-- exemption.
GROUP BY lap_id
