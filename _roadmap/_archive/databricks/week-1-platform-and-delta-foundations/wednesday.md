# Week 1 · Wednesday — Port the 12 staging models

⏱️ **~3 hrs** · 90% build · **Build day** 🔨
🎯 **One-liner:** re-express the 12 `stg_*` models as Spark SQL **views** — the cheapest, lowest-risk slice.

> ▶️ **Start here (first 15 min):** open the dbt source `stg_circuit_info.sql` from the off-the-pace
> repo and just *read* it. It's a thin cast/rename. You're translating, not inventing — the scary part
> is already solved.

---

## 🎯 If you only do one thing today
Port **one** `stg_*` model end-to-end as a Spark view. One complete loop proves the pattern; the other 11
are copy-paste-adapt.

## Parts (tick as you go)

### ⬜ Part 1 — Port the 12 staging views · ~2 hrs  *(build)*
Each `stg_*` is a thin bronze→silver read (cast/rename, no shuffle). Create each as a Spark SQL **view**
in the `staging` schema. Tick them off — 12 little wins:

- [ ] `stg_circuit_info`   - [ ] `stg_events`   - [ ] `stg_laps`   - [ ] `stg_laps_qualifying`
- [ ] `stg_pits`   - [ ] `stg_results`   - [ ] `stg_sector_times`   - [ ] `stg_session_status`
- [ ] `stg_telemetry`   - [ ] `stg_track_status`   - [ ] `stg_tyre_allocations`   - [ ] `stg_weather`

> ⚠️ **Carry the known gotcha:** `stg_laps.race_id` is **NUMERIC, not the slug** (from repo memory). Get
> the type right *here* or every downstream join in Week 3 silently breaks. This is the kind of bug that
> eats an afternoon — pin it now.

### ⬜ Part 2 — Sanity check · ~30 min  *(build)*
- [ ] For 3–4 ported views, eyeball `SELECT COUNT(*)` against the dbt-duckdb table. Rough match = good
      enough for now; the real proof is tomorrow's harness.

## 🐍 You already know this
This is **SQL → Spark SQL**, ~1:1. Spark SQL is ANSI-ish; the dialect differences are tiny (functions
like `cast`, `coalesce`, `when` all exist). The dbt `{{ ref() }}` Jinja becomes a plain
`catalog.schema.table` reference. If you can read the dbt model, you can write the Spark view.

## 📚 Resources
- None today. No videos, no tutorials. Repo open, docs closed. This is muscle memory.

## 🏁 Done when
- [ ] 12 `stg_*` views exist in `otp_spark.staging`.
- [ ] You've spot-checked a few row counts and nothing is wildly off.

## 🅿️ Park it
Tomorrow you build the **parity harness** that turns "looks right" into "proven right." Note any view you
felt unsure about — those are the ones the harness will catch first.

## Notes & gotchas
-
