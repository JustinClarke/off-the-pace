-- Driver isolation, step 0: the clean-lap panel Ω and the field-centred
-- isolated time. WI-16a
-- (_roadmap/_fixes/wi/WI-16-cumulative-driver-isolation.md). Grain: one row per
-- Ω lap, PK lap_id. It is the input of the car-term fit
-- (tasks/coefficients/fit_constructor_car_fe.py --panel isolation) and of every
-- downstream isolation model.
--
-- WHAT IT COMPUTES
--   x_s = lap_time_s - compound_component_s - dirty_air_tax_s
--   y_s = x_s - MEDIAN over the Ω laps on the same (race, lap) of x_s
--   tyre_offset_vs_field_s = compound_component_s - that lap's field median
-- Sign: y_s and tyre_offset_vs_field_s are in seconds, POSITIVE = SLOWER than
-- the field-typical car and driver on that lap (the residual chain's
-- convention). The published ratings downstream flip this: every *_gain_s
-- column is positive = faster.
--
-- WHY THE RATINGS DO NOT DEPEND ON FD1 (the base question). Write a lap as
--   t = B(r,l) + F(r,l) + R(r,l) + A(r,l) + C(d,l) + K(c,r) + D(d,l) + e(d,l)
-- (field base, fuel, rubber, ambient, compound + tyre age, constructor, dirty
-- air, driver). Every car on a lap carries the same fuel load
-- (int_lap_fuel_state prices fuel from the scheduled distance, one rate per
-- race) and the same B, R and A, so all four depend on (race, lap) alone. They
-- shift every x on the lap and the lap's median by the same amount, so they
-- cancel out of y exactly: y = (K + e) - MEDIAN(K + e). Nothing here reads
-- base_track_pace_s, fuel_component_s, rubber_component_s, ambient_component_s
-- or constructor_component_s. T41 (assert_isolation_base_invariance) re-derives
-- y_s from the residual chain and pins this; measured on 2026-09-26, none of
-- those four terms varies inside any of the 7,907 (race, lap) cells of Ω.
--
-- Ω, THE CLEAN-LAP PANEL. Both upstream models carry correction_weight, so
-- every predicate is table-qualified instead of calling clean_lap_filter()
-- bare. The first three lines are clean_lap_filter(); the rest go further on
-- purpose.
--   r.correction_weight = 1.0
--   a.anomaly_class IN ('normal', 'clean_cliff')  (drops event_driven, F51)
--   NOT COALESCE(a.is_rain_lap, FALSE)
--   NOT a.is_out_lap AND NOT a.is_in_lap
--   r.compound NOT IN ('INTERMEDIATE', 'WET')     (wet skill is out of scope)
--   r.compound_component_s IS NOT NULL AND r.laps_past_cliff IS NOT NULL
--                              (unknown tyre = no rating, F7/F39; never 0)
--   a measured lagged air state, from the tax component's own row or, on a
--   thin cell, priced here (FD6 / CO-04 and W10 / v17; below)
--   r.race_id NOT IN var('isolation_exclude_races')
--   the (race, lap) holds >= var('isolation_min_field_n') laps passing the rest
--
-- STINT PHASE. The tyre phase comes from the seed's cliff onset
-- (laps_past_cliff), which is exogenous to the residual, so a phase is never
-- selected on the outcome it stratifies:
--   early  laps_past_cliff = 0 AND valid_lap_in_stint <= 5
--   mid    laps_past_cliff = 0 AND valid_lap_in_stint >= 6
--   cliff  laps_past_cliff > 0
-- (Deviation from the WI doc, which writes early as valid_lap_in_stint BETWEEN
-- 2 AND 5. The 2 was there to skip the out-lap, which Ω already drops through
-- is_out_lap. When a stint's out-lap is not a valid lap, its first flying lap
-- has valid_lap_in_stint = 1; 4,085 Ω laps (3.1%) are like that and would have
-- had no phase at all.)
--
-- RECOVERY is an overlay: is_recovery marks the first
-- var('isolation_recovery_laps') valid laps of a non-dirty-air run that
-- directly follows a run of at least var('isolation_recovery_min_dirty_run')
-- consecutive dirty-air valid laps in the same stint, and stint_phase =
-- 'recovery' on those laps, tyre_phase otherwise. The rule is gap-based and
-- looks backward only. It runs over all valid laps, not Ω, so a dirty-air run
-- is measured whole. The run aggregate uses BOOL_AND (the F16 lesson), not
-- ANY_VALUE. Rejected alternatives:
-- int_tyre_surface_vs_bulk_decoupling.recovery_flag reads future laps (LEAD),
-- and push_residual is derived from lap time, so either would make "pace in
-- recovery" circular.
--
-- FD6 (CO-04, 2026-10-15): unmeasured air is unknown, not clean air.
--   x_s needs the lap's dirty-air tax, and int_lap_residual_decomposed fills
--   that tax with 0.0 wherever int_dirty_air_tax_component has no row (no
--   field base) and passes it through as NULL where the previous lap's air
--   state is unmeasured. Only a lap with a measured lagged air state
--   (dirty_air_intensity_lag1 NOT NULL) has a tax that was actually priced, so
--   Ω keeps only those. Measured on the CO-04 build (2026-10-15) this drops
--   5,989 of 129,527 candidate laps: 1,322 in 2018_1 Australia and 2018_2
--   Bahrain (no telemetry in bronze, no field base, every tax a 0.0 fill), 12
--   whose previous lap was unmeasured, and 4,655 elsewhere whose field-base
--   cell is thin (W44: no base, so int_dirty_air_tax_component writes no row,
--   T18). Those last laps' air IS measured, but their tax was never priced:
--   3,584 of them followed a car, so the 0.0 fill would under-charge them by
--   theta_air (0.331 s). Pricing the tax without a base would keep them, and
--   needs T18 / F23a revisited; that is an open point in the CO-04 report.
--
-- W10 / v17 (owner ruling 2026-10-23, option 1a): those thin-cell laps are
--   priced here. The tax is theta_air x the previous lap's dirty-air share,
--   clamped to [0, 5.0] -- it needs no field base (the base cancels out of y_s,
--   T41), so the thin cell only ever blocked the tax component's row, not the
--   tax. `thin_priced` rebuilds the lag exactly as int_dirty_air_tax_component's
--   full_sequence_lag does (LAG over the whole stint, 0.0 only for a stint's
--   first lap, an unmeasured previous lap stays NULL), and it applies ONLY to a
--   lap with no tax-component row; a lap that has a row keeps that row's tax,
--   so a lap priced in both places gets the same number
--   (assert_isolation_thin_cell_tax_matches_component). Races where
--   var('isolation_thin_min_air_measured_share') of the laps or fewer have a
--   measured air state (2018_1 Australia and 2018_2 Bahrain, 6% each; no
--   telemetry in bronze) stay out, per the owner's 2026-10-15 decision. The
--   label spine is NOT touched: int_dirty_air_tax_component and the residual
--   chain still carry no row/0.0 on these laps, so no ML label moves from this.
--   is_thin_cell_tax flags the repriced laps. The car-term fit reads this panel,
--   so the isolation car FE refit is owed (see the item note).
--   The recovery overlay reads an unmeasured lap as unknown (is_dirty NULL),
--   not clean: it is its own run, it neither ends nor extends a dirty run, and
--   it is never itself a recovery lap. is_dirty_air_lap is NULL on such a lap.
--
-- LEAKAGE WARNING, reversed from fct_cliff_prediction_features: the isolation
-- ratings are functions of the residual trajectory. No ML-contract mart
-- (fct_cliff_prediction_features, fct_stint_features, fct_lap_residuals,
-- fct_driver_skill_features) may reference this model or anything downstream of
-- it. T48 (ml/tests/test_manifest_contract.py) enforces it on the dbt manifest.

