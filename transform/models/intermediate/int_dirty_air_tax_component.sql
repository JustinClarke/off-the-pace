-- Dirty air tax model: Dirty air tax component.
--
-- Attributes per-second slowdown cost to dirty air following.
-- Uses lagged dirty-air share for identification:
-- same driver, same race, air state from previous lap ensures the causal arrow
-- runs prior-lap-position → current-lap-cost, not the reverse.
--
-- Output grain: lap_id (one row per lap, grain matches stg_laps).
--
-- Identity expansion:
--   pace_delta_s = fuel + compound + rubber + ambient + constructor
--               + dirty_air_tax + driver_skill + unexplained
--
-- Two parts:
-- Part 1: Calibration panel -- the population θ_air is fitted on
--   (partial_residual ~ dirty_air_lag1). Since W40 the fit itself runs
--   outside dbt and θ_air is a declared var; see the W40 block below.
--   partial_residual = lap_time_s - field_pace_smoothed_s - fuel_component_s
--                      - compound_component_s   (WI-01: tyre cost too, see
--                      panel_base; the base is fuel- AND compound-neutral)
--   This avoids the circular reference: int_dirty_air_tax_component cannot ref
--   int_lap_residual_decomposed because that model refs this one.
--   The calibration panel carries BOTH arms (treated and untreated laps).
--   See 08q below: filtering it to the treated arm left the regressor constant
--   and the slope unidentified, so θ_air was never actually fitted.
-- Part 2: Apply per lap
--   dirty_air_tax_s = CLAMP(θ_air × dirty_air_share_lag1, 0, 5.0)
--
-- 08q (2026-09-21): θ_air is now an ESTIMATE, not a default.
--   Until this item, `calibration_panel` filtered to `dirty_air_share_lag1 > 0`.
--   dirty_air_share_lap is one bit per lap (S2-only, int_lap_air_state:144-152),
--   so filtering to its treated arm left the regressor constant at 1.0 →
--   VAR_POP = 0 → NULLIF → NULL → the COALESCE fell through to the literal 0.5
--   on every build. dirty_air_tax_s was therefore exactly 0.5 s on every dirty-
--   air lap and 0.0 otherwise: a lap counter with a unit attached, which the
--   app's dirty-air-cost leaderboard presented as measured seconds.
--   Removing the filter restores both arms and identifies the slope. Measured
--   on the v12 substrate over the full 123,993-row panel (23.0% treated):
--     θ_air = +0.1310 s/lap  [95% CI +0.1144, +0.1476], SE 0.0085
--   The shipped 0.5 was 3.8x too high and sits outside that CI.
--   Global pooled θ is used rather than per-season (06b/08q ruling): per-season
--   θ ranges +0.418 (2018) to -0.011 (2024) and is indistinguishable from zero
--   on 2021 and 2024, but a seven-way seasonal conditional is not carried into
--   the ML label without its own gate ladder. See work/08-foundations-repair.md
--   section 08q for the identification argument and the open ruling on what the
--   app should show for seasons where θ is not distinguishable from zero.
--
-- WI-01 (2026-09-27, F5 + F23a + F23b + F48-θ): three fixes land together
-- because they all touch this same calibration/application split.
--   F23a -- the calibration panel is no longer defended by
--     COALESCE(fp.field_pace_smoothed_s, f.lap_time_s): that fallback made
--     partial_residual_s = -fuel_component_s (never NULL) for a lap the field
--     curve has no row for, so the existing
--     `WHERE partial_residual_s IS NOT NULL` filter never actually excluded a
--     fabricated-base lap from the fit. panel_base now INNER JOINs field_pace
--     directly, so a lap with no measured base gets no row at all here --
--     same NULL-propagation discipline as F1, not a fabricated tax value.
--   F23b -- the correction_weight/rainfall filter used to gate `panel` itself,
--     so a downweighted or wet lap got NO row in the OUTPUT table, which
--     int_lap_residual_decomposed's COALESCE(da.dirty_air_tax_s, 0.0) then
--     read as "0 s of dirty air" even when that lap genuinely followed one.
--     That filter now governs `calibration_panel` (estimation) only;
--     `panel_base` (application, and this model's grain) carries every
--     base-measured lap regardless of its own weight/weather.
--   F5 -- calibration_panel additionally requires
--     race_year <= var('theta_air_fit_season_max'): theta is fit on a
--     declared, frozen season window instead of "every ingested season," so
--     ingesting a new season cannot silently move theta and relabel history
--     that already shipped.
--   F48-θ -- this is the FIRST rebuild of theta after F1 (honest base),
--     F23a/F23b (honest calibration panel) and F48's coding fix
--     (WI-15a: S2 dirty-air share is monotone in the gap, no longer
--     miscoding sub-1s DRS-open follows as clean) all landed together, per
--     the WI-01 doc's instruction to re-estimate exactly once on top of all
--     three rather than once per fix.
--   Verification pass (2026-09-27): the partial residual now also subtracts
--     the lap's own compound_component_s. With a compound-neutral base (F38)
--     a fuel-only partial residual kept every lap's tyre cost in y, which
--     biased the pooled slope to 0.169; subtracting it gave pooled 0.5033,
--     WI-01's interim label value (superseded by W40, below).
--
-- W40 (2026-09-27, ruled by the user; the second half of the same label
-- bump, WI-01 + WI-12): θ_air is the DECLARED var('theta_air_label_value'),
-- 0.331 s/lap, applied as-is. It is no longer fitted in this model.
--   The value is 06b's pre-registered F2 estimator (partial residual on the
--   lagged bit | stint FE + six tyre-age bins, race-clustered), fitted by
--   WI-12 on exactly this model's calibration_panel (2018-2025):
--   0.3313 [0.293, 0.370], n = 138,679 (singleton stints drop out).
--   It replaces the pooled OLS slope this model used to compute here
--   (COVAR_POP / VAR_POP, 0.5033) because every estimator that removes
--   between-stint variation lands at 0.30-0.43 and pooled sits outside F2's
--   interval: slower cars follow more often (the constructor term alone is
--   worth 0.14 s between the arms), and later-in-stint laps are both more
--   often following and slower than the tyre model accounts for (the age
--   bins take stint-FE 0.433 to 0.331). The label only sees θ through
--   within-stint differences, so a between-stint confound has no place in it.
--   A two-way FE fit is not one SQL aggregate, so it runs outside dbt
--   (_roadmap/_fixes/_evidence/wi-12-2026-09-27/d2_fit_wi12.py, section W)
--   and is frozen as the var. Moving it is a reviewed label bump: rebuild,
--   re-run d1/d2 on the new panel, edit the var, re-take
--   label_stability_baseline. calibration_panel below still defines the
--   population the value was fitted on and still sets calibration_sample_n
--   (tax_calibration_confidence), and theta_air_fit_season_max still bounds it.

