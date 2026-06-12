-- Transform v0.2 Fix 1: centring identity for constructor deg slopes.
--
-- The unshrunk deviation (deg_slope_raw_s_per_lap - field_mean_slope_s_per_lap)
-- must have a precision-weighted mean of exactly 0 within each (race_year,
-- compound) over qualifying cells that is what "deviation from the field-average
-- compound curve" means. If this drifts, the centring constant and the
-- recombination interpretation are broken.
--
-- Tolerance: 1e-9 s/lap (pure floating-point identity).
-- Low-sample cells are excluded: they don't enter the field mean.

WITH qualifying AS (
    SELECT
        race_year,
        compound,
        deg_slope_raw_s_per_lap - field_mean_slope_s_per_lap    AS dev,
        1.0 / (deg_slope_se_s_per_lap * deg_slope_se_s_per_lap) AS w
    FROM {{ ref('int_constructor_deg_sensitivity') }}
    WHERE is_low_sample = FALSE
)

SELECT
    race_year,
    compound,
    SUM(w * dev) / SUM(w) AS weighted_mean_dev
FROM qualifying
GROUP BY race_year, compound
HAVING ABS(SUM(w * dev) / SUM(w)) > 1e-9