{{ config(materialized='table', tags=['driver_isolation']) }}

{%- set exclude_races = var('isolation_exclude_races') %}

WITH theta AS (
    SELECT CAST({{ var('theta_air_label_value') }} AS DOUBLE) AS theta_air
),

-- W10 / v17: the previous lap's dirty-air share on every lap, the same
-- full-sequence lag int_dirty_air_tax_component prices from (header).
air_lag AS (
    SELECT
        g.lap_id,
        g.race_id,
        LAG(a.dirty_air_share_lap, 1, 0.0) OVER (
            PARTITION BY g.stint_id
            ORDER BY g.lap_in_stint
        ) AS share_lag1
    FROM {{ ref('int_stint_geometry') }} AS g
    LEFT JOIN {{ ref('int_lap_air_state') }} AS a
        ON g.lap_id = a.lap_id
),

race_air AS (
    SELECT
        race_id,
        AVG(CASE WHEN air_state_dominant IS NOT NULL THEN 1.0 ELSE 0.0 END)
            AS air_measured_share
    FROM {{ ref('int_lap_air_state') }}
    GROUP BY race_id
),

thin_priced AS (
    SELECT
        l.lap_id,
        l.share_lag1 AS dirty_air_intensity_lag1,
        CASE
            WHEN t.theta_air * l.share_lag1 < 0 THEN 0.0
            WHEN t.theta_air * l.share_lag1 > 5.0 THEN 5.0
            ELSE t.theta_air * l.share_lag1
        END AS dirty_air_tax_s
    FROM air_lag AS l
    INNER JOIN race_air AS ra
        ON l.race_id = ra.race_id
    CROSS JOIN theta AS t
    WHERE
        l.share_lag1 IS NOT NULL
        AND ra.air_measured_share
        > {{ var('isolation_thin_min_air_measured_share') }}
),

