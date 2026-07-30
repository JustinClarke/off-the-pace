-- Check that dirty air tax is always a penalty (i.e. always positive value being subtracted, or wait - is it positive or negative?)
-- The DAG doc says: "Aero penalty inverted | Positive delta (faster in traffic) | Check sign: delta must be negative/penalty"
-- But wait! In the residual decomposition, `dirty_air_tax_s` is a component of lap_time_s.
-- "dirty_air_tax_s: per-lap seconds attributable to following another car."
-- "Additive components (all in seconds, positive = slower contribution)"
-- So if dirty_air_tax_s is POSITIVE, it means the lap is SLOWER. This is a PENALTY.
-- If dirty_air_tax_s is NEGATIVE, it means the lap is FASTER in traffic, which is inverted!
SELECT lap_id, dirty_air_tax_s
FROM {{ ref('int_dirty_air_tax_component') }}
WHERE dirty_air_tax_s < 0