{{ config(materialized='table', tags=['causal_decomposition', 'dirty_air']) }}

WITH fuel AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        weight_penalty_s AS fuel_component_s
    FROM {{ ref('int_lap_fuel_state') }}
),

field_pace AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        field_pace_smoothed_s
    FROM {{ ref('int_field_pace_curve') }}
),

-- The lap's own tyre cost, the same term int_lap_residual_decomposed
-- subtracts as compound_component_s. Needed in the partial residual below
-- because the base is compound-neutral (WI-01/F38): see panel_base.
compound AS (
    SELECT
        lap_id,
        expected_compound_pace_s AS compound_component_s
    FROM {{ ref('int_compound_cliff_predicted') }}
),

geom AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        is_valid_lap
    FROM {{ ref('int_stint_geometry') }}
),

air_state AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        dirty_air_share_lap,
        air_state_dominant
    FROM {{ ref('int_lap_air_state') }}
),

-- Lag dirty_air_share over the FULL chronological sequence (SC/VSC/pit laps
-- included, via geom + air_state which both now carry every lap). Without
-- this, the first valid lap after an SC period would lag back to the last
-- *valid* pre-SC lap and wrongly inherit a high traffic penalty; with the
-- full sequence, it correctly lags to the SC lap itself (share = 0, per the
-- int_lap_air_state SC-bunching fix).
full_sequence_lag AS (
    SELECT
        g.lap_id,
        LAG(COALESCE(a.dirty_air_share_lap, 0.0), 1, 0.0) OVER (
            PARTITION BY g.stint_id
            ORDER BY g.lap_in_stint
        ) AS dirty_air_share_lag1
    FROM geom AS g
    LEFT JOIN air_state AS a ON g.lap_id = a.lap_id
),