lap_source AS (
    SELECT
        r.lap_id,
        r.stint_id,
        r.race_year,
        r.race_id,
        r.driver_id,
        r.constructor_id,
        r.lap_number,
        r.compound,
        r.age_in_stint,
        r.lap_in_stint,
        r.valid_lap_in_stint,
        r.laps_past_cliff,
        r.fuel_mass_kg,
        r.lap_time_s,
        r.compound_component_s,
        -- W10 / v17: a lap with no tax-component row (thin field-base cell)
        -- is priced from thin_priced; the residual chain's 0.0 fill is not
        -- used. A lap with a row keeps its row.
        CASE
            WHEN da.lap_id IS NULL THEN tp.dirty_air_tax_s
            ELSE r.dirty_air_tax_s
        END AS dirty_air_tax_s,
        CASE
            WHEN da.lap_id IS NULL THEN tp.dirty_air_intensity_lag1
            ELSE r.dirty_air_intensity_lag1
        END AS dirty_air_intensity_lag1,
        da.lap_id IS NULL AND tp.lap_id IS NOT NULL AS is_thin_cell_tax,
        a.anomaly_class
    FROM {{ ref('int_lap_residual_decomposed') }} AS r
    INNER JOIN {{ ref('int_lap_anomaly_flags') }} AS a
        ON r.lap_id = a.lap_id
    LEFT JOIN {{ ref('int_dirty_air_tax_component') }} AS da
        ON r.lap_id = da.lap_id
    LEFT JOIN thin_priced AS tp
        ON r.lap_id = tp.lap_id
    WHERE
        r.correction_weight = 1.0
        AND a.anomaly_class IN ('normal', 'clean_cliff')
        AND NOT COALESCE(a.is_rain_lap, FALSE)
        AND NOT a.is_out_lap
        AND NOT a.is_in_lap
        AND r.compound NOT IN ('INTERMEDIATE', 'WET')
        AND r.compound_component_s IS NOT NULL
        AND r.laps_past_cliff IS NOT NULL
        -- FD6: a dirty-air tax that was priced, not filled (header). Priced
        -- by the tax component, or on a thin cell by thin_priced (W10, v17).
        AND (
            CASE
                WHEN da.lap_id IS NULL THEN tp.dirty_air_intensity_lag1
                ELSE r.dirty_air_intensity_lag1
            END
        ) IS NOT NULL
        {%- if exclude_races | length > 0 %}
            AND r.race_id NOT IN (
                {%- for rid in exclude_races %}
                    '{{ rid }}'{% if not loop.last %},{% endif %}
                {%- endfor %}
            )
        {%- endif %}
),

with_field_n AS (
    SELECT
        *,
        COUNT(*) OVER (PARTITION BY race_year, race_id, lap_number) AS field_n
    FROM lap_source
),

omega AS (
    SELECT
        *,
        lap_time_s - compound_component_s - dirty_air_tax_s AS x_s
    FROM with_field_n
    WHERE field_n >= {{ var('isolation_min_field_n') }}
),

-- A grouped median joined back, not MEDIAN() OVER (...): DuckDB 1.5.3 raises an
-- internal "unordered_map::at" error on a windowed median stacked on the
-- COUNT() OVER above.
field_median AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        MEDIAN(x_s) AS field_median_x_s,
        MEDIAN(compound_component_s) AS field_median_compound_component_s
    FROM omega
    GROUP BY race_year, race_id, lap_number
),

centred AS (
    SELECT
        o.*,
        fm.field_median_x_s,
        fm.field_median_compound_component_s
    FROM omega AS o
    INNER JOIN field_median AS fm
        ON
            o.race_year = fm.race_year
            AND o.race_id = fm.race_id
            AND o.lap_number = fm.lap_number
),

