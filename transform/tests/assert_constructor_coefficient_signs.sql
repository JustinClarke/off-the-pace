-- Initial transform release medium priority: championship top-3 constructors must have
-- constructor_structural_pace_s < 0 (faster than field average) at 95% CI.
--
-- Placeholder until the pyfixest HDFE model ships: returns no rows unconditionally.
-- Once int_constructor_structural_pace.py produces real CIs from CRV1-clustered FEs,
-- replace SELECT 1 WHERE FALSE with the actual sign check below.
--
-- Real check (activate after pyfixest):
--   SELECT race_year, constructor_id, constructor_structural_pace_ci_high_s
--   FROM {{ ref('int_constructor_structural_pace') }}
--   WHERE constructor_id IN (
--       SELECT constructor_id FROM {{ ref('dim_constructor_championship') }}
--       WHERE season_rank <= 3
--   )
--   AND constructor_structural_pace_ci_high_s > 0   -- upper CI still positive = cannot reject α>0

SELECT 1 WHERE FALSE
