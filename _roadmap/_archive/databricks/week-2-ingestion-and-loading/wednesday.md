# Week 2 · Wednesday — Bronze ingestion for the real sources

⏱️ **~3 hrs** · 90% build · **Build day** 🔨
🎯 **One-liner:** land a working subset of the real corpus into bronze Delta tables via Auto Loader.

> ▶️ **Start here (first 15 min):** copy a **season subset** (e.g. 2023–2024 — respects Free Edition
> quotas) into `otp_spark.bronze.landing/`. Small data = fast feedback loops = less frustration. Save the
> full corpus for the one big end-of-project run.

---

## 🎯 If you only do one thing today
Get **3 sources** landed into bronze tables. Three is enough to prove the pattern generalises; the rest
is repetition you can finish in the buffer.

## Parts (tick as you go)

### ⬜ Part 1 — Generalise the stream · ~45 min  *(build)*
- [ ] Refactor yesterday's one-off into a small reusable function: `ingest(source_name, fmt, pk)` that
      builds the `cloudFiles` reader + `toTable("otp_spark.bronze.<source>")`. Put it in `src/`.
- [ ] One `schemaLocation` + one `checkpointLocation` **per source** (never shared — sharing corrupts state).

### ⬜ Part 2 — Land the sources · ~1.5 hrs  *(build)*
Run the function across the corpus. Tick each:
- [ ] `laps`   - [ ] `results`   - [ ] `telemetry`   - [ ] `weather`   - [ ] `pits`
- [ ] `sector_times`   - [ ] `track_status`   - [ ] `session_status`   - [ ] `circuit_info`
- [ ] `tyre_allocations`   - [ ] `events`

### ⬜ Part 3 — Verify landing · ~30 min  *(build)*
- [ ] `COUNT(*)` each bronze table vs the source file count expectation. Re-run the whole batch → nothing
      re-ingests (idempotent by checkpoint).

## 🐍 You already know this
You're writing a loop over sources with a parameterised function — the same factoring you'd do in any
Python ETL script. The Databricks-specific part is just the per-source **checkpoint + schema location**
bookkeeping. Keep those paths tidy and the rest is plain engineering.

## 📚 Resources
- None. Repo + Volume open, docs closed. Build.

## 🏁 Done when
- [ ] At least 3 (ideally all 11) bronze tables populated.
- [ ] A full re-run ingests **zero** new files (idempotency proven).

## 🅿️ Park it
Tomorrow: COPY INTO (the *other* ingest tool) + re-point staging at bronze and re-prove parity. Note any
source still un-landed so you can mop up in the buffer.

## Notes & gotchas
-
