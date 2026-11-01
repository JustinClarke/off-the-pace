-- int_lap_wake_placeholder_cost.sql · intermediate · grain: one row per lap
--
-- WC-11 (_roadmap/_wake-calibration/wi/WC-11-interim-placeholder-values.md):
-- INTERIM PLACEHOLDER wake (dirty-air) cost per lap. The values are ASSUMED,
-- not measured or fitted. WC-12: the per-lap loss is set per race by a
-- transparent rule (int_wake_placeholder_race_loss: the race layout's corner
-- mix x a regulation-era factor, constants in seeds/wake_placeholder_rule.csv),
-- with the circuit-class values of seeds/wake_placeholder_values.csv as the
-- flagged fallback. Meant to be replaced by calibrated values later with no
-- downstream change: put them in loss_s_per_lap_within_1s (and set
-- value_kind) and every consumer keeps working.
--
-- WHAT IT COMPUTES
--   wake_cost_placeholder_s = loss_s_per_lap_within_1s x wake_exposure
--   wake_exposure (0..1, MEASURED) = share of the lap within 1.0 s of the car
--       ahead, plus half the share between 1.0 and 2.0 s:
--       share_lap_within_1s + 0.5 * (share_lap_within_2s - share_lap_within_1s)
--   i.e. the full assumed loss inside 1.0 s, tapering linearly to zero at
--   2.0 s (0.5 is the average of a linear 1 -> 0 taper over the 1-2 s band),
--   nothing beyond 2.0 s. The shares are int_lap_proximity's crossing-time
--   gaps (same point on track, same session clock), not the speed-converted
--   DistanceToDriverAhead gap. Current lap, not lagged: this is a display
--   cost, not an identified estimate.
--   Not included: being held up (blocking), the tow gain on straights, DRS,
--   tyre wear. Era differences enter only through the assumed era factor.
--
-- WC-13: TYRE AND CAR MULTIPLIERS (assumptions, bounded, flagged)
--   loss_s_per_lap_within_1s = ROUND(clamp(race_loss x compound_factor
--                              x constructor_factor, min_s, max_s), 4)
--   race_loss_s_per_lap_within_1s is the WC-12 per-race value, unchanged.
--   compound_factor (seeds/wake_placeholder_compound_factor.csv) is keyed by
--   the lap's RELATIVE dry class in its race: 2019 on, FastF1's
--   SOFT/MEDIUM/HARD label; 2018 (absolute names, HYPERSOFT..HARD), the
--   softest / middle / hardest of the race's three dry compounds, ranked by
--   compound_hardness_scale (every 2018 race shows exactly three; any other
--   count is unresolved).
--   A small thermal / grip sensitivity on the per-lap loss, NOT tyre wear.
--   INTERMEDIATE and WET are neutral by rule. constructor_factor
--   (seeds/wake_placeholder_constructor_factor.csv, per season x
--   constructor_id) is a neutral 1.00 for every team today: plumbing only,
--   no per-team claim.
--   A lap with no compound, an unresolved compound, no constructor or no seed
--   row gets the rule seed's neutral_default AND a factor_flag, never silently.
--   Rounded to 4 dp, not 0.01: at 0.01 some race x tyre products land on 0.40,
--   an archived-method number (rule 6).
--   Reads only identity columns from stg_laps (lap_id, race_id, race_year,
--   compound, constructor_id); no lap time or speed.
--
-- WC-16: C-NUMBER TYRE FACTOR (DD-WC28, owner 2026-10-31)
--   A 2019+ dry lap whose race has a verified trio in
--   seeds/wake_placeholder_tyre_allocation.csv (all 152 races 2019-2025) maps
--   its relative label (HARD / MEDIUM / SOFT) to the race's C-number
--   (tyre_c_number) and takes, from seeds/wake_placeholder_c_number_factor.csv,
--     compound_factor = ROUND(clamp(step x medium_shift, 0.90, 1.17), 4)
--   step: by the distance in C-numbers from the race's MEDIUM (two or more
--   harder 0.93, one harder 0.96, medium 1.00, one softer 1.10, two or more
--   softer 1.17), so a race whose labels skip a C-number follows the actual
--   gap; medium_shift: by the race's MEDIUM, 1.00 for C2-C5 since owner
--   ruling DD-WC29 (2026-10-31: the proposed 0.97-1.06 shift put 23 per-lap
--   values on archived-method numbers at 3 dp; rule 6 stays strict). The rows
--   stay so a calibrated shift can slot in. A medium with no shift row
--   (C1 / C6) fails
--   assert_wake_placeholder_tyre_allocation; such a race would use the
--   relative class. compound_factor_scale = 'c_number'.
--   2018 (named compounds, no C-numbers) and any race with no trio keep the
--   WC-13 relative factors above (compound_factor_scale = 'relative_class').
--   Wet / intermediate / missing / unresolved stay neutral 1.00 and flagged
--   as before (compound_factor_scale = 'neutral').
--   The user-supplied seeds/tyre_allocations.csv is NOT read.
--
-- WHAT IT IS NOT
--   * Not an ML feature and not an ML target. ML keeps the measured gap
--     features (int_lap_proximity via fct_cliff_prediction_features); nothing
--     in the label spine (int_dirty_air_tax_component,
--     int_lap_residual_decomposed,
--     fct_cliff_prediction_features) reads this model. A model trained on these
--     values would relearn the assumption and look validated.
--   * Not the label's dirty-air term. dirty_air_tax_s (theta_air) is unchanged.
--   * Uses no number from the archived dirty-air method (BUILD-ORDER rule 6).
--
-- LABELS (BUILD-ORDER rule 7): every value is `modelled` (value_kind
-- 'placeholder') and carries the DD-WC2 disclaimer word for word plus a
-- second, placeholder line (WC-11 note). An unavailable lap is NULL with an
-- unavailable_reason, never 0. A modelled 0 (a measured lap with no car within
-- 2 s) is a real modelled value, not an unavailable one.
{{ config(materialized='table', tags=['wake_placeholder']) }}

