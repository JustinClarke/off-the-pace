# Staging

One model per Bronze source table. All materialised as views (no storage cost).
Responsibilities: rename columns to snake_case, cast types, derive validity flags,
normalise compound labels. No joins, no aggregations.

| Model | Source | Key output columns |
|---|---|---|
| `stg_laps` | `bronze_f1.raw_laps` | `lap_id`, `lap_time_s` (ns→s), `compound`, `is_valid_lap`, `is_safety_car_lap` |
| `stg_laps_qualifying` | `bronze_f1.raw_laps_qualifying` | Qualifying-session laps (`session=Q`); same shape as `stg_laps` |
| `stg_weather` | `bronze_f1.raw_weather` | `session_time_s`, `ambient_temp_c`, `track_temp_c`, `rainfall_flag` |
| `stg_telemetry` | `bronze_f1.raw_telemetry` | `distance_m`, `speed_kph`, `throttle_pct`, `brake`, `n_gear` |
| `stg_sector_times` | derived from `stg_laps` | Unpivoted sector times  -  one row per lap × sector |
| `stg_pits` | derived from `stg_laps` | One row per pit stop; `pit_duration_s` where both in/out times recorded |
| `stg_results` | `bronze_f1.raw_results` | Classified finishing results; DNF source for the ghost-car finish model |
| `stg_track_status` | `bronze_f1.raw_track_status` | SC/VSC/yellow/red timeline; decoded `status_label`, `is_safety_car`, `is_vsc` |
| `stg_session_status` | `bronze_f1.raw_session_status` | Session start/stop/finish timeline (red-flag stoppages) |
| `stg_circuit_info` | `bronze_f1.raw_circuit_info` | Corner/marshal-sector geometry per circuit |
| `stg_events` | `seeds.raw_dim_events` | Race-level events (damage, retirement, penalties) |
| `stg_tyre_allocations` | stub  -  source not yet ingested | Empty result set; see model comment |

Source declarations (external Parquet locations) are in [src_formula1.yml](src_formula1.yml).
Column-level tests are in [schema.yml](schema.yml).

## How it connects

- **Upstream (depends on):** `data/bronze/`  -  Hive-partitioned Parquet written by `ingestion/`
- **Downstream (consumed by):** `transform/models/intermediate/`  -  physics models join staging views; `transform/models/reference/`  -  derives dims from seeds

## Layer contract

- Materialised as **views** (no storage cost; always reflects current Bronze)
- Column names must be snake_case; types must be cast (no raw strings for numeric columns)
- No joins between staging models; no aggregations; no business logic
- Every added column needs a `schema.yml` test entry

---

← [transform/README.md](../../README.md) | Part of tour stop 3: Transform
