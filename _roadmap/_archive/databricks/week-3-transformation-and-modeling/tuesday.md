# Week 3 · Tuesday — Windows + MERGE → port the dimensions

⏱️ **~3 hrs** · 50% learn / 50% build · **Domain:** Transform (22%)
🎯 **One-liner:** master window functions and Delta `MERGE` (both exam favourites), then port the 4
`dim_*` tables as your first real build.

> ▶️ **Start here (first 15 min):** write one window query against `stg_laps` —
> `row_number() OVER (PARTITION BY driver, stint ORDER BY lap)`. Your residual/skill logic is *built* on
> this; warming it up now pays off all week.

---

## 🎯 If you only do one thing today
Port the **4 `dim_*` tables** (+ their seeds) and get them parity-green. Small, finite, satisfying — and
they're the broadcast targets every intermediate joins to.

## Parts (tick as you go)

### ⬜ Part 1 — Windows & aggregations · ~45 min  *(learn)*
- [ ] Docs: **"Window functions"**, **"Aggregate functions"**.
- [ ] Drill until automatic: `OVER (PARTITION BY … ORDER BY …)`, `row_number`/`rank`, `lag`/`lead`,
      running sums, `groupBy().agg()`. **Windowing shows up heavily on the exam.**

### ⬜ Part 2 — Delta MERGE · ~30 min  *(learn)*
- [ ] Docs: **"Upsert into a Delta table using MERGE"**. Know the shape
      `MERGE INTO … WHEN MATCHED UPDATE … WHEN NOT MATCHED INSERT` and *why* it beats a full rebuild for incremental gold.

### ⬜ Part 3 — Port the 4 dimensions · ~1.5 hrs  *(build)*
Materialise as Delta **tables** (small → broadcast targets):
- [ ] First port the **seeds** they consume (`circuit_reference`, `compound_cliff_params`) as small managed Delta tables.
- [ ] `dim_circuits`   - [ ] `dim_compounds_season`   - [ ] `dim_constructors`   - [ ] `dim_drivers`
- [ ] Parity-check each → green.

## 🐍 You already know this
Window functions are **standard SQL** — `OVER (PARTITION BY …)` is the same in DuckDB and Spark. `MERGE`
is the SQL `MERGE`/upsert you may already know. The only new wrapper is that the target is a **Delta**
table, so the merge is ACID and time-travellable for free.

## 📚 Resources (pick ONE)
- Re-read your *own* dbt `dim_*` models side-by-side with the Spark version. Best "tutorial" there is.

## 🏁 Done when
- [ ] Window verbs are automatic (lag/lead/row_number without looking them up).
- [ ] 4 `dim_*` + their seeds ported and **parity-green**.

## 🅿️ Park it
Tomorrow = the 34 intermediates, by cluster. Open [wednesday.md](./wednesday.md) and pick your **first
cluster** now (suggest: Lap state — the gentlest) so tomorrow starts with zero decisions.

## Notes & gotchas
-
