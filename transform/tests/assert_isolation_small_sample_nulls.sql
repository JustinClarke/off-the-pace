-- T46 (WI-16a): floors are NULLs, never zeros, and no NaN escapes.
--
-- The F1/F7 defect class is a missing measurement COALESCEd to 0 and then read as "no
-- effect". The isolation ratings put hard floors before shrinkage, and below a floor the
-- value must be NULL:
--   window    each 5-lap value NULL iff its count < var('isolation_window_min_laps')
--             (non-extrapolated laps / tactical laps / pair-laps)
--   tactical  NULL on every lap of a stint whose line has < var('isolation_min_stint_laps')
--             laps (then m_s is NULL), and never non-NULL -- in particular never exactly 0.0
--             -- where m_s is NULL
--   relative  NULL iff the lap has no peer (n_peers = 0)
--   confidence_pct never without a lambda, at any grain
--   NaN       DuckDB's REGR_SLOPE returns NaN, not NULL, when n < 2 or Sxx = 0; no
--             rating, slope or SE column may hold one (isnan)

{%- set min_n = var('isolation_window_min_laps') %}
{%- set min_line = var('isolation_min_stint_laps') %}

WITH lap_mart AS (
    SELECT * FROM {{ ref('fct_driver_isolation_lap') }}
)

SELECT 'window pure: NULL iff count < floor' AS issue, lap_id AS row_id
FROM lap_mart
WHERE (pure_skill_5lap_gain_s IS NULL) != (window_n_pure_laps < {{ min_n }})

UNION ALL
SELECT 'window tactical: NULL iff count < floor' AS issue, lap_id AS row_id
FROM lap_mart
WHERE (tactical_5lap_gain_s IS NULL) != (window_n_tactical_laps < {{ min_n }})

UNION ALL
SELECT 'window relative: NULL iff pair-laps < floor' AS issue, lap_id AS row_id
FROM lap_mart
WHERE (relative_pace_5lap_gain_s IS NULL) != (window_n_pair_laps < {{ min_n }})

UNION ALL
SELECT 'relative: NULL iff no peer' AS issue, lap_id AS row_id
FROM lap_mart
WHERE (relative_pace_gain_s IS NULL) != (n_peers = 0)

UNION ALL
SELECT 'tactical: value where m_s is NULL' AS issue, lap_id AS row_id
FROM {{ ref('int_driver_isolation_lap_values') }}
WHERE tactical_gain_s IS NOT NULL AND tactical_slope_s_per_lap2 IS NULL

UNION ALL
SELECT 'tactical: slope on a line below the floor' AS issue, stint_id AS row_id
FROM {{ ref('int_driver_isolation_stint_tyre') }}
WHERE
    n_line_laps < {{ min_line }}
    AND (line_slope_s_per_lap2 IS NOT NULL OR tactical_slope_s_per_lap2 IS NOT NULL)

UNION ALL
SELECT 'NaN in a stint slope or SE' AS issue, stint_id AS row_id
FROM {{ ref('int_driver_isolation_stint_tyre') }}
WHERE
    ISNAN(line_slope_s_per_lap2)
    OR ISNAN(tactical_slope_s_per_lap2)
    OR ISNAN(line_slope_se_s_per_lap2)
    OR ISNAN(tactical_slope_se_s_per_lap2)
    OR ISNAN(kappa_ref_gain_s)

UNION ALL
SELECT 'NaN in a lap rating' AS issue, lap_id AS row_id
FROM lap_mart
WHERE
    ISNAN(pace_isolated_gain_s)
    OR ISNAN(pure_skill_gain_s)
    OR ISNAN(tactical_gain_s)
    OR ISNAN(relative_pace_gain_s)
    OR ISNAN(pure_skill_5lap_gain_s)
    OR ISNAN(tactical_5lap_gain_s)
    OR ISNAN(relative_pace_5lap_gain_s)
    OR ISNAN(pure_skill_5lap_se_s)
    OR ISNAN(tactical_5lap_se_s)
    OR ISNAN(relative_pace_5lap_se_s)

UNION ALL
SELECT 'window: confidence without lambda' AS issue, lap_id AS row_id
FROM lap_mart
WHERE
    (pure_skill_5lap_confidence_pct IS NOT NULL AND pure_skill_5lap_lambda IS NULL)
    OR (tactical_5lap_confidence_pct IS NOT NULL AND tactical_5lap_lambda IS NULL)
    OR (relative_pace_5lap_confidence_pct IS NOT NULL AND relative_pace_5lap_lambda IS NULL)

UNION ALL
SELECT 'stint: confidence without lambda' AS issue, stint_phase_id AS row_id
FROM {{ ref('fct_driver_isolation_stint') }}
WHERE
    (pure_skill_confidence_pct IS NOT NULL AND pure_skill_lambda IS NULL)
    OR (tactical_confidence_pct IS NOT NULL AND tactical_lambda IS NULL)
    OR (relative_pace_confidence_pct IS NOT NULL AND relative_pace_lambda IS NULL)

UNION ALL
SELECT 'race: confidence without lambda' AS issue, driver_race_id AS row_id
FROM {{ ref('fct_driver_isolation_race') }}
WHERE
    (pure_skill_confidence_pct IS NOT NULL AND pure_skill_lambda IS NULL)
    OR (tactical_confidence_pct IS NOT NULL AND tactical_lambda IS NULL)
    OR (relative_pace_confidence_pct IS NOT NULL AND relative_pace_lambda IS NULL)
