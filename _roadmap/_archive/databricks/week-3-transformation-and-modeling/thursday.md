# Week 3 · Thursday — The 10 marts → contract paths

⏱️ **~3 hrs** · 90% build + make-it-shippable 🔧
🎯 **One-liner:** build the 10 gold marts, write them to the **exact export paths the app/ML expect**, and
get **all 10 parity-green**. Green here = the rebuild is functionally complete.

> ▶️ **Start here (first 15 min):** open the contract in
> [`SPARK_REBUILD_PLAN.md` §1](../../_wip/SPARK_REBUILD_PLAN.md). The four export paths are sacred — the
> whole "app never changed" proof hinges on writing the same paths/types. Re-read them before building.

---

## 🎯 If you only do one thing today
Build + parity-green the marts the app actually reads, and **export them to the contract paths**. Even a
subset proves the cutover works end-to-end.

## Parts (tick as you go)

### ⬜ Part 1 — Build the 10 marts · ~1.5 hrs  *(build)*
Materialise each as a Delta **table** (matches dbt `marts: +materialized: table`):
- [ ] `dim_events` (+ `data/marts/`)   - [ ] `fct_cliff_prediction_features`   - [ ] `fct_driver_skill_features`
- [ ] `fct_ghost_car_pace`   - [ ] `fct_ghost_race_finish`   - [ ] `fct_lap_residuals`
- [ ] `fct_stint_features`   - [ ] `fct_telemetry_deltas`   - [ ] `mart_corner_skill_driver`
- [ ] `mart_degradation_history_envelope`

### ⬜ Part 2 — Practise the incremental pattern · ~30 min  *(build)*
- [ ] For **one** fact, implement the refresh as a **`MERGE`** keyed on its PK — even though the project
      rebuilds fully today. The exam loves MERGE; do it once for real.

### ⬜ Part 3 — Export + parity + ship · ~1 hr  *(production engineering)*
- [ ] Write the parquet exports to the contract paths
      (`data/dimensions|facts|intermediates|marts/`) so app/ML stay untouched.
- [ ] Parity-check **all 10** → green 🟢.
- [ ] Document each model's materialization choice in `notebooks/00_architecture.md` (view vs table, and why).

## 🐍 You already know this
A "mart" is just a final `SELECT` that joins your intermediates — the same gold-layer SQL you wrote in
dbt. The new bits: it lands as a **Delta table**, and you also **write parquet to a fixed path** so the
downstream app reads it unchanged. That export step is plain `df.write.parquet(path)`.

## 🏁 Done when
- [ ] 10 marts built, exported to contract paths, **all parity-green**.
- [ ] One mart refreshed via `MERGE`.  → **Rebuild is functionally complete.** 🎉

## 🅿️ Park it
If any intermediate is still red, the dependent mart will fail parity — note the chain. Tomorrow is reps +
ship, then Week 4 *productionizes* all this. The hard part is behind you.

## Notes & gotchas
-
