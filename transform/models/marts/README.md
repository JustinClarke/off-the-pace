# Marts

Feature tables and dimension tables for ML and analytics. All marts are materialised as
tables. Schemas on the two primary ML inputs are enforced via dbt model contracts
(`contract: enforced: true`)  -  see [Contract policy](#contract-policy) below.

| Model | Grain | ML / analytics use |
|---|---|---|
| `fct_driver_skill_features` | driver × race | Driver-skill extraction  -  race-grain residuals, synthetic-teammate delta, constructor index |
| `fct_cliff_prediction_features` | lap | Tyre-cliff XGBoost  -  lap features + `next_lap_degradation_jump_s` target |
| `fct_lap_residuals` | lap | Analytics  -  full residual decomposition with anomaly flags |
| `fct_stint_features` | stint | Pit-strategy features  -  compound, stint length, tyre-age progression |
| `fct_telemetry_deltas` | telemetry sample | Sector-level traction and braking analysis |
| `fct_ghost_car_pace` | ego-driver × host-constructor × race × lap | Ghost Car  -  counterfactual "what-if" lap times |
| `fct_ghost_race_finish` | host-constructor × ego-driver × race | Ghost Car  -  projected finishing position with SE |
| `mart_corner_skill_driver` | race-year × driver | Equal-car driver corner-skill ranking |
| `mart_degradation_history_envelope` | circuit × era × compound × tyre-life | Degradation Simulator history overlay |
| `fct_driver_isolation_pair_lap` | lap × peer | Driver isolation tier 3: raw relative pace against each same-tyre-age peer |
| `fct_driver_isolation_lap` | lap | Driver isolation per lap, with trailing-window ratings |
| `fct_driver_isolation_stint` | stint × phase | Driver isolation per stint phase (early / mid / cliff / recovery, plus `all`) |
| `fct_driver_isolation_race` | driver × race | Driver isolation ratings rolled up per race |
| `fct_power_law_training` | race × compound hardness rank | Power-law tyre-curve training frame for `ml/src/powerlaw.py` |
| `mart_driver_season_summary` | driver × season | Season rating, rank, teammate gap and component means, shaped for plain-language explanations |
| `mart_race_driver_summary` | driver × race | Race rating, rank, teammate gap, components and result, shaped for plain-language explanations |
| `mart_metric_benchmark` | metric × season | p05 / p50 / p95, mean and sd of each decomposition component over clean laps |
| `dim_events` | event | Race event flags (damage, retirement, penalty) |

Exposures pointing at `ml/` are declared in [exposures.yml](exposures.yml).

## Contract policy

Model contracts (`contract: enforced: true`) are applied **deliberately and narrowly**, only to
marts that are a binding interface to a system outside this dbt project:

- ✅ **Contracted:** `fct_driver_skill_features` and `fct_cliff_prediction_features`. These are the
  column-exact inputs to the offline ONNX / XGBoost scoring pipeline in `ml/`. A renamed or
  retyped column silently breaks scoring parity, so the contract turns that into a hard
  `dbt build` failure at the source.
- ⬜ **Not contracted (intentional):** every other mart. These are internal analytics and
  app-feed surfaces whose columns evolve alongside the analysis. They have no cross-system
  consumer that breaks on a schema change, so enforcing a contract would add migration churn
  without buying safety. Their schemas are still documented and tested in `schema.yml`.

When a mart gains a stable external consumer (a published API, a second scoring model, a
downstream warehouse), promote it to a contract at that point  -  not pre-emptively.

Breaking a column name or type on either contracted mart fails `dbt build` with a
contract-violation error. Update `schema.yml` and coordinate with `ml/` before renaming any
contracted column.
