# Week 5 — Governance, Security & Optimization 🔐⚡

**Theme:** govern the data (Unity Catalog), make the big tables fast (Liquid Clustering), and replay the
famous float-drift incident in Spark terms.
**Exam domains:** Governance & Security / Unity Catalog (**15%**) + Troubleshooting, Monitoring & Optimization (**10%**) = **25% combined**.
**Friday deliverable:** gold governed in UC (grants + a row filter + a column mask) · big marts optimized
(OPTIMIZE + **Liquid Clustering**) · the drift incident **formally replayed** in `notebooks/05_determinism.md`.

> 📅 **BOOK THE EXAM THIS WEEK** (Monday) — see the **readiness gate** below. A locked date gives Week 6 a
> hard deadline, which is exactly the external structure that makes deadlines work *with* ADHD instead of against it.

---

## 🚦 Readiness gate (book the exam, but smartly)
Book your exam **on Monday** for end of Week 6 — **only if** you're scoring **≥75–80% on the official
Academy practice exam** as of this week. If you're below that, book it **1–2 weeks later** and protect the
buffer. *Book to a score, not to the calendar.* You can always sit it sooner if reps go well.

---

## The 5-day rhythm

| Day | Vibe | Split | This week |
|---|---|---|---|
| [Mon](./monday.md) | Learn the *why* | 70% learn / 30% lab | UC object model + grants · **book exam** |
| [Tue](./tuesday.md) | Learn by recreating | 50% learn / 50% build | Row filters/masks · Sharing/Federation · OPTIMIZE |
| [Wed](./wednesday.md) | Build | 90% project | Govern gold + cluster the big marts |
| [Thu](./thursday.md) | Build + make it shippable | 90% project | **Replay the float-drift incident** (headline artefact) |
| [Fri](./friday.md) | Review + exam reps + ship | 40 / 30 / 30 | Self-check, practice Qs, commit |

> 🧠 **ADHD note:** governance is "demo + explain," not a big build — **timebox it hard** or it sprawls.
> The genuinely fun day is Thursday: a real detective story (why did identical logic drift?) that's also the
> exam's favourite scenario shape. Save your best energy for Thursday.

---

## Momentum tracker

- [ ] Mon — exam booked 📅 · grants + lineage graph seen
- [ ] Tue — row filter + column mask applied; OPTIMIZE/CLUSTER BY tried on a toy
- [ ] Wed — gold governed + big marts clustered; before/after file counts compared
- [ ] Thu — `05_determinism.md` written (the headline learning artefact) 🟢
- [ ] Fri — self-check done, practice Qs logged, branch pushed
