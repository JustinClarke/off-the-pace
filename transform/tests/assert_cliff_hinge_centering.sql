-- Transform v0.2 Fix 2: centring identity for the constructor cliff-onset hinge.
--
-- The unshrunk hinge deviation (cliff_hinge_coef_s_per_lap -
-- cliff_hinge_field_mean_s_per_lap) must have a precision-weighted mean of exactly
-- 0 within each (race_year, compound) over cliff-qualifying cells that is what
-- "deviation from the field-average post-onset degradation" means. If this drifts,
-- the onset-shift mapping and the recombination interpretation are broken.
--
-- Tolerance: 1e-9 s/lap (pure floating-point identity).
-- Low-sample cliff cells are excluded: they don't enter the field mean.

WITH qualifying AS (
    SELECT
        race_year,
        compound,
        cliff_hinge_coef_s_per_lap - cliff_hinge_field_mean_s_per_lap AS dev,
        -- SE of the hinge coef = (shift_se * severity) / ref_depth, recovered from
        -- the carried columns so the precision weight matches the field-mean weight.
        POWER(cliff_ref_depth_laps / NULLIF(cliff_onset_shift_se_laps * cliff_severity_used_s_per_lap, 0), 2) AS w
    FROM {{ ref('int_constructor_deg_sensitivity') }}
    WHERE is_low_sample_cliff = FALSE
)

SELECT
    race_year,
    compound,
    SUM(w * dev) / SUM(w) AS weighted_mean_dev
FROM qualifying
GROUP BY race_year, compound
HAVING ABS(SUM(w * dev) / SUM(w)) > 1e-9