-- Recovery overlay, over every valid lap of the stint (not just Ω), so that a
-- dirty-air run is measured whole even where some of its laps fail Ω.
air AS (
    SELECT
        g.lap_id,
        g.stint_id,
        g.lap_number,
        -- NULL when the air state is unmeasured (FD6, header), not FALSE
        ai.air_state_dominant = 'dirty_air' AS is_dirty
    FROM {{ ref('int_stint_geometry') }} AS g
    LEFT JOIN {{ ref('int_lap_air_state') }} AS ai
        ON g.lap_id = ai.lap_id
    WHERE g.is_valid_lap
),

air_prev AS (
    SELECT
        *,
        LAG(is_dirty)
            OVER (PARTITION BY stint_id ORDER BY lap_number)
            AS prev_dirty
    FROM air
),

runs AS (
    SELECT
        lap_id,
        stint_id,
        lap_number,
        is_dirty,
        SUM(CASE WHEN is_dirty IS DISTINCT FROM prev_dirty THEN 1 ELSE 0 END)
            OVER (
                PARTITION BY stint_id ORDER BY lap_number
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS run_id
    FROM air_prev
),

run_len AS (
    SELECT
        stint_id,
        run_id,
        BOOL_AND(is_dirty) AS run_is_dirty,
        COUNT(*) AS n_laps
    FROM runs
    GROUP BY stint_id, run_id
),

recovery AS (
    SELECT
        r.lap_id,
        r.is_dirty,
        COALESCE(
            NOT r.is_dirty
            AND p.run_is_dirty
            AND p.n_laps >= {{ var('isolation_recovery_min_dirty_run') }}
            AND ROW_NUMBER() OVER (
                PARTITION BY r.stint_id, r.run_id ORDER BY r.lap_number
            ) <= {{ var('isolation_recovery_laps') }},
            FALSE
        ) AS is_recovery
    FROM runs AS r
    LEFT JOIN run_len AS p
        ON
            r.stint_id = p.stint_id
            AND r.run_id - 1 = p.run_id
),

phased AS (
    SELECT
        c.*,
        ai.air_state_dominant,
        -- FALSE where the lap has no recovery row (not a valid lap), as
        -- before; NULL only for an unmeasured air state (FD6, header).
        CASE
            WHEN rec.lap_id IS NULL THEN FALSE ELSE rec.is_dirty
        END AS is_dirty_air_lap,
        COALESCE(rec.is_recovery, FALSE) AS is_recovery,
        CASE
            WHEN c.laps_past_cliff > 0 THEN 'cliff'
            WHEN c.valid_lap_in_stint <= 5 THEN 'early'
            ELSE 'mid'
        END AS tyre_phase
    FROM centred AS c
    LEFT JOIN recovery AS rec
        ON c.lap_id = rec.lap_id
    LEFT JOIN {{ ref('int_lap_air_state') }} AS ai
        ON c.lap_id = ai.lap_id
)

SELECT
    p.lap_id,
    p.stint_id,
    p.race_year,
    p.race_id,
    p.driver_id,
    p.constructor_id,
    g.stint_number,
    p.lap_number,
    p.compound,
    p.age_in_stint,
    p.lap_in_stint,
    p.valid_lap_in_stint,
    p.laps_past_cliff,
    p.fuel_mass_kg,
    CASE
        WHEN p.race_year >= {{ var('era_boundary') }}
            THEN 'post{{ var("era_boundary") }}'
        ELSE 'pre{{ var("era_boundary") }}'
    END AS era,
    p.driver_id || '_' || CASE
        WHEN p.race_year >= {{ var('era_boundary') }}
            THEN 'post{{ var("era_boundary") }}'
        ELSE 'pre{{ var("era_boundary") }}'
    END AS driver_era,
    p.anomaly_class,
    p.air_state_dominant,
    p.is_dirty_air_lap,
    p.field_n,

    -- Inputs of x, carried so the identity can be re-derived downstream.
    p.lap_time_s,
    p.compound_component_s,
    p.dirty_air_tax_s,
    p.is_thin_cell_tax,

    -- Step 0 (s; positive = slower than the lap's field median).
    p.x_s,
    p.field_median_x_s,
    p.x_s - p.field_median_x_s AS y_s,
    p.compound_component_s - p.field_median_compound_component_s
        AS tyre_offset_vs_field_s,

    -- Phase.
    p.tyre_phase,
    p.is_recovery,
    CASE WHEN p.is_recovery THEN 'recovery' ELSE p.tyre_phase END AS stint_phase
FROM phased AS p
INNER JOIN {{ ref('int_stint_geometry') }} AS g
    ON p.lap_id = g.lap_id
