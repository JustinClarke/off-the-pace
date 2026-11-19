-- int_corner_length_measured.sql · intermediate · grain: one row per race x corner
-- PK: (race_id, corner_name). One row per dim_corners corner that has an apex.
--
-- MEASURED corner length in metres for the mid-corner term of
-- int_corner_skill_residuals (L_m * (1/v_own - 1/v_field)).
--
-- The per-lap measurement (brake onset to throttle >= 90 %, 0.3 s flicker merge,
-- 600 m guards, 0 < length <= 1200 m) now lives in int_corner_lap_measured,
-- together with the validation flags. This model aggregates it twice:
--   RAW        every measured clean-lap observation -> corner_length_raw_m
--   VALIDATED  observations that are not demonstrably invalid (stopped,
--              near-stopped, distance-axis misalignment; see
--              int_corner_lap_measured) -> corner_length_m, the column
--              downstream models read.
-- Raw measurements are preserved. Statistical speed outliers are NOT excluded.
--
-- PER CORNER: median across laps and drivers of ONE RACE. Fewer than 5
-- observations gives NULL (no constant fallback). Count and IQR are reported
-- for both views. Linked-corner quality: share of validated laps flagged
-- throttle-past-next-apex / brake-before-previous-apex (definition of linked
-- corners unchanged), and a cell flag when at least half the laps are flagged.
--
-- GRAIN CHOICE: per race, not per track (layouts and numbering change between
-- seasons; nothing is pooled across races).
{{ config(materialized='table', tags=['intermediate', 'feature_engineering']) }}

WITH corners AS (
    SELECT race_id, race_year, track_id, corner_name, apex_distance_m
    FROM {{ ref('dim_corners') }}
    WHERE apex_distance_m IS NOT NULL
),

laps AS (
    SELECT * FROM {{ ref('int_corner_lap_measured') }}
),

raw_agg AS (
    SELECT
        race_id, corner_name,
        COUNT(*) AS n_laps_raw,
        MEDIAN(length_m) AS median_raw_m,
        QUANTILE_CONT(length_m, 0.25) AS p25_raw_m,
        QUANTILE_CONT(length_m, 0.75) AS p75_raw_m
    FROM laps
    GROUP BY race_id, corner_name
),

valid_agg AS (
    SELECT
        race_id, corner_name,
        COUNT(*) AS n_laps_measured,
        MEDIAN(length_m) AS median_length_m,
        QUANTILE_CONT(length_m, 0.25) AS length_p25_m,
        QUANTILE_CONT(length_m, 0.75) AS length_p75_m,
        AVG(linked_corner_flag::INTEGER) AS linked_corner_share,
        AVG(throttle_past_next_apex::INTEGER) AS throttle_past_next_share,
        AVG(brake_before_prev_apex::INTEGER) AS brake_before_prev_share
    FROM laps
    WHERE exclusion_reason IS NULL
    GROUP BY race_id, corner_name
),

excl AS (
    SELECT
        race_id, corner_name,
        COUNT(*) FILTER (WHERE exclusion_reason = 'stopped') AS n_excluded_stopped,
        COUNT(*) FILTER (WHERE exclusion_reason = 'near_stopped') AS n_excluded_near_stopped,
        COUNT(*) FILTER (WHERE exclusion_reason = 'misaligned_global_lap') AS n_excluded_misaligned_lap,
        COUNT(*) FILTER (WHERE exclusion_reason = 'misaligned_corner') AS n_excluded_misaligned_corner
    FROM laps
    GROUP BY race_id, corner_name
)

SELECT
    c.race_id,
    c.race_year,
    c.track_id,
    c.corner_name,
    c.apex_distance_m,
    COALESCE(v.n_laps_measured, 0) AS n_laps_measured,
    COALESCE(r.n_laps_raw, 0) AS n_laps_raw,
    CASE WHEN v.n_laps_measured >= 5 THEN v.median_length_m END AS corner_length_m,
    CASE WHEN v.n_laps_measured >= 5 THEN v.length_p75_m - v.length_p25_m END AS length_iqr_m,
    CASE WHEN v.n_laps_measured >= 5 THEN v.length_p25_m END AS length_p25_m,
    CASE WHEN v.n_laps_measured >= 5 THEN v.length_p75_m END AS length_p75_m,
    CASE WHEN r.n_laps_raw >= 5 THEN r.median_raw_m END AS corner_length_raw_m,
    CASE WHEN r.n_laps_raw >= 5 THEN r.p25_raw_m END AS length_raw_p25_m,
    CASE WHEN r.n_laps_raw >= 5 THEN r.p75_raw_m END AS length_raw_p75_m,
    COALESCE(x.n_excluded_stopped, 0) AS n_excluded_stopped,
    COALESCE(x.n_excluded_near_stopped, 0) AS n_excluded_near_stopped,
    COALESCE(x.n_excluded_misaligned_lap, 0) AS n_excluded_misaligned_lap,
    COALESCE(x.n_excluded_misaligned_corner, 0) AS n_excluded_misaligned_corner,
    v.linked_corner_share,
    v.throttle_past_next_share,
    v.brake_before_prev_share,
    COALESCE(v.linked_corner_share >= 0.5, FALSE) AS linked_corner_cell_flag,
    CASE
        WHEN COALESCE(v.n_laps_measured, 0) >= 5 THEN NULL
        WHEN COALESCE(r.n_laps_raw, 0) = 0 THEN 'no_measured_clean_lap'
        WHEN r.n_laps_raw >= 5 THEN 'too_few_valid_laps'
        ELSE 'too_few_laps'
    END AS null_reason
FROM corners AS c
LEFT JOIN raw_agg AS r ON c.race_id = r.race_id AND c.corner_name = r.corner_name
LEFT JOIN valid_agg AS v ON c.race_id = v.race_id AND c.corner_name = v.corner_name
LEFT JOIN excl AS x ON c.race_id = x.race_id AND c.corner_name = x.corner_name
ORDER BY c.race_year, c.race_id, c.apex_distance_m