WITH race_loss AS (
    SELECT * FROM {{ ref('int_wake_placeholder_race_loss') }}
),

laps AS (
    SELECT
        p.lap_id,
        p.stint_id,
        p.race_year,
        CAST(p.race_id AS VARCHAR) AS race_id,
        p.driver_id,
        p.lap_number,
        p.is_neutralised_lap,
        p.proximity_bin_count,
        p.share_lap_within_1s,
        p.share_lap_within_2s,
        p.gap_ahead_median_s
    FROM {{ ref('int_lap_proximity') }} AS p
),

rule AS (
    SELECT
        MAX(CASE WHEN param = 'min_s' THEN value END) AS min_s,
        MAX(CASE WHEN param = 'max_s' THEN value END) AS max_s,
        MAX(
            CASE
                WHEN
                    param_kind = 'factor' AND param = 'neutral_default'
                    THEN value
            END
        ) AS neutral_factor
    FROM {{ ref('wake_placeholder_rule') }}
),

-- WC-16: the race's verified dry trio as C-numbers (2019 on; 2018 rows have
-- named compounds only and are not used here) and the C-number rule constants.
c_trio AS (
    SELECT
        CAST(race_id AS VARCHAR) AS race_id,
        hard_c,
        medium_c,
        soft_c
    FROM {{ ref('wake_placeholder_tyre_allocation') }}
    WHERE compound_scale = 'c_number'
),

c_rule AS (
    SELECT
        param_kind,
        param,
        value
    FROM {{ ref('wake_placeholder_c_number_factor') }}
),

c_bound AS (
    SELECT
        MAX(CASE WHEN param = 'min' THEN value END) AS c_min,
        MAX(CASE WHEN param = 'max' THEN value END) AS c_max
    FROM c_rule
    WHERE param_kind = 'bound'
),

-- identity columns only: no lap time, sector time or speed
lap_identity AS (
    SELECT
        lap_id,
        CAST(race_id AS VARCHAR) AS race_id,
        race_year,
        compound,
        constructor_id
    FROM {{ ref('stg_laps') }}
),

