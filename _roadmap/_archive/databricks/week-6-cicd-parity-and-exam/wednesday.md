# Week 6 · Wednesday — The full parity cutover 🎯

⏱️ **~3 hrs** · 90% build · **Build day (the project's finish line)** 🔨
🎯 **One-liner:** run the full-corpus build, parity-check **all 60 models**, and triage every diff.

> ▶️ **Start here (first 15 min):** kick off the full-corpus build (all seasons — the one big batch Free
> Edition can do end-to-end). It runs while you set up the parity triage. Let the machine work.

---

## 🎯 If you only do one thing today
Run `src/parity.py` across **all 60 models** and triage the diffs into *intended* vs *unintended*. That
triage **is** the cutover decision — it's the whole point the rebuild existed to reach.

## Parts (tick as you go)

### ⬜ Part 1 — Full build + parity · ~1.25 hrs  *(build)*
- [ ] Run the full-corpus build (all seasons).
- [ ] Run `src/parity.py` across **all 60 models**.

### ⬜ Part 2 — Triage every diff · ~1.25 hrs  *(investigate)*
- [ ] **Intended changes** (where the rebuild deliberately fixes a data-layer issue) → document the diff and
      *expect* it. These are the "where we went wrong" wins the project exists to find.
- [ ] **Unintended diffs** on models you didn't mean to change → fix until clean (this is the Week-5
      float-determinism work paying off — apply your `05_determinism.md` fixes).

### ⬜ Part 3 — ML, only if needed · ~30 min  *(build)*
- [ ] **Only if** feature distributions shifted: retrain via existing `ml/` scripts (a v4→v5 bump, same
      pattern as the manifest history) — **no ML code rewrite**, per the contract.
- [ ] Point the app's CDN publish at Spark-produced parquet **only after parity is green**. Until then,
      dbt-duckdb stays authoritative. **App + ML never changed — that's the proof.**

## 🐍 You already know this
This is the same parity harness from Week 1, now run at full scale. No new skill — just the disciplined
finish: prove equivalence *before* anything downstream switches engines. You built the safety net in Week
1 precisely so today is calm.

## 🏁 Done when
- [ ] 60/60 models parity-triaged: clean, or diff documented as **intended**.
- [ ] ML retrained only if features shifted; app + ML code untouched.

## 🅿️ Park it
**Build's done.** From here it's pure exam prep. Tomorrow = full revision; Friday = exam. Take a breath —
you rebuilt a production-style warehouse on a new platform. That's the hard part, finished.

## Notes & gotchas
-
