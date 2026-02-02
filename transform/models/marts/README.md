# Marts

Feature tables and dimension tables for ML and analytics. All marts are materialised as
tables. Schemas are enforced via dbt model contracts (`contract: enforced: true`) on the
two primary ML inputs.

| Model | Grain | ML / analytics use |
|---|---|---|
| `fct_driver_skill_features` | driver × race | Driver skill extraction   race-grain residuals, synthetic-teammate delta, constructor index |
| `fct_cliff_prediction_features` | lap | Tyre cliff XGBoost   lap features + `next_lap_degradation_jump_s` target |
| `fct_lap_residuals` | lap | Analytics   full residual decomposition with anomaly flags |
| `fct_telemetry_deltas` | telemetry sample | Sector-level traction and braking analysis |
| `dim_events` | event | Race event flags (damage, retirement, penalty) |

Exposures pointing at `ml/` are declared in [exposures.yml](exposures.yml).

## Contract

Breaking a column name or type on `fct_driver_skill_features` or
`fct_cliff_prediction_features` will fail `dbt build` with a contract-violation error.
Update `schema.yml` and coordinate with `ml/` before renaming any contracted column.