-- 2018 used absolute names; the race's relative class is its rank among the
-- race's three dry compounds (1 = softest).
legacy_dry AS (
    SELECT DISTINCT
        li.race_id,
        li.compound,
        h.hardness_rank
    FROM lap_identity AS li
    INNER JOIN {{ ref('compound_hardness_scale') }} AS h
        ON
            li.compound = CAST(h.compound_code AS VARCHAR)
            AND CAST(h.era AS VARCHAR) = '2018'
    WHERE li.race_year <= 2018
),

legacy_class AS (
    SELECT
        race_id,
        compound,
        COUNT(*) OVER (PARTITION BY race_id) AS n_dry_compounds,
        DENSE_RANK()
            OVER (PARTITION BY race_id ORDER BY hardness_rank DESC)
            AS softness_pos
    FROM legacy_dry
),

tyre_car AS (
    SELECT
        li.lap_id,
        li.compound,
        li.constructor_id,
        CASE
            WHEN li.compound IS NULL THEN NULL
            WHEN li.compound IN ('INTERMEDIATE', 'WET') THEN li.compound
            WHEN li.race_year <= 2018 AND lc.n_dry_compounds = 3
                THEN CASE lc.softness_pos
                    WHEN 1 THEN 'SOFT'
                    WHEN 2 THEN 'MEDIUM'
                    WHEN 3 THEN 'HARD'
                END
            WHEN li.race_year <= 2018 THEN NULL
            WHEN li.compound IN ('SOFT', 'MEDIUM', 'HARD') THEN li.compound
        END AS compound_class,
        CASE
            WHEN li.compound IS NULL THEN 'neutral_missing_compound'
            WHEN
                li.compound IN ('INTERMEDIATE', 'WET')
                THEN 'neutral_wet_or_intermediate'
            WHEN
                li.race_year <= 2018 AND lc.n_dry_compounds = 3
                THEN 'assumed_race_order_2018'
            WHEN li.race_year <= 2018 THEN 'neutral_unresolved_compound'
            WHEN
                li.compound IN ('SOFT', 'MEDIUM', 'HARD')
                AND sh.value IS NOT NULL
                THEN 'assumed_c_number'
            WHEN
                li.compound IN ('SOFT', 'MEDIUM', 'HARD')
                THEN 'assumed_relative_label'
            ELSE 'neutral_unresolved_compound'
        END AS compound_factor_source,
        CASE
            WHEN
                li.race_year > 2018
                AND li.compound IN ('SOFT', 'MEDIUM', 'HARD')
                AND sh.value IS NOT NULL
                THEN CASE li.compound
                    WHEN 'HARD' THEN ct.hard_c
                    WHEN 'MEDIUM' THEN ct.medium_c
                    WHEN 'SOFT' THEN ct.soft_c
                END
        END AS tyre_c_number,
        ct.medium_c AS race_medium_c,
        sh.value AS medium_shift
    FROM lap_identity AS li
    LEFT JOIN legacy_class AS lc
        ON li.race_id = lc.race_id AND li.compound = lc.compound
    LEFT JOIN c_trio AS ct
        ON li.race_id = ct.race_id AND li.race_year > 2018
    LEFT JOIN c_rule AS sh
        ON sh.param_kind = 'medium_shift' AND ct.medium_c = sh.param
),

-- WC-16: steps in C-numbers from the race's MEDIUM (positive = softer),
-- capped at two each way ("two or more"), and the step constant.
tyre_c AS (
    SELECT
        tc.*,
        CAST(SUBSTR(tc.tyre_c_number, 2) AS INTEGER)
        - CAST(SUBSTR(tc.race_medium_c, 2) AS INTEGER) AS c_steps,
        st.value AS c_step_factor
    FROM tyre_car AS tc
    LEFT JOIN c_rule AS st
        ON
            st.param_kind = 'step'
            AND st.param = CAST(
                GREATEST(
                    LEAST(
                        CAST(SUBSTR(tc.tyre_c_number, 2) AS INTEGER)
                        - CAST(SUBSTR(tc.race_medium_c, 2) AS INTEGER),
                        2
                    ),
                    -2
                ) AS VARCHAR
            )
),

