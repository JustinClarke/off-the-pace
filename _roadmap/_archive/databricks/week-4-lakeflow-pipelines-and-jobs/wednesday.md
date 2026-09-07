# Week 4 · Wednesday — The medallion as a declarative pipeline

⏱️ **~3 hrs** · 90% build · **Build day** 🔨
🎯 **One-liner:** express the full bronze→silver→gold graph as **one** Lakeflow Declarative Pipeline and
let it resolve the order.

> ▶️ **Start here (first 15 min):** open `pipelines/` and convert just the **bronze** layer to
> `STREAMING TABLE`s (reusing Week 2's Auto Loader reads). One layer first; momentum from there.

---

## 🎯 If you only do one thing today
Get bronze + silver expressed declaratively and **running as one pipeline** — even if gold lands tomorrow.
Seeing 40+ tables build in inferred order is the payoff.

## Parts (tick as you go)

### ⬜ Part 1 — Bronze as streaming tables · ~45 min  *(build)*
- [ ] Convert the Week-2 Auto Loader ingests into `CREATE OR REFRESH STREAMING TABLE` definitions.

### ⬜ Part 2 — Silver as materialized views · ~1.5 hrs  *(build)*
- [ ] Express the 12 `stg_*` + 34 `int_*` as **materialized views** (derived, recomputed).
- [ ] Reference upstream tables by name — **don't** specify order anywhere.

### ⬜ Part 3 — Gold + delete the manual sequencing · ~45 min  *(build)*
- [ ] Express the 14 gold (`dim_*` + `fct_*`/`mart_*`) as MVs / streaming tables to the contract.
- [ ] **Delete every line of manual ordering** — run the pipeline and watch Lakeflow infer the DAG.

## 🐍 You already know this
You're not rewriting model logic — you're **wrapping the Week-3 SQL** in `CREATE OR REFRESH MATERIALIZED
VIEW` and deleting the orchestration you used to do by hand. The SQL bodies are the same; only the
*declaration* around them changes.

## 📚 Resources
- None. `pipelines/` open, docs closed.

## 🏁 Done when
- [ ] Bronze + silver (ideally + gold) run as one declarative pipeline with an auto-derived DAG.
- [ ] Zero manual sequencing remains.

## 🅿️ Park it
Tomorrow: add expectations (your dbt tests, ported) + rebuild the 7-stage CI DAG as a Job. Note any model
that didn't slot cleanly into ST/MV — that's a real exam-relevant edge case to understand.

## Notes & gotchas
-
