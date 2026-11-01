-- int_wake_placeholder_race_loss.sql · intermediate · grain: one row per race
--
-- WC-12 (_roadmap/_wake-calibration/wi/WC-11-interim-placeholder-values.md,
-- section "WC-12"):
-- the ASSUMED per-race wake loss that int_lap_wake_placeholder_cost scales by
-- each lap's measured exposure. A transparent rule, not a fit: nothing here
-- reads a lap time, a segment time or a speed, for any season.
--
-- THE RULE (every constant is in seeds/wake_placeholder_rule.csv, with its
-- basis)
--   corner_index  = 1.00 x n_fast + 0.50 x n_medium + 0.25 x n_slow
--                   + 0.25 x n_flat
--                   (fast-corner equivalents on the race's layout; the counts
--                   are seeds/wake_placeholder_race_structure.csv, built by
--                   tasks/wake_calibration/wc12_structure.py from STRUCTURE
--                   columns only)
--   loss_raw_s    = era_factor(season) x 0.35 x corner_index / 8
--   loss          = ROUND(clamp(loss_raw_s, 0.15, 0.55), 2)
--
-- FALLBACK (flagged, never silent): a race with no structure row (no telemetry
-- in bronze, no FastF1 corner table, a new venue) uses
--   era_factor(season) x class value (seeds/wake_placeholder_values.csv; the
--   class values are read as 2017-18-era values), clamped and rounded the same
--   way, with loss_source = 'class_fallback'. A season past the last assessed
--   era carries the latest factor and era_assessed = false.
--
-- REPLACEABLE: calibrated values slot into loss_s_per_lap_within_1s (set
-- value_kind and loss_source); int_lap_wake_placeholder_cost and the app
-- read only these columns.
{{ config(materialized='table', tags=['wake_placeholder']) }}

WITH rule AS (
    SELECT param_kind, param, season_from, season_to, value
    FROM {{ ref('wake_placeholder_rule') }}
),

p AS (
    SELECT
        MAX(CASE WHEN param_kind = 'weight' AND param = 'fast' THEN value END)
            AS w_fast,
        MAX(
            CASE WHEN param_kind = 'weight' AND param = 'medium' THEN value END
        ) AS w_medium,
        MAX(CASE WHEN param_kind = 'weight' AND param = 'slow' THEN value END)
            AS w_slow,
        MAX(CASE WHEN param_kind = 'weight' AND param = 'flat' THEN value END)
            AS w_flat,
        MAX(CASE WHEN param = 'loss_at_reference_s' THEN value END)
            AS loss_ref_s,
        MAX(CASE WHEN param = 'reference_index' THEN value END) AS index_ref,
        MAX(CASE WHEN param = 'min_s' THEN value END) AS min_s,
        MAX(CASE WHEN param = 'max_s' THEN value END) AS max_s
    FROM rule
),

era AS (
    SELECT
        param AS era,
        season_from,
        season_to,
        value AS era_factor,
        param <> '2026_on_unassessed' AS era_assessed
    FROM rule
    WHERE param_kind = 'era'
),

cfg AS (
    SELECT row_kind, key, corner_class, loss_s_per_lap_within_1s, value_kind
    FROM {{ ref('wake_placeholder_values') }}
),

races AS (
    SELECT DISTINCT
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(SPLIT_PART(CAST(race_id AS VARCHAR), '_', 1) AS INTEGER)
            AS race_year
    FROM {{ ref('race_to_track') }}
    UNION
    SELECT DISTINCT
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(race_year AS INTEGER) AS race_year
    FROM {{ ref('int_lap_proximity') }}
),

unlisted AS (
    SELECT corner_class FROM cfg
    WHERE row_kind = 'unlisted_default'
),

