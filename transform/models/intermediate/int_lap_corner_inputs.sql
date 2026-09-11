-- Corner-level driver inputs, aggregated to lap grain.
-- Grain: lap_id -- one row per race lap that has at least one measured corner.
-- Work item 02c (Tier 2 of _improvements/work/02-feature-expansion.md).
--
-- WHAT THIS IS FOR. The degradation target's variance is 99.06% within stint
-- (`between_stint_share` = 0.0094, ml_research_program.md §1c). A feature that is
-- constant inside a stint can only ever address the other 0.94%. This is the only
-- candidate channel in item 02 that varies lap to lap, so it is the only one that
-- can reach the degradation trio at all.
--
-- MECHANISM, stated so the ablation has something to falsify. Braking, rotation and
-- throttle application are the direct physical inputs of energy into a tyre. The
-- incumbent `thermal` group (push_residual, cumulative_push_load_*) INFERS push load
-- from lap-time residuals. This measures the inputs instead of inferring them.
--
-- WHY mean / sd / max. Per the leaf doc: mean is the lap's overall input level, max
-- is the single hardest corner, and sd is the one with a tyre-management story --
-- a driver who is even across the lap loads the tyre differently from one who is
-- spiking in two corners and coasting the rest, at the same mean.
--
-- Each phase is aggregated over the corners where THAT phase is measurable, not over
-- the intersection of all three. The three phases have genuinely different corner-grain
-- availability, re-measured on the shipped table 2026-09-11 over all 2,206,939 corner
-- rows: braking 69.94%, mid-corner 81.12%, exit 47.00%. 18.88% of corner rows are
-- unmapped outright (field_corner_sample_n < 5 under the trailing window, so every
-- residual is NULL); among the mapped ones the three run 86.21% / 100% / 57.94%.
-- Mid-corner is the ceiling because every corner has an apex; braking_point_m is NULL
-- where a corner is taken flat and throttle_point_m is NULL where the driver never
-- reaches full throttle before the next apex, and both are real answers about a fast
-- corner rather than missing data. Intersecting them would have thrown away most of the
-- channel for nothing: corner_residual_total_s, which is exactly that intersection, is
-- non-null on only 38.59% of corner rows.
--
-- (An earlier draft of this header quoted mid-corner 97.6% and exit 60.9%. Those do not
-- reproduce against this table and are corrected above; the braking and intersection
-- figures do reproduce. Lap-grain coverage is unaffected and much higher than any of
-- these, because one measurable corner is enough to give the lap a non-null mean.)
--
-- POINT-IN-TIME. Every input column is a residual against a backward-only trailing-5
-- field median (02g). The values are contemporaneous with lap t; the degradation
-- target spans t+1..t+5. The GROUP BY is keyed on lap_id, which pins one lap, so this
-- model adds no aggregation scope of its own -- the whole point-in-time argument rests
-- on int_corner_skill_residuals upstream, where 02a found the original defect and 02g
-- repaired it.
--
-- COVERAGE IS A DECLARED COLUMN, NOT A SILENT NaN. Measured against the mart's
-- training-eligible rows, the braking mean is NULL on 4.15% of them, and those rows
-- are NOT a random subset: their mean 5-lap label is +1.393 s against -2.330 s for
-- the covered rows, with sd 10.196 against 5.938. The missingness carries label
-- signal. It is not forward leakage -- a lap is uncovered because its own telemetry is
-- absent, or because the trailing baseline over laps t-5..t-1 held fewer than five
-- valid observations, and both are settled strictly before t+1 -- but a model handed
-- these columns as bare NaNs would be free to split on "corner inputs missing" and
-- score a win that has nothing to do with driver inputs. So the coverage is emitted
-- as its own column and admitted to the contract beside the residuals, which is what
-- makes it separately ablatable. See the leaf doc's arm C.
{{ config(materialized='table', tags=['intermediate', 'feature_engineering']) }}

WITH corner_rows AS (
    SELECT
        lap_id,
        braking_loss_s,
        mid_corner_residual_s,
        exit_residual_s,
        corner_unmapped_flag
    FROM {{ ref('int_corner_skill_residuals') }}
)

SELECT
    lap_id,

    -- Coverage. corners_total_n is every corner the telemetry placed on this lap;
    -- corners_mapped_n is the subset that cleared the field_corner_sample_n >= 5
    -- gate and so carries a residual at all. The ratio is what enters the contract:
    -- the raw count conflates coverage with circuit corner count (Monaco 19 vs
    -- Monza 11), and circuit identity is already in the feature set three times over.
    COUNT(*) AS corners_total_n,
    COUNT(*) FILTER (WHERE NOT corner_unmapped_flag) AS corners_mapped_n,
    COUNT(*) FILTER (WHERE NOT corner_unmapped_flag)
    / NULLIF(CAST(COUNT(*) AS DOUBLE), 0) AS corner_input_coverage,

    -- Per-phase measured counts. Not contract features -- these are the companion
    -- columns the trailing_median macro's own docstring asks for, so a reader can
    -- see how thin any one lap's aggregate is instead of guessing.
    COUNT(braking_loss_s) AS corner_braking_n,
    COUNT(mid_corner_residual_s) AS corner_mid_n,
    COUNT(exit_residual_s) AS corner_exit_n,

    -- Braking phase: where the driver puts energy in on entry.
    AVG(braking_loss_s) AS corner_braking_loss_mean_s,
    STDDEV_SAMP(braking_loss_s) AS corner_braking_loss_sd_s,
    MAX(braking_loss_s) AS corner_braking_loss_max_s,

    -- Mid-corner phase: rotation, the highest-coverage of the three.
    AVG(mid_corner_residual_s) AS corner_mid_residual_mean_s,
    STDDEV_SAMP(mid_corner_residual_s) AS corner_mid_residual_sd_s,
    MAX(mid_corner_residual_s) AS corner_mid_residual_max_s,

    -- Exit phase: throttle application, where traction energy goes in.
    AVG(exit_residual_s) AS corner_exit_residual_mean_s,
    STDDEV_SAMP(exit_residual_s) AS corner_exit_residual_sd_s,
    MAX(exit_residual_s) AS corner_exit_residual_max_s

FROM corner_rows
-- Keyed on lap_id: the group is confined to one lap, so it has no forward reach to
-- have. This is the shape ml/src/features.py::_pins_one_lap accepts without an
-- exemption, and it is deliberate -- 02a's ruling was caused by a GROUP BY whose key
-- was a five-lap bucket rather than a lap.
GROUP BY lap_id
