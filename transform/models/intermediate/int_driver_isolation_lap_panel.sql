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
-- LEAKAGE WARNING, reversed from fct_cliff_prediction_features: the isolation
-- ratings are functions of the residual trajectory. No ML-contract mart
-- (fct_cliff_prediction_features, fct_stint_features, fct_lap_residuals,
-- fct_driver_skill_features) may reference this model or anything downstream of
-- it. T48 (ml/tests/test_manifest_contract.py) enforces it on the dbt manifest.

{{ config(materialized='table', tags=['driver_isolation']) }}

{%- set exclude_races = var('isolation_exclude_races') %}

WITH lap_source AS (
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
        r.dirty_air_tax_s,
        a.anomaly_class
    FROM {{ ref('int_lap_residual_decomposed') }} AS r
    INNER JOIN {{ ref('int_lap_anomaly_flags') }} AS a
        ON r.lap_id = a.lap_id
    WHERE
        r.correction_weight = 1.0
        AND a.anomaly_class IN ('normal', 'clean_cliff')
        AND NOT COALESCE(a.is_rain_lap, FALSE)
        AND NOT a.is_out_lap
        AND NOT a.is_in_lap
        AND r.compound NOT IN ('INTERMEDIATE', 'WET')
        AND r.compound_component_s IS NOT NULL
        AND r.laps_past_cliff IS NOT NULL
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
        COALESCE(ai.air_state_dominant = 'dirty_air', FALSE) AS is_dirty
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
        COALESCE(rec.is_dirty, FALSE) AS is_dirty_air_lap,
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
