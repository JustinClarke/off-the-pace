# Week 5 · Friday — Review, exam reps & ship 🏁

⏱️ **~2.5 hrs** · 40% review / 30% practice Qs / 30% cleanup · **Certification day**
🎯 **One-liner:** lock in Governance (15%) + Troubleshooting/Optimization (10%) = 25% of the exam, then ship.

> ▶️ **Start here (first 15 min):** close tabs. From memory: the **privilege chain** an analyst needs to
> `SELECT` a gold table, top to bottom. If it flows, your UC core is solid.

---

## 🎯 If you only do one thing today
**Part 2 (practice questions).** This Friday covers a quarter of the exam — the reps here move the needle
more than any other single Friday.

## Parts (tick as you go)

### ⬜ Part 1 — Closed-book self-check · ~40 min  *(review)*
1. Three-level namespace — what privileges (top to bottom) must an analyst hold to `SELECT` a gold table?
2. Row filter vs column mask — what does each protect, and how is each attached?
3. Delta Sharing vs Lakehouse Federation — which copies data, which doesn't?
4. Liquid Clustering vs partitioning vs ZORDER — current guidance, and when does partitioning still win?
5. A float aggregate drifts run-to-run with identical logic — diagnose in Spark terms + two fixes.

### ⬜ Part 2 — Practice questions · ~40 min  *(exam reps)*
- [ ] Do **both** the Governance and the Troubleshooting/Optimization question sets (Academy + third-party).
- [ ] Log *why* each wrong answer was wrong. Watch for `ZORDER`-vs-Liquid-Clustering phrasing traps.

### ⬜ Part 3 — Ship · ~40 min  *(cleanup)*
- [ ] Commit governance config, optimization changes, and `05_determinism.md`.
- [ ] Push, clean branch for Week 6 (the final week).

## 🏁 Done when
- [ ] 5 self-check Qs answered closed-book.
- [ ] Both practice sets done, reasons logged.
- [ ] Branch pushed; [week README](./README.md) tracker ticked. 🎉

## 🅿️ Park it / weekend buffer
**Final week next.** It's half ship (DAB + parity cutover), half revise, and ends with **the exam itself**.
Glance at the [Week 6 README](../week-6-cicd-parity-and-exam/README.md) so the run-in is calm, not frantic.

## Notes & gotchas
-
