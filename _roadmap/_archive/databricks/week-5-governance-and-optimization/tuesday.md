# Week 5 · Tuesday — Row filters/masks + the optimization toolkit

⏱️ **~2.5 hrs** · 50% learn / 50% build · **Domains:** Governance (15%) + Optimization (10%)
🎯 **One-liner:** apply a row filter + column mask, place Delta Sharing / Federation on your mental map,
and learn the 2025-preferred layout tool — **Liquid Clustering**.

> ▶️ **Start here (first 15 min):** `OPTIMIZE` one of your marts and run `DESCRIBE DETAIL` before/after to
> see `numFiles` drop. Instant, visible win — the small-files problem, solved in one command.

---

## 🎯 If you only do one thing today
Learn the **Liquid Clustering vs partitioning vs ZORDER** guidance cold. It's the single most-changed-in-2025
optimization topic and a near-guaranteed exam question.

## Parts (tick as you go)

### ⬜ Part 1 — Row filters & column masks · ~40 min  *(learn + build, timeboxed)*
- [ ] Docs: **"Filter sensitive table data using row filters and column masks"**.
- [ ] Apply a **row filter** (restrict rows to recent seasons for the read-only group) and a **column
      mask** (mask a driver identifier for non-privileged readers). off-the-pace has no real PII — this is a *learning demo*, keep it tight.

### ⬜ Part 2 — Delta Sharing & Lakehouse Federation · ~25 min  *(learn, explain-only)*
- [ ] Docs: **"What is Delta Sharing?"**, **"What is Lakehouse Federation?"**.
- [ ] Two sentences each: a realistic use case. **The exam rule:** Delta Sharing **copies/shares** a table
      cross-org; Federation **queries external sources without copying**. Know which is which.

### ⬜ Part 3 — Optimization toolkit · ~50 min  *(learn + build)*
- [ ] Docs: **"Use liquid clustering for Delta tables"**, **"Optimize data file layout"** (`OPTIMIZE`/`ZORDER`),
      **"Remove unused data files with VACUUM"**, **"Predictive optimization"**.
- [ ] Lock the modern guidance: **prefer Liquid Clustering (`CLUSTER BY`)**; reach for partitioning **only**
      on very large, low-cardinality columns; `ZORDER` is the pre-2025 answer the exam may still phrase either way.

## 🐍 You already know this
A row filter / column mask is just a **function the table runs on read** to hide rows/cells from some users
— like a `WHERE` clause and a `CASE` you don't have to remember to write. `OPTIMIZE` is file compaction
(merging many small files into few big ones); `VACUUM` is garbage collection. Familiar concepts, managed.

## 📚 Resources (pick ONE)
- A "Liquid Clustering vs ZORDER vs partitioning 2025" explainer (must be post-2025 — the guidance flipped).

## 🏁 Done when
- [ ] Row filter + column mask applied (and you can explain what each protects).
- [ ] You can state the Liquid-Clustering-first rule and when partitioning still wins.

## 🅿️ Park it
Tomorrow you govern the real gold schema + cluster the big marts for measured speedups. Note which columns
you join/filter on most (`race_id`, `driver_id`) — those are your `CLUSTER BY` keys.

## Notes & gotchas
-
