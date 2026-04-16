# Models

Four layers, each in its own subdirectory. The DAG flows top to bottom.

| Layer | Dir | Materialisation | Purpose |
|---|---|---|---|
| Staging | `staging/` | view | Bronze → clean column names, type casts, validity flags (9 views) |
| Reference | `reference/` | table | Seed-backed dimensions: circuits, compounds, drivers, constructors (4 tables) |
| Intermediate | `intermediate/` | table / view | Physics layers 03–05: fuel, air state, thermal proxy, compound cliff, field pace, track evolution, constructor pace, synthetic teammate, event corrections, residual decomposition, anomaly flags (36 tables) |
| Marts | `marts/` | table | Feature tables for ML and analytics: `fct_driver_skill_features`, `fct_cliff_prediction_features`, `fct_lap_residuals`, `fct_telemetry_deltas`, `fct_stint_features`, `fct_racecraft`, `fct_ghost_car_pace`, `fct_ghost_race_finish`, `dim_events` (9 tables) |

See [../README.md](../README.md) for the full model DAG and running instructions.