corrections AS (
    -- Clean-lap filter: use correction_weight instead of int_lap_anomaly_flags
    -- to
    -- avoid the cycle: int_dirty_air_tax_component → int_lap_anomaly_flags →
    -- int_lap_residual_decomposed → int_dirty_air_tax_component.
    SELECT
        lap_id,
        correction_weight
    FROM {{ ref('int_event_corrections') }}
),

evolution AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        rainfall_flag
    FROM {{ ref('int_track_evolution') }}
),

panel_base AS (
    -- Full spine: every lap with fuel/geom data AND a measured field-pace
    -- base. A lap the field curve has no row for (F1) gets no row here
    -- either -- the same NULL-propagation discipline as the rest of the
    -- label spine, not a fabricated tax (F23a). This is BOTH the application
    -- population (every row here gets a tax value in with_tax below) and the
    -- superset calibration_panel narrows for estimation only (F23b).
    SELECT
        f.lap_id,
        g.stint_id,
        f.race_year,
        f.race_id,
        f.driver_id,
        f.lap_number,
        g.lap_in_stint,
        -- Partial residual: pace delta minus fuel AND the lap's own tyre cost
        -- (avoids circular ref to int_lap_residual_decomposed).
        -- WI-01 (2026-09-27): the base is now compound-neutral (F38), so it no
        -- longer absorbs the field's tyre cost. Subtracting fuel only left
        -- each lap's whole tyre cost in the partial residual, and that cost is
        -- not orthogonal to the dirty-air lag: treated laps carry about 0.33 s
        -- LESS modelled tyre cost than untreated ones (1.08 vs 1.41 s, WI-12),
        -- so the pooled slope came out at 0.169 instead of ~0.5. Tyre cost is
        -- now handled exactly the way fuel is.
        -- A lap with an unknown tyre cost (F39: unknown tyre age) gets a NULL
        -- partial residual and so stays out of the fit (calibration_panel's
        -- IS NOT NULL filter); it still gets a tax value in with_tax.
        -- Constructor pace is left in, and it is NOT orthogonal to the lag:
        -- slower cars follow more often. Measured 2026-09-27 on this panel:
        -- pooled 0.503, pooled with the constructor term also subtracted
        -- 0.363, stint FE 0.433, stint FE + tyre-age bins (F2) 0.331. That
        -- confound is why θ_air is the declared F2 value, not the pooled
        -- slope of this residual (W40, header): stint FE absorbs the car.
        -- No defensive COALESCE on fp.field_pace_smoothed_s (F23a): the INNER
        -- JOIN to field_pace below already means every row reaching this
        -- SELECT has a measured base, so this is a plain subtraction, not a
        -- fallback that could silently revive the fabrication.
        (f.lap_time_s - fp.field_pace_smoothed_s)
        - f.fuel_component_s
        - cc.compound_component_s
            AS partial_residual_s,
        a.dirty_air_share_lap,
        a.air_state_dominant,
        fsl.dirty_air_share_lag1,
        c.correction_weight,
        e.rainfall_flag
    FROM fuel AS f
    INNER JOIN geom AS g ON f.lap_id = g.lap_id
    INNER JOIN full_sequence_lag AS fsl ON f.lap_id = fsl.lap_id
    INNER JOIN field_pace AS fp                -- F1/F23a: no base, no row
        ON
            f.race_year = fp.race_year
            AND f.race_id = fp.race_id
            AND f.lap_number = fp.lap_number
    LEFT JOIN compound AS cc ON f.lap_id = cc.lap_id
    LEFT JOIN air_state AS a ON f.lap_id = a.lap_id
    LEFT JOIN corrections AS c ON f.lap_id = c.lap_id
    LEFT JOIN evolution AS e
        ON
            f.race_year = e.race_year
            AND f.race_id = e.race_id
            AND f.lap_number = e.lap_number
    WHERE
        f.lap_time_s IS NOT NULL
        -- F1/F23a: int_field_pace_curve can carry a ROW for a (race, lap_number)
        -- with too few eligible cars to produce a value (eligible_lap_count as
        -- low as 1-2 around a red flag/restart) -- field_pace_trimmed_mean_s AND
        -- the smoothed rolling average both NULL despite the row existing. The
        -- INNER JOIN above only guarantees a row, not a measured value, so this
        -- guards the value itself (measured 2026-09-27: 19 laps, all lap 21-22
        -- of 2022_7 around a red-flag restart).
        AND fp.field_pace_smoothed_s IS NOT NULL
),

