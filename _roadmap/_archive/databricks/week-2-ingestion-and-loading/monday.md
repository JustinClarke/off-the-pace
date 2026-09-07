# Week 2 · Monday — Reading files & the Auto Loader idea

⏱️ **~2.5 hrs** · 70% learn / 30% lab · **Domain:** Ingestion (21%)
🎯 **One-liner:** understand how Spark reads files (and why schema handling is the whole game), then meet Auto Loader.

> ▶️ **Start here (first 15 min):** `spark.read.parquet(<a bronze file path>)` then `.printSchema()`.
> See how Spark *inferred* types. Now you know why "schema handling" is a recurring exam theme.

---

## 🎯 If you only do one thing today
Read **one source file three ways** — `inferSchema`, a provided `StructType`, and with a rescued-data
column — and notice the trade-offs. That's the day's exam payload.

## Parts (tick as you go)

### ⬜ Part 1 — Reading files & schema handling · ~50 min  *(learn)*
- [ ] Docs: **"Read and write files"**, **"Configure schema inference and evolution in Auto Loader"**.
- [ ] Notes — the trade-off: `inferSchema` (convenient, scans data, slow/risky) vs a **provided
      `StructType`** (fast, safe, explicit). What does `rescuedDataColumn` capture? What does `mergeSchema` do on Parquet?

### ⬜ Part 2 — Meet Auto Loader · ~40 min  *(learn)*
- [ ] Docs: **"What is Auto Loader?"**, **"Auto Loader options"**.
- [ ] Notes: the **one big idea** — Auto Loader is a *streaming* read that **checkpoints which files it's
      already seen**, so re-running only picks up *new* files. Even over a static directory.

### ⬜ Part 3 — Inventory your raw corpus · ~30 min  *(lab)*
- [ ] List the raw sources under the off-the-pace repo + what [`ingestion/`](../../../ingestion/) produces:
      laps, results, telemetry, weather, pits, sector times, track/session status, circuit info, tyre
      allocations, events. For each: **file format + natural primary key**. This is your bronze backlog.

## 🐍 You already know this
You've read CSV/Parquet/JSON with pandas a hundred times. Spark adds two things: (1) reads are **lazy**
(nothing happens until an action), and (2) **schema is a first-class decision**, not an afterthought —
because at scale, inferring it every run is expensive and unsafe. That's the entire mindset shift.

## 📚 Resources (pick ONE)
- Academy → Data Engineering path → the "Load data into a lakehouse" / ingestion module.

## 🏁 Done when
- [ ] You can state, in one line each: `inferSchema` vs `StructType`, and what `rescuedDataColumn` does.
- [ ] Raw-source inventory written (format + PK per source).

## 🅿️ Park it
Tomorrow you write your first real Auto Loader stream. Note which source you'll start with (pick a big one: `laps` or `telemetry`).

## Notes & gotchas
-
