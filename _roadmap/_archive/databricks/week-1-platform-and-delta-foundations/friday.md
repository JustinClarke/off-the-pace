# Week 1 · Friday — Review, exam reps & ship 🏁

⏱️ **~2.5 hrs** · 40% review / 30% practice Qs / 30% cleanup · **Certification day**
🎯 **One-liner:** lock in the week — explain it closed-book, drill real exam questions, and ship a clean branch.

> ▶️ **Start here (first 15 min):** close every doc tab. Answer self-check Q1 below *from memory, out loud.*
> Stumbling is fine — it tells you exactly what to re-read.

---

## 🎯 If you only do one thing today
Do **Part 2 (practice questions)**. Reps on real exam-style questions are the #1 predictor of passing —
more than any amount of building. Never skip the reps.

## Parts (tick as you go)

### ⬜ Part 1 — Closed-book self-check · ~40 min  *(review)*
Answer out loud, no notes:
1. Serverless vs classic compute — which does Free Edition use, and what exam decision does that delete?
2. What 3 guarantees does the Delta transaction log give you? How do you read a table as of yesterday?
3. Managed vs external table — who owns the files, and what happens on `DROP TABLE` for each?
4. Map `fct_lap_residuals`, `int_lap_fuel_state`, `stg_laps` to bronze/silver/gold.
5. Why can a row-hash parity check fail on byte-identical logic? *(You'll fully answer this Week 5.)*

→ Any question you fumble: 10-min targeted re-read, then move on. Don't re-read everything.

### ⬜ Part 2 — Practice questions · ~40 min  *(exam reps)*
- [ ] Do the **Platform + Delta** questions from the official Academy practice exam.
- [ ] For every wrong answer, write **one line on *why* Databricks wanted the right answer** — the
      distractor pattern is the real lesson.

### ⬜ Part 3 — Ship + architecture note · ~40 min  *(cleanup)*
- [ ] Write `notebooks/00_architecture.md`: map all 60 models to bronze/silver/gold. This doubles as your
      Week 2–3 build backlog *and* exam revision.
- [ ] Commit everything, push, **start next week on a clean branch**.

## 🏁 Done when
- [ ] 5 self-check Qs answered closed-book.
- [ ] ≥1 set of practice Qs done, wrong-answer reasons logged.
- [ ] Branch pushed; momentum tracker in the [week README](./README.md) ticked. 🎉

## 🅿️ Park it / weekend buffer
Sat = optional spillover. Sun = rest. If staging parity is green, **you are exactly on schedule** —
protect the rest so Week 2's heavier ingestion week starts with fuel in the tank.

## Notes & gotchas
-
