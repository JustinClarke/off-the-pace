# Week 3 — Data Transformation & Modeling 🧮

**Theme:** rebuild the silver + gold logic in Spark — the heaviest build *and* the heaviest exam domain.
**Exam domain:** Transformation & Modeling (**22%** — the single biggest).
**Friday deliverable:** 4 `dim_*` + 34 `int_*` + 10 marts rebuilt in Spark, **parity-clean** against dbt-duckdb.

> 🚨 **Read this first — it's 48 models and that's a lot. Don't panic.**
> You already know the *logic* — you designed it. This week is **translation**, not invention
> (dbt SQL/Jinja → Spark SQL/PySpark). The build is **chunked into clusters** so you never face all 48 at
> once. And it's 100% fine if Wed/Thu spill into the weekend buffer — the deliverable is *parity-clean*,
> not *fast*. **If you fall behind: port a representative model per cluster, move on, mop up later.**

---

## The 5-day rhythm

| Day | Vibe | Split | This week |
|---|---|---|---|
| [Mon](./monday.md) | Learn the *why* | 70% learn / 30% lab | Spark SQL ⇄ PySpark + joins/broadcast |
| [Tue](./tuesday.md) | Learn by recreating | 50% learn / 50% build | Windows + MERGE → port the 4 `dim_*` |
| [Wed](./wednesday.md) | Build | 90% project | The 34 `int_*` (by cluster) |
| [Thu](./thursday.md) | Build + make it shippable | 90% project | The 10 marts → contract paths |
| [Fri](./friday.md) | Review + exam reps + ship | 40 / 30 / 30 | Self-check, practice Qs, commit |

> 🧠 **ADHD anti-overwhelm kit:** each cluster is a self-contained win (3–7 models, one Spark pattern).
> Tick a cluster, take a real break, come back. **Don't try to hold all 34 intermediates in your head** —
> the dependency order *is* the to-do list. One cluster at a time.

---

## Momentum tracker

- [ ] Mon — same transform written in SQL *and* DataFrame API; `.explain()` shows same plan
- [ ] Tue — 4 `dim_*` + seeds ported, parity-green
- [ ] Wed — `int_*` clusters: ⬜ Lap state ⬜ Residual ⬜ Stint ⬜ Driver ⬜ Constructor ⬜ Corner ⬜ Strategy
- [ ] Thu — 10 marts built + exported to contract paths, **all parity-green** 🟢
- [ ] Fri — self-check done, practice Qs logged, branch pushed

**This week is "won" when:** all 48 are parity-clean. At that point the rebuild is **functionally
complete** — Weeks 4–6 just productionize what already works.
