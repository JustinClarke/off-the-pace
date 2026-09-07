# Week 1 · Monday — Platform & the lakehouse mental model

⏱️ **~2.5 hrs** · 70% learn / 30% lab · **Domain:** Platform basics (6%)
🎯 **One-liner:** get a Databricks workspace live and learn how it *names* and *stores* data.

> ▶️ **Start here (first 15 min):** sign up for **Free Edition**
> (<https://docs.databricks.com/aws/en/getting-started/free-edition>), open a serverless notebook, and run
> `SELECT current_catalog(), current_schema();`. That's it — you're in. Activation beaten.

---

## 🎯 If you only do one thing today
Get the workspace live and run one query. Everything else is bonus.

## Parts (tick as you go)

### ⬜ Part 1 — The platform tour · ~50 min  *(learn)*
- [ ] Academy → *Data Engineering with Databricks* → "Get Started" / platform-overview module.
- [ ] Skim docs (search by **title**): **"What is Databricks?"**, **"Navigate the workspace"**,
      **"What is Unity Catalog?"**, **"What are Unity Catalog volumes?"**.
- [ ] One-sentence answer in your notes: *serverless vs classic compute* — which does Free Edition use,
      and what exam trivia (cluster sizing) does that delete?

### ⬜ Part 2 — The medallion mental model · ~40 min  *(learn)*
- [ ] Docs: **"Medallion lakehouse architecture"**, **"What is a Delta Lake table?"**.
- [ ] Map it to *your own project* (your unfair advantage):

  | Medallion | off-the-pace layer | Count |
  |---|---|---|
  | Bronze | raw ingested files | — |
  | Silver | `stg_*` (12) + `int_*` (34) | 46 |
  | Gold | `dim_*` (4) + `fct_*`/`mart_*`/`dim_events` (10) | 14 |

### ⬜ Part 3 — Tiny lab + repo skeleton · ~40 min  *(do)*
- [ ] Create a **Git folder** pointing at a fresh GitHub repo `off-the-pace-spark`:
  ```
  off-the-pace-spark/
    notebooks/   src/   pipelines/   resources/   README.md
  ```
- [ ] `README.md`: one line linking back to the contract in
      [`SPARK_REBUILD_PLAN.md`](../../_wip/SPARK_REBUILD_PLAN.md).

## 🐍 You already know this
A SQL `schema.table` you know — Databricks just adds **one level on top**: `catalog.schema.table`.
"Serverless" means **no infrastructure to manage** — no clusters to size, no JVM to babysit. You write
SQL/PySpark; the platform finds the compute. That's the whole mental shift today.

## 📚 Resources (pick ONE video, don't binge)
- Any post-Aug-2025 "Databricks platform tour" (15–30 min) that shows *serverless* + *Unity Catalog*.

## 🏁 Done when
- [ ] Workspace live, one query run.
- [ ] `off-the-pace-spark` skeleton committed.
- [ ] You can say bronze/silver/gold for `fct_lap_residuals`, `int_lap_fuel_state`, `stg_laps` out loud.

## 🅿️ Park it
Tomorrow you create your first Delta table. Leave a sticky note: *"Tue = Delta lab, then make the catalog."*

## Notes & gotchas
-
