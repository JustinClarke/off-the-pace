# Week 4 · Friday — Review, exam reps & ship 🏁

⏱️ **~2.5 hrs** · 40% review / 30% practice Qs / 30% cleanup · **Certification day**
🎯 **One-liner:** lock in Lakeflow (16%) with closed-book recall + practice questions, then ship.

> ▶️ **Start here (first 15 min):** close tabs. From memory: streaming table vs materialized view — which
> is incremental, and when each? If that's crisp, your Lakeflow core is solid.

---

## 🎯 If you only do one thing today
**Part 2 (practice questions).** Lakeflow is heavily *scenario*-tested (which mode, which expectation
action, how the DAG resolves). Reps beat re-reading here.

## Parts (tick as you go)

### ⬜ Part 1 — Closed-book self-check · ~40 min  *(review)*
1. Streaming table vs materialized view — when each, and which is incremental?
2. How does a declarative pipeline know the build order? What do you (not) specify?
3. Name the 3 expectation actions + a scenario for each. How do you encode `pace_delta` given float noise?
4. A Job task fails transiently — what makes it retry, and how do you stop a retry storm?
5. Triggered vs continuous for a once-per-weekend 6 GB batch — which, and why?

### ⬜ Part 2 — Practice questions · ~40 min  *(exam reps)*
- [ ] Do the **Lakeflow Jobs / pipelines** question set (Academy + one third-party bank).
- [ ] Log *why* each wrong answer was wrong. Flag anything still using old **DLT/Workflows** naming — discard those questions.

### ⬜ Part 3 — Ship · ~40 min  *(cleanup)*
- [ ] Commit the pipeline + Job definitions; note the design decisions in `notebooks/00_architecture.md`.
- [ ] Push, clean branch for Week 5.

## 🏁 Done when
- [ ] 5 self-check Qs answered closed-book.
- [ ] Lakeflow practice set done, reasons logged.
- [ ] Branch pushed; [week README](./README.md) tracker ticked. 🎉

## 🅿️ Park it / weekend buffer
**Next week you BOOK THE EXAM** (Week 5, Monday — see the readiness gate). Glance at the
[Week 5 README](../week-5-governance-and-optimization/README.md) so you walk in knowing the plan.

## Notes & gotchas
-
