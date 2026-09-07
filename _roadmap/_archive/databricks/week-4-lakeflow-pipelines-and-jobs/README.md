# Week 4 — Lakeflow Declarative Pipelines & Jobs 🔁

**Theme:** stop hand-running notebooks — let the platform resolve the DAG, enforce data quality, and orchestrate.
**Exam domain:** Working with Lakeflow Jobs / pipelines (**16%**).
**Friday deliverable:** the medallion graph as a **Lakeflow Declarative Pipeline** with **expectations** ·
the 7-stage `pipeline.yml` DAG rebuilt as a **Lakeflow Job** with dependencies, retries, and a schedule.

> 🏷️ **2025 naming (the exam tests the new names):** **DLT → Lakeflow Declarative Pipelines**;
> **Workflows → Lakeflow Jobs**. Same concepts older material calls DLT/Workflows — *answer in the new names.*

You've already got 60 working models from Week 3. This week is pure **productionizing**: declarative
dependency resolution, built-in data quality, orchestration. Less new logic, more new platform muscle.

---

## The 5-day rhythm

| Day | Vibe | Split | This week |
|---|---|---|---|
| [Mon](./monday.md) | Learn the *why* | 70% learn / 30% lab | Declarative pipelines (ST vs MV, auto-DAG) |
| [Tue](./tuesday.md) | Learn by recreating | 50% learn / 50% build | Expectations + a 2-task Job |
| [Wed](./wednesday.md) | Build | 90% project | Medallion graph as a declarative pipeline |
| [Thu](./thursday.md) | Build + make it shippable | 90% project | Expectations + the 7-stage Job DAG |
| [Fri](./friday.md) | Review + exam reps + ship | 40 / 30 / 30 | Self-check, practice Qs, commit |

> 🧠 **ADHD note:** the satisfying bit this week is **deletion** — you delete all your manual sequencing
> and the pipeline *figures out the order itself* from table references. Watch the DAG draw itself. That
> visual payoff is the hook; lean into it.

---

## Momentum tracker

- [ ] Mon — toy 2-table pipeline; watched Lakeflow draw the DAG
- [ ] Tue — `EXPECT` warn/drop/fail seen; 2-task Job with retry runs
- [ ] Wed — full medallion graph runs as one declarative pipeline
- [ ] Thu — ~20 expectations live + 7-stage Job DAG green 🟢
- [ ] Fri — self-check done, practice Qs logged, branch pushed
