# Week 2 · Friday — Review, exam reps & ship 🏁

⏱️ **~2.5 hrs** · 40% review / 30% practice Qs / 30% cleanup · **Certification day**
🎯 **One-liner:** lock in Ingestion (21% of the exam!) with closed-book recall + real practice questions.

> ▶️ **Start here (first 15 min):** close all tabs. State the **Auto Loader vs COPY INTO decision rule**
> from memory. If it's fuzzy, that's your first re-read.

---

## 🎯 If you only do one thing today
**Part 2 (practice questions).** Ingestion is the second-heaviest domain and the most *scenario-driven* —
the points are in the question reps, not in more building.

## Parts (tick as you go)

### ⬜ Part 1 — Closed-book self-check · ~40 min  *(review)*
1. Auto Loader vs `COPY INTO` — one-line decision rule + a scenario for each.
2. What does `cloudFiles.schemaLocation` store, and what breaks if two streams share one?
3. New column appears — contrast `addNewColumns` vs `failOnNewColumns` vs `rescue`.
4. Why is Auto Loader *streaming* even over a finished static directory? What does `trigger(availableNow=True)` do?
5. You re-run an ingest and get double rows — was it Auto Loader or `COPY INTO`, and what went wrong?

→ Fumble one? 10-min targeted re-read, then move on.

### ⬜ Part 2 — Practice questions · ~40 min  *(exam reps)*
- [ ] Do the **Ingestion & Loading** question set from the Academy practice exam + one third-party bank.
- [ ] Log *why* each wrong answer was wrong. Watch for the classic trap: questions that test **pre-2025
      naming** — discard those, trust the official Exam Guide PDF.

### ⬜ Part 3 — Ship · ~40 min  *(cleanup)*
- [ ] Update `notebooks/00_architecture.md` with the bronze ingestion design (which sources, which tool, why).
- [ ] Commit, push, clean branch for Week 3.

## 🏁 Done when
- [ ] 5 self-check Qs answered closed-book.
- [ ] Ingestion practice set done, wrong-answer reasons logged.
- [ ] Branch pushed; [week README](./README.md) tracker ticked. 🎉

## 🅿️ Park it / weekend buffer
**Heads-up:** Week 3 is the monster — 48 models. Rest well this weekend. Skim the
[Week 3 README](../week-3-transformation-and-modeling/README.md) Sunday evening so Monday isn't a cold start.

## Notes & gotchas
-