resolved AS (
    SELECT
        l.*,
        r.circuit_key,
        r.corner_class,
        r.class_source,
        r.era,
        r.era_factor,
        r.loss_source,
        r.loss_bounded,
        r.loss_basis,
        r.loss_s_per_lap_within_1s,
        r.value_kind,
        r.loss_s_per_lap_within_1s AS race_loss_s,
        t.compound,
        t.compound_class,
        t.tyre_c_number,
        t.race_medium_c,
        CASE
            WHEN t.compound_factor_source = 'assumed_c_number'
                THEN ROUND(
                    LEAST(
                        GREATEST(t.c_step_factor * t.medium_shift, cb.c_min),
                        cb.c_max
                    ),
                    4
                )
            ELSE COALESCE(cf.factor, rule.neutral_factor)
        END AS compound_factor,
        t.compound_factor_source,
        CASE
            WHEN t.compound_factor_source = 'assumed_c_number' THEN 'c_number'
            WHEN
                t.compound_factor_source IN (
                    'assumed_relative_label', 'assumed_race_order_2018'
                )
                THEN 'relative_class'
            ELSE 'neutral'
        END AS compound_factor_scale,
        CASE
            WHEN t.compound_factor_source = 'assumed_c_number'
                THEN PRINTF(
                    'C-number rule: %s is %d C-number(s) %s the race medium %s '
                    || '(step x%.2f); medium shift x%.2f',
                    t.tyre_c_number,
                    ABS(t.c_steps),
                    CASE
                        WHEN t.c_steps < 0 THEN 'harder than'
                        WHEN t.c_steps > 0 THEN 'softer than'
                        ELSE 'from'
                    END,
                    t.race_medium_c,
                    t.c_step_factor,
                    t.medium_shift
                )
            ELSE cf.basis
        END AS compound_basis,
        t.constructor_id,
        COALESCE(kf.constructor_lineage_id, dc.constructor_lineage_id)
            AS constructor_lineage_id,
        COALESCE(kf.factor, rule.neutral_factor) AS constructor_factor,
        CASE
            WHEN t.constructor_id IS NULL THEN 'neutral_missing_constructor'
            WHEN kf.constructor_id IS NULL THEN 'neutral_no_constructor_row'
            ELSE kf.source_type
        END AS constructor_factor_source,
        COALESCE(
            kf.basis,
            'neutral default: no car factor row for this team and season'
        ) AS constructor_basis,
        rule.min_s,
        rule.max_s
    FROM laps AS l
    LEFT JOIN race_loss AS r ON l.race_id = r.race_id
    LEFT JOIN tyre_c AS t ON l.lap_id = t.lap_id
    LEFT JOIN {{ ref('wake_placeholder_compound_factor') }} AS cf
        ON t.compound_class = cf.compound_class
    CROSS JOIN c_bound AS cb
    LEFT JOIN {{ ref('wake_placeholder_constructor_factor') }} AS kf
        ON l.race_year = kf.season AND t.constructor_id = kf.constructor_id
    LEFT JOIN {{ ref('dim_constructors') }} AS dc
        ON t.constructor_id = dc.constructor_id
    CROSS JOIN rule
),