resolved AS (
    SELECT
        r.race_year,
        r.race_id,
        rt.track_id AS circuit_key,
        COALESCE(c.corner_class, u.corner_class) AS corner_class,
        CASE
            WHEN
                c.loss_s_per_lap_within_1s IS NOT NULL
                THEN 'circuit_entry_override'
            WHEN c.corner_class IS NOT NULL THEN 'circuit_entry'
            ELSE 'unlisted_circuit_default'
        END AS class_source,
        COALESCE(c.loss_s_per_lap_within_1s, d.loss_s_per_lap_within_1s)
            AS class_loss_s,
        d.value_kind,
        e.era,
        e.era_factor,
        e.era_assessed,
        s.n_corners,
        s.layout_seasons,
        s.n_fast,
        s.n_medium,
        s.n_slow,
        s.n_flat,
        s.race_id IS NOT NULL AS has_structure
    FROM races AS r
    LEFT JOIN {{ ref('race_to_track') }} AS rt
        ON r.race_id = CAST(rt.race_id AS VARCHAR)
    LEFT JOIN cfg AS c
        ON c.row_kind = 'circuit' AND rt.track_id = c.key
    CROSS JOIN unlisted AS u
    LEFT JOIN cfg AS d
        ON
            d.row_kind = 'class_default'
            AND COALESCE(c.corner_class, u.corner_class) = d.corner_class
    LEFT JOIN era AS e
        ON r.race_year BETWEEN e.season_from AND e.season_to
    LEFT JOIN {{ ref('wake_placeholder_race_structure') }} AS s
        ON r.race_id = CAST(s.race_id AS VARCHAR)
),

scored AS (
    SELECT
        resolved.*,
        p.min_s,
        p.max_s,
        CASE
            WHEN resolved.has_structure THEN
                p.w_fast * resolved.n_fast
                + p.w_medium * resolved.n_medium
                + p.w_slow * resolved.n_slow
                + p.w_flat * resolved.n_flat
        END AS corner_index,
        CASE
            WHEN resolved.has_structure
                THEN
                    resolved.era_factor * p.loss_ref_s
                    * (
                        p.w_fast * resolved.n_fast
                        + p.w_medium * resolved.n_medium
                        + p.w_slow * resolved.n_slow
                        + p.w_flat * resolved.n_flat
                    )
                    / p.index_ref
            ELSE resolved.era_factor * resolved.class_loss_s
        END AS loss_raw_s
    FROM resolved
    CROSS JOIN p
)

SELECT
    race_year,
    race_id,
    circuit_key,
    corner_class,
    class_source,
    era,
    era_factor,
    era_assessed,
    CASE WHEN has_structure THEN 'race_structure' ELSE 'class_fallback' END
        AS loss_source,
    n_corners,
    layout_seasons,
    n_fast,
    n_medium,
    n_slow,
    n_flat,
    ROUND(corner_index, 3) AS corner_index,
    ROUND(loss_raw_s, 4) AS loss_raw_s,
    loss_raw_s < min_s OR loss_raw_s > max_s AS loss_bounded,
    ROUND(LEAST(GREATEST(loss_raw_s, min_s), max_s), 2)
        AS loss_s_per_lap_within_1s,
    value_kind,
    CASE
        WHEN has_structure
            THEN PRINTF(
                'Assumed rule: %.2f fast-corner equivalents (%g fast, %g medium, %g slow, %g flat-out kinks) x era factor %.2f (%s)%s',  -- noqa: LT05
                corner_index, n_fast, n_medium, n_slow, n_flat, era_factor, era,
                CASE
                    WHEN loss_raw_s < min_s OR loss_raw_s > max_s
                        THEN
                            PRINTF(
                                '; held to the %.2f-%.2f s bounds', min_s, max_s
                            )
                    ELSE ''
                END
            )
        ELSE PRINTF(
            'Fallback: no corner structure for this race, so the %s circuit class value x era factor %.2f (%s)%s',  -- noqa: LT05
            corner_class, era_factor, era,
            CASE
                WHEN loss_raw_s < min_s OR loss_raw_s > max_s
                    THEN
                        PRINTF('; held to the %.2f-%.2f s bounds', min_s, max_s)
                ELSE ''
            END
        )
    END
    || CASE
        WHEN
            NOT era_assessed
            THEN '; era not assessed, latest factor carried forward'
        ELSE ''
    END
        AS loss_basis
FROM scored
