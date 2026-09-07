# Week 3 · Friday — Review, exam reps & ship 🏁

⏱️ **~2.5 hrs** · 40% review / 30% practice Qs / 30% cleanup · **Certification day**
🎯 **One-liner:** consolidate the heaviest domain (22%) with closed-book recall + practice questions, then ship.

> ▶️ **Start here (first 15 min):** close tabs. Write a window spec from memory that numbers each driver's
> laps within a stint in lap order. If it flows, your Week-3 core is solid.

---

## 🎯 If you only do one thing today
**Part 2 (practice questions).** This is the biggest exam domain — bank the reps. (And if Wed/Thu spilled,
it's fine to spend the rest of today mopping up models; just don't skip the questions.)

## Parts (tick as you go)

### ⬜ Part 1 — Closed-book self-check · ~40 min  *(review)*
1. Same logic in Spark SQL vs DataFrame API — do they perform differently? Why/why not?
2. Join a 50M-row fact to a 22-row `dim_drivers` — what join strategy, and how do you guarantee it?
3. Write a window spec numbering each driver's laps within a stint in lap order.
4. `MERGE` vs `INSERT OVERWRITE` for a daily-refreshed fact — trade-offs?
5. Which models can't be pure Spark SQL (external fit), and how do you ingest that dependency?

### ⬜ Part 2 — Practice questions · ~40 min  *(exam reps)*
- [ ] Do the **Transformation & Modeling** question set (Academy + one third-party bank).
- [ ] Log *why* each wrong answer was wrong. Pay attention to window-function and join-strategy questions — they're dense here.

### ⬜ Part 3 — Ship · ~40 min  *(cleanup)*
- [ ] Finalise `notebooks/00_architecture.md` materialization map.
- [ ] Commit, push, clean branch for Week 4.

## 🏁 Done when
- [ ] 5 self-check Qs answered closed-book.
- [ ] Transform practice set done, reasons logged.
- [ ] Branch pushed; [week README](./README.md) tracker ticked. 🎉

## 🅿️ Park it / weekend buffer
**If 48/48 are parity-green: the rebuild is functionally complete — that's the hardest week done.** 🏆
Use the weekend to rest or mop up stragglers. Week 4 (Lakeflow) is about *productionizing*, not new logic.

## Notes & gotchas
-
