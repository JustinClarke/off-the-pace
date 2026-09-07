# Week 1 — Platform & Delta Lake Foundations 🏗️

**Theme:** get the workspace live and learn how Databricks *stores* and *names* data.
**Exam domains:** Platform basics (6%) + the Delta/relational-entity base of Transform (22%).
**Friday deliverable:** Free Edition workspace live · `off-the-pace-spark` repo skeleton · 12 `stg_*` models ported · the parity harness **green on all 12**.

You already write Python and SQL, so almost nothing this week is about *logic* — it's about the
**platform**: where data lives (catalog → schema → table → Volume), how Delta stores it, and how you
*prove* a Spark table equals its dbt-duckdb twin. Get the boring foundation solid now and Weeks 2–6 fly.

---

## The 5-day rhythm (same every week — that's the point)

| Day | Vibe | Split | This week |
|---|---|---|---|
| [Mon](./monday.md) | Learn the *why* | 70% learn / 30% lab | Platform + lakehouse mental model |
| [Tue](./tuesday.md) | Learn by recreating | 50% learn / 50% build | Delta Lake + relational entities |
| [Wed](./wednesday.md) | Build | 90% project | Port the 12 `stg_*` models |
| [Thu](./thursday.md) | Build + make it shippable | 90% project | The parity harness, green on 12 |
| [Fri](./friday.md) | Review + exam reps + ship | 40 / 30 / 30 | Self-check, practice Qs, commit |

> 🧠 **ADHD note, read once:** every day file has the same shape — a **15-min start-here** to get you
> moving, a **🎯 if-you-only-do-one-thing** for low-fuel days, timeboxes so you don't spiral, and a
> **🏁 done-when** so you get a clean *stop*. You don't have to read every doc. Pick one, build, move on.

---

## Momentum tracker (tick these — it's the dopamine)

- [ ] Mon — workspace live, repo skeleton pushed
- [ ] Tue — Delta probe table created + time-travelled
- [ ] Wed — 12 `stg_*` views built
- [ ] Thu — parity harness green on 12/12 🟢
- [ ] Fri — self-check done, practice Qs logged, branch pushed

**This week is "won" when:** the cheapest layer (staging) is parity-clean. That proves the engine-swap
is invisible — the safety net the whole rebuild hangs from. Everything hard comes later, on a proven harness.