factored AS (
    SELECT
        resolved.* EXCLUDE (loss_s_per_lap_within_1s),
        race_loss_s * compound_factor * constructor_factor AS lap_loss_raw_s,
        ROUND(
            LEAST(
                GREATEST(
                    race_loss_s * compound_factor * constructor_factor, min_s
                ),
                max_s
            ),
            4
        )
            AS loss_s_per_lap_within_1s,
        CONCAT_WS(
            '; ',
            CASE
                WHEN compound_factor_source = 'neutral_missing_compound'
                    THEN 'no compound on this lap: neutral tyre factor'
            END,
            CASE
                WHEN compound_factor_source = 'neutral_unresolved_compound'
                    THEN 'compound class unresolved: neutral tyre factor'
            END,
            CASE
                WHEN constructor_factor_source = 'neutral_missing_constructor'
                    THEN 'no constructor on this lap: neutral car factor'
            END,
            CASE
                WHEN constructor_factor_source = 'neutral_no_constructor_row'
                    THEN 'no car factor row: neutral car factor'
            END
        ) AS factor_flag_raw
    FROM resolved
),

scored AS (
    SELECT
        *,
        CASE
            WHEN proximity_bin_count IS NULL
                THEN 'no gap measured on this lap'
            WHEN is_neutralised_lap
                THEN 'neutralised lap (safety car, VSC or red flag)'
            WHEN loss_s_per_lap_within_1s IS NULL
                THEN 'no placeholder value for this race'
        END AS unavailable_reason,
        share_lap_within_1s
        + 0.5 * (share_lap_within_2s - share_lap_within_1s) AS exposure_raw
    FROM factored
)

SELECT
    lap_id,
    stint_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    circuit_key,
    corner_class,
    class_source,
    -- WC-12: the per-race assumed loss and how it was set
    era,
    era_factor,
    loss_source,
    loss_bounded,
    loss_basis,
    -- WC-13: the per-lap assumed loss = race value x tyre x car, bounded
    loss_s_per_lap_within_1s,
    race_loss_s AS race_loss_s_per_lap_within_1s,
    compound,
    compound_class,
    compound_factor,
    compound_factor_source,
    compound_basis,
    -- WC-16: which tyre scale set the factor, and the lap's C-number
    compound_factor_scale,
    tyre_c_number,
    race_medium_c,
    constructor_id,
    constructor_lineage_id,
    constructor_factor,
    constructor_factor_source,
    constructor_basis,
    lap_loss_raw_s IS NOT NULL
    AND (lap_loss_raw_s < min_s OR lap_loss_raw_s > max_s) AS lap_loss_bounded,
    NULLIF(factor_flag_raw, '') AS factor_flag,
    CASE
        WHEN race_loss_s IS NOT NULL THEN PRINTF(
            'Assumed: race value %.2f s x tyre %.2f (%s) x car %.2f (%s)%s',
            race_loss_s,
            compound_factor,
            COALESCE(
                compound_class || COALESCE(' ' || tyre_c_number, ''),
                'unresolved'
            ),
            constructor_factor, constructor_factor_source,
            CASE
                WHEN lap_loss_raw_s < min_s OR lap_loss_raw_s > max_s
                    THEN PRINTF('; held to %.2f-%.2f s', min_s, max_s)
                ELSE ''
            END
        )
    END AS lap_loss_basis,
    -- measured inputs, carried for display and audit
    gap_ahead_median_s,
    share_lap_within_1s,
    share_lap_within_2s,
    CASE
        WHEN unavailable_reason IS NULL THEN ROUND(exposure_raw, 4)
    END AS wake_exposure,
    CASE
        WHEN unavailable_reason IS NULL
            THEN ROUND(loss_s_per_lap_within_1s * exposure_raw, 4)
    END AS wake_cost_placeholder_s,
    CASE
        WHEN unavailable_reason IS NULL THEN 'modelled' ELSE 'unavailable'
    END AS value_label,
    value_kind,
    unavailable_reason,
    -- DD-WC2, word for word (build-log.json, DD-WC2 resolution; reworded by
    -- the owner 2026-10-31).
    'Modelled: an assumed typical loss for this circuit, season, tyre and car, applied to the measured time spent close behind another car. Not calibrated on this driver''s own stints.'  -- noqa: LT05
        AS disclaimer,
    -- Placeholder line, word for word (DD-WC30, 2026-11-01).
    'Placeholder = an interim value set by a fixed rule, not a measurement of this lap.'  -- noqa: LT05
        AS disclaimer_placeholder
FROM scored
