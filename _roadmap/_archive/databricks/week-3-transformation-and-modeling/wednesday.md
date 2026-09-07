# Week 3 · Wednesday — The 34 intermediates (by cluster)

⏱️ **~3–4 hrs (may spill to buffer — that's OK)** · 90% build · **Build day** 🔨
🎯 **One-liner:** port the 34 `int_*` models in dependency order, **one cluster at a time**.

> ▶️ **Start here (first 15 min):** open the **Lap state** cluster only. Ignore the other 30 models exist.
> One cluster. That's the whole trick to not drowning today.

---

## 🎯 If you only do one thing today
Finish the **Lap state** and **Residual decomp** clusters parity-clean. Those two are the spine; the rest
build on them and can flow into Thursday/buffer.

## The clusters (tick each model — 34 little wins)
Port in order. Each cluster teaches **one** Spark pattern, so you learn as you ship.

### ⬜ Cluster 1 — Lap state · `withColumn` + `when`/`coalesce`
- [ ] `int_lap_fuel_state` - [ ] `int_lap_fuel_state_qualifying` - [ ] `int_lap_air_state`
- [ ] `int_lap_thermal_proxy` - [ ] `int_lap_anomaly_flags`

### ⬜ Cluster 2 — Residual decomp · window + arithmetic identities
- [ ] `int_lap_residual_decomposed` - [ ] `int_lap_residual_decomposed_qualifying`
- [ ] `int_sector_residual_decomposed` - [ ] `int_lap_residual_stint_detrend` - [ ] `int_qualifying_decomposed`

### ⬜ Cluster 3 — Stint / geometry · windowed running aggregates
- [ ] `int_stint_geometry` - [ ] `int_track_evolution` - [ ] `int_field_pace_curve`

### ⬜ Cluster 4 — Driver skill · group-agg + joins + era variance
- [ ] `int_driver_race_skill_loro` - [ ] `int_driver_season_ratings` - [ ] `int_era_normalized_driver_rating`
- [ ] `int_synthetic_teammate` - [ ] `int_driver_circuit_affinity` - [ ] `int_driver_circuit_era_affinity`

### ⬜ Cluster 5 — Constructor · joins + de-biased FE
- [ ] `int_constructor_structural_pace` - [ ] `int_constructor_structural_pace_qualifying`
- [ ] `int_constructor_car_fe` - [ ] `int_constructor_deg_sensitivity` - [ ] `int_circuit_x_constructor_interaction`

### ⬜ Cluster 6 — Corner / telemetry · telemetry aggregation
- [ ] `int_corner_metrics` - [ ] `int_corner_skill_residuals` - [ ] `int_lap_telemetry_aggregates`
- [ ] `int_dirty_air_tax_component` - [ ] `int_tyre_surface_vs_bulk_decoupling`

### ⬜ Cluster 7 — Strategy · hazard / strategy logic
- [ ] `int_pit_loss_circuit` - [ ] `int_pit_strategy_value` - [ ] `int_sc_hazard_history`
- [ ] `int_compound_cliff_predicted` - [ ] `int_event_corrections`

> ⚠️ **Two gotchas to carry exactly:**
> 1. The **7-term `pace_delta` identity**: `pace_delta = 6 env terms + driver_skill`. `track_unexplained_s`
>    is informational/non-additive — do **not** add it (over-counts by ≤2.5s). Parity flags drift to ~1e-14.
> 2. `int_constructor_car_fe` is fed by an **external pyfixest fit** (gitignored `data/fits/` parquet).
>    Read that fit output as a **reference input table** — don't reimplement the HDFE solve in Spark.

## 🐍 You already know this
Every model here is logic *you wrote*. You're not deriving the residual decomposition again — you're
retyping it in a near-identical SQL dialect. When stuck, open the dbt model next to the Spark one and translate line by line.

## 🏁 Done when
- [ ] At least Clusters 1–2 parity-green (ideally more). Each green cluster = a real checkpoint.

## 🅿️ Park it
**Write down which cluster you stopped on.** Tomorrow's marts depend on these, so note any int_ still red.
Falling behind is fine — port one representative model per unfinished cluster and keep moving.

## Notes & gotchas
-
