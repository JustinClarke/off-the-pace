# Week 2 · Tuesday — Auto Loader stream + schema evolution

⏱️ **~2.5 hrs** · 50% learn / 50% build · **Domain:** Ingestion (21%)
🎯 **One-liner:** stand up a real `cloudFiles` stream, then watch a new column flow in automatically.

> ▶️ **Start here (first 15 min):** copy **one** source's files into a UC Volume
> `otp_spark.bronze.landing/`. That landing zone is the whole stage for today's play.

---

## 🎯 If you only do one thing today
Get **one Auto Loader stream** writing to a bronze table, then **re-run it and watch already-ingested
files get skipped**. That "it skipped them!" moment *is* incremental detection — the core exam concept.

## Parts (tick as you go)

### ⬜ Part 1 — Write the stream · ~50 min  *(build)*
- [ ] For the largest source (`laps`/`telemetry`):
  ```python
  (spark.readStream.format("cloudFiles")
       .option("cloudFiles.format", "parquet")
       .option("cloudFiles.schemaLocation", schema_path)
       .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
       .load(landing_path)
    .writeStream.option("checkpointLocation", ckpt)
       .trigger(availableNow=True)          # batch-replay a static dir
       .toTable("otp_spark.bronze.laps"))
  ```
- [ ] Re-run it → confirm **already-ingested files are skipped** (checkpoint = incremental detection).

### ⬜ Part 2 — Schema evolution in practice · ~50 min  *(build)*
- [ ] Drop a modified file into the landing zone with **one extra column** (e.g. synthetic `tyre_pressure`).
- [ ] Re-run → watch the bronze table **grow the column automatically**.
- [ ] Drop a malformed row → watch it land in **`_rescued_data`** instead of being dropped.
- [ ] 📸 Screenshot both — classic scenario-question setups.

### ⬜ Part 3 — Lock the vocabulary · ~20 min  *(learn)*
- [ ] In notes, contrast the evolution modes: `addNewColumns` · `rescue` · `failOnNewColumns` · `none`.
- [ ] One line: what does `trigger(availableNow=True)` do, and why is this *still* a streaming query?

## 🐍 You already know this
A stream is just a **read that remembers where it left off**. The `checkpointLocation` is its bookmark;
the `schemaLocation` is its memory of the columns. If you've ever written an incremental ETL job that
tracks a high-water mark, this is the managed, bulletproof version of that idea.

## 📚 Resources (pick ONE)
- Video: search *"Databricks Auto Loader tutorial 2025"* — must show `cloudFiles.schemaLocation`. Watch, then recreate without pausing.

## 🏁 Done when
- [ ] One bronze table populated by Auto Loader; re-run skips old files.
- [ ] New column auto-added; bad row captured in `_rescued_data`; both screenshotted.

## 🅿️ Park it
Tomorrow you scale this to all the real sources. Note any source whose format/PK was awkward today.

## Notes & gotchas
-
