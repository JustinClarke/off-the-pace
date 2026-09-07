# Week 4 · Thursday — Expectations + the 7-stage Job DAG

⏱️ **~3 hrs** · 90% build + make-it-shippable 🔧
🎯 **One-liner:** bolt data quality onto the pipeline (expectations) and orchestrate the whole thing as a
multi-task Lakeflow Job mirroring your existing CI DAG.

> ▶️ **Start here (first 15 min):** open [`pipeline.yml`](../../../.github/workflows/pipeline.yml) — your
> existing 7-stage CI DAG. That's the blueprint you're rebuilding as a Job. Read the stage names; that's your task list.

---

## 🎯 If you only do one thing today
Port **~20 high-value expectations** onto the pipeline. You don't need all 443 dbt tests — pick the
invariants your incident history actually hit. Quality coverage where it counts.

## Parts (tick as you go)

### ⬜ Part 1 — Port expectations · ~1.25 hrs  *(build)*
Pick the highest-value invariants (~20, not 443):
- [ ] not-null / uniqueness on **every mart PK** → `ON VIOLATION FAIL UPDATE`.
- [ ] the **7-term `pace_delta` identity** on `fct_lap_residuals` as a tolerance-bounded arithmetic check
      → **warn** (it's floats, so a hard fail would be noise).
- [ ] range checks (e.g. lap-time ratios within the `outlier_exclude_ratio` band).

### ⬜ Part 2 — Rebuild the 7-stage DAG as a Job · ~1.25 hrs  *(build)*
Mirror `pipeline.yml` with explicit `depends_on`:
```
1 Ingest → 2 Transform+Tests → 3 Data Quality → 4 ML → 5 Export → 6 Publish → 7 Verify(+rollback)
```
- [ ] Stages 2–3 = the declarative pipeline (Wed + Part 1). Stage 4 = a **notebook task** running `ml/` retrain.
- [ ] Stage 5 = parquet export to contract paths. Stage 6 = publish. Stage 7 = a **verify task that fails
      the run on parity mismatch**.
- [ ] Add **retries** on the ingest + ML tasks.

### ⬜ Part 3 — Modes + the design note · ~30 min  *(production engineering)*
- [ ] Docs: **"Pipeline development and production modes"**, **"Triggered vs continuous"**.
- [ ] One paragraph in notes: for off-the-pace's once-per-weekend 6 GB batch, is **triggered** the right
      mode? Where does the original "persistent self-hosted runner" concern
      ([`SPARK_REBUILD_PLAN.md` §3](../../_wip/SPARK_REBUILD_PLAN.md)) reappear under serverless Free Edition quotas?

## 🐍 You already know this
Expectations are your dbt tests, re-homed. The Job is your `pipeline.yml` CI DAG, re-homed. You're not
designing new flow — you're **translating an orchestration you already built** from GitHub Actions to
Lakeflow Jobs. Same stages, same dependencies, new runner.

## 🏁 Done when
- [ ] ~20 expectations live (warn/drop/fail used appropriately).
- [ ] 7-stage Job runs end-to-end with dependencies + retries; verify task fails on parity mismatch.

## 🅿️ Park it
Tomorrow = reps + ship. Note your triggered-vs-continuous conclusion — it's a near-certain exam question
("once-per-weekend batch → which mode?").

## Notes & gotchas
-