calibration_panel AS (
    -- BOTH ARMS. Do not re-add a `dirty_air_share_lag1 > 0` filter here: the
    -- regressor is binary, so restricting it to the treated arm makes it a
    -- constant and the slope below is no longer identified (08q).
    --
    -- The three filters below govern ESTIMATION only (F23b): a lap excluded
    -- here from the theta fit still gets a tax value in with_tax, which reads
    -- from panel_base, not from this CTE.
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_in_stint,
        partial_residual_s,
        dirty_air_share_lag1
    FROM panel_base
    WHERE
        partial_residual_s IS NOT NULL
        AND COALESCE(correction_weight, 1.0) = 1.0
        AND COALESCE(rainfall_flag, FALSE) = FALSE
        -- F5: frozen fit window (dbt_project.yml var), not "every ingested
        -- season" -- see that var's comment for why.
        AND race_year <= {{ var('theta_air_fit_season_max') }}
),

-- Global θ_air: the declared label value (W40, header), one number for every
-- lap and season. Identified by the one-lap lag: the air state that prices
-- this lap is the previous lap's, so the causal arrow runs prior-position ->
-- current-cost. It is 06b's F2 estimate (stint FE + tyre-age bins) on this
-- model's calibration_panel, fitted outside dbt because a two-way FE fit is
-- not one SQL aggregate. Until W40 this CTE fitted the pooled OLS slope
-- COVAR_POP(y, x) / VAR_POP(x) here (0.5033 on this panel; 0.1310 on the v12
-- substrate), with a COALESCE to 0.1310 for a degenerate panel. A declared
-- value has no degenerate case, so the fallback is gone with the fit.
-- calibration_panel still sets calibration_sample_n (the population the
-- declared value was fitted on).
theta_air_label AS (
    SELECT
        CAST({{ var('theta_air_label_value') }} AS DOUBLE) AS theta_air,
        COUNT(*) AS calibration_sample_n
    FROM calibration_panel
),

with_tax AS (
    SELECT
        wl.lap_id,
        wl.stint_id,
        wl.race_year,
        wl.race_id,
        wl.driver_id,
        wl.lap_number,
        wl.lap_in_stint,
        wl.dirty_air_share_lag1,
        wl.air_state_dominant,
        ta.theta_air,
        ta.calibration_sample_n,
        -- Dirty air tax: θ_air × lagged share, bounded [0, 5.0]
        CASE
            WHEN
                ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) < 0
                THEN 0.0
            WHEN
                ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) > 5.0
                THEN 5.0
            ELSE ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0)
        END AS dirty_air_tax_s,
        ABS(ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) * 0.15)
            AS dirty_air_tax_se_s,
        -- Continuous shrinkage-towards-prior: n / (n + k) where k = 500 (prior
        -- equivalent sample).
        -- Approaches 1.0 asymptotically; stays honest near zero at small n.
        CAST(ta.calibration_sample_n AS DOUBLE)
        / (CAST(ta.calibration_sample_n AS DOUBLE) + 500.0)
            AS tax_calibration_confidence,
        SUM(
            CASE
                WHEN
                    ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) < 0
                    THEN 0.0
                WHEN
                    ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0) > 5.0
                    THEN 5.0
                ELSE ta.theta_air * COALESCE(wl.dirty_air_share_lag1, 0.0)
            END
        ) OVER (
            PARTITION BY wl.race_year, wl.race_id, wl.driver_id
            ORDER BY
                wl.lap_number
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_dirty_air_tax_race_s
    FROM panel_base AS wl
    CROSS JOIN theta_air_label AS ta
)

SELECT
    lap_id,
    dirty_air_share_lag1 AS dirty_air_intensity_lag1,
    dirty_air_tax_s,
    dirty_air_tax_se_s,
    tax_calibration_confidence,
    cumulative_dirty_air_tax_race_s,
    COALESCE(dirty_air_tax_s = MAX(dirty_air_tax_s) OVER (
        PARTITION BY race_year, race_id, driver_id
    ), FALSE) AS dirtiest_air_lap_in_race_flag
FROM with_tax
ORDER BY race_year, race_id, driver_id, lap_number
