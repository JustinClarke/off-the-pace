# Week 2 · Thursday — COPY INTO + re-prove parity

⏱️ **~3 hrs** · 90% build + make-it-shippable 🔧
🎯 **One-liner:** learn the *other* ingest tool (`COPY INTO`), then prove the engine swap is still
invisible by re-pointing staging at bronze and re-running parity.

> ▶️ **Start here (first 15 min):** pick one bronze source and re-ingest it with `COPY INTO` instead of
> Auto Loader. Run it twice. The row count doesn't change the second time — that's idempotency, live.

---

## 🎯 If you only do one thing today
Re-point the 12 `stg_*` views at the new `otp_spark.bronze.*` tables and get **parity green again**. That
single result proves: *bronze + staging are both clean, and downstream can't tell the engine changed.*

## Parts (tick as you go)

### ⬜ Part 1 — COPY INTO (idempotent batch) · ~45 min  *(build)*
- [ ] Re-ingest one source via `COPY INTO`; run it **twice**; confirm row count unchanged.
- [ ] Docs: **"Get started using COPY INTO"**. Write the **decision rule** in one line:
      *continuous flood of files → Auto Loader; periodic bounded batch → COPY INTO.*
- [ ] One paragraph: which fits off-the-pace's **once-per-race-weekend** batch, and why?

### ⬜ Part 2 — Re-point staging → bronze · ~1 hr  *(build)*
- [ ] Change the 12 `stg_*` views to read from `otp_spark.bronze.*` instead of raw file paths.
- [ ] Re-run `src/parity.py` on all 12 → **still 12/12 green** 🟢.

### ⬜ Part 3 — Make it shippable · ~45 min  *(production engineering)*
Thursday questions:
- [ ] Checkpoint + schema locations tidy and **one-per-source**? Any orphaned state to clean?
- [ ] Is the ingest reproducible from a clean Volume? Commit the `src/` ingest helper.

## 🐍 You already know this
`COPY INTO` is basically a **smart, idempotent `INSERT … SELECT` from files** — it remembers which files
it loaded so re-runs don't duplicate. If you've ever written a "load only new files" guard by hand,
this is that, built in and bulletproof.

## 🏁 Done when
- [ ] `COPY INTO` run twice with stable row count (idempotency seen).
- [ ] Staging re-pointed at bronze; **parity green on 12/12**.
- [ ] Decision-rule paragraph written.

## 🅿️ Park it
You've now proven the engine swap is invisible **up to silver entry**. Tomorrow = reps + ship. If parity's
green, you're ahead — Friday's a victory lap again.

## Notes & gotchas
-
