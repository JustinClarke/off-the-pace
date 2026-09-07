# Week 4 · Monday — Declarative pipelines (the auto-DAG)

⏱️ **~2.5 hrs** · 70% learn / 30% lab · **Domain:** Lakeflow (16%)
🎯 **One-liner:** learn how a declarative pipeline derives its own build order, and when to use a
**streaming table** vs a **materialized view**.

> ▶️ **Start here (first 15 min):** build a 2-cell toy — a bronze `STREAMING TABLE` and a silver
> `MATERIALIZED VIEW` that reads it. Run the pipeline and **watch it draw the DAG**. That picture is the
> whole concept.

---

## 🎯 If you only do one thing today
Stand up the **toy bronze→silver pipeline** and watch Lakeflow infer the dependency order from the table
reference. Seeing "you declare *what*, not *order*" click is the day's win.

## Parts (tick as you go)

### ⬜ Part 1 — Streaming tables vs materialized views · ~50 min  *(learn)*
- [ ] Docs: **"What is Lakeflow Declarative Pipelines?"**, **"Streaming tables"**, **"Materialized views"**.
- [ ] Notes — the rule: **streaming table** = incremental/append (good for bronze ingest);
      **materialized view** = recomputed/derived (good for silver/gold transforms).

### ⬜ Part 2 — The auto-DAG · ~30 min  *(learn)*
- [ ] Docs: **"Develop pipeline code"**. Understand: Lakeflow reads your table references and **derives the
      DAG itself** — you declare *what each table is*, never the order.

### ⬜ Part 3 — Toy pipeline lab · ~40 min  *(lab)*
- [ ] In `pipelines/`, write the 2-object toy (`CREATE OR REFRESH STREAMING TABLE` + `… MATERIALIZED VIEW`).
- [ ] Run it; open the pipeline graph; confirm the order was inferred, not written.

## 🐍 You already know this
This is dbt's `{{ ref() }}` idea, **built into the engine**. In dbt the DAG comes from refs; here the DAG
comes from table references in your pipeline code — same mental model, no separate tool. If you internalised
dbt's "declare models, let it order them," you already get Lakeflow.

## 📚 Resources (pick ONE)
- Academy → Data Engineering path → "Build data pipelines with Lakeflow Declarative Pipelines" module.

## 🏁 Done when
- [ ] Toy pipeline runs; you watched the DAG auto-derive.
- [ ] You can state ST-vs-MV in one line each.

## 🅿️ Park it
Tomorrow: data-quality **expectations** + your first multi-task **Job**. Note whether you'll express the
medallion mostly as MVs (likely yes — they're derived).

## Notes & gotchas
-
