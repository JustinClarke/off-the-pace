-- T35 (F45, WI-14b). An era offset may only be applied if it is
-- statistically real, and it must never widen or invert the between-era gap
-- it claims to remove.
--
-- The rating is teammate-relative (F40), and a change of car era moves both
-- teammates alike, so the natural reference for any "era step" is the gap in
-- the field-mean rating across the boundary: mean(pre) - mean(post). F45:
-- the old bridge-driver offset (-0.1153 s, t = -1.5, applied with no
-- significance gate) moved that gap from -0.044 s to +0.071 s -- larger, and
-- of the opposite sign. WI-14b dropped the offset (era_adjusted_rating =
-- shrunk_residual_s); this test keeps it dropped unless a gated estimate
-- replaces it.
--
-- Fails with one row per broken rule:
--   offset_applied_ungated  some row's era_adjusted_rating differs from its
--                           shrunk_residual_s while the published bridge
--                           shift has |t| < 2 (or no SE)
--   offset_widens_gap       |gap after| > |gap before|
--   offset_inverts_gap      gap before and gap after have opposite signs
-- Passes vacuously when one side of the boundary has no rows (CI fixtures).
{{ config(severity='error') }}

WITH rated AS (
    SELECT
        season < {{ var('era_boundary', 2022) }} AS is_pre_era,
        shrunk_residual_s,
        era_adjusted_rating,
        era_adjusted_rating - shrunk_residual_s AS applied_offset_s,
        era_shift_global_s / NULLIF(era_shift_se_s, 0) AS shift_t
    FROM {{ ref('int_era_normalized_driver_rating') }}
    WHERE era_adjusted_rating IS NOT NULL
),

gaps AS (
    SELECT
        AVG(shrunk_residual_s) FILTER (WHERE is_pre_era)
        - AVG(shrunk_residual_s) FILTER (WHERE NOT is_pre_era) AS gap_before_s,
        AVG(era_adjusted_rating) FILTER (WHERE is_pre_era)
        - AVG(era_adjusted_rating) FILTER (WHERE NOT is_pre_era) AS gap_after_s
    FROM rated
),

applied AS (
    SELECT
        MAX(ABS(applied_offset_s)) AS max_abs_applied_offset_s,
        MAX(ABS(shift_t)) AS abs_shift_t
    FROM rated
)

SELECT
    'offset_applied_ungated' AS failure,
    max_abs_applied_offset_s AS value_s,
    abs_shift_t AS detail
FROM applied
WHERE
    max_abs_applied_offset_s > 1e-9
    AND (abs_shift_t IS NULL OR abs_shift_t < 2)

UNION ALL

SELECT
    'offset_widens_gap' AS failure,
    gap_after_s AS value_s,
    gap_before_s AS detail
FROM gaps
WHERE ABS(gap_after_s) > ABS(gap_before_s) + 1e-9

UNION ALL

SELECT
    'offset_inverts_gap' AS failure,
    gap_after_s AS value_s,
    gap_before_s AS detail
FROM gaps
WHERE gap_before_s * gap_after_s < 0 AND ABS(gap_after_s) > 1e-9
