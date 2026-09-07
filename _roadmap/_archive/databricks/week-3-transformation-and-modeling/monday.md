# Week 3 · Monday — Spark SQL ⇄ PySpark + joins

⏱️ **~2.5 hrs** · 70% learn / 30% lab · **Domain:** Transform (22%)
🎯 **One-liner:** get fluent switching between Spark SQL and the DataFrame API, and learn when Spark
**broadcasts** a small table to avoid a shuffle.

> ▶️ **Start here (first 15 min):** take any `stg_*` view and write a trivial transform **two ways** —
> once in Spark SQL, once with `.withColumn(...)`. Run `.explain()` on both. Same plan. That equivalence
> is the whole mental model for the week.

---

## 🎯 If you only do one thing today
Prove to yourself that **SQL and the DataFrame API compile to the same plan** (`.explain()`), so you can
pick whichever reads cleanest *per model* without guilt. That confidence makes Wed/Thu twice as fast.

## Parts (tick as you go)

### ⬜ Part 1 — Spark SQL ⇄ PySpark · ~50 min  *(learn)*
- [ ] Docs: **"DataFrame API"**, **"Spark SQL language reference"**, **"Built-in functions"**.
- [ ] Practise the everyday verbs both ways: `select` / `where` / `withColumn` / `cast` / `when` / `coalesce`.

### ⬜ Part 2 — Joins & broadcast · ~40 min  *(learn)*
- [ ] Docs: **"Join hints"**, **"Adaptive query execution"** (AQE auto-broadcasts the small side).
- [ ] Notes: why broadcasting the 4 small `dim_*` tables **avoids a shuffle**; how to force/avoid it
      (`broadcast()` hint, `spark.sql.autoBroadcastJoinThreshold`).

### ⬜ Part 3 — Tiny lab · ~30 min  *(lab)*
- [ ] Join a `stg_*` fact to a small dim with a `broadcast()` hint. Open the **Spark UI** and confirm
      there's **no exchange** on the dim branch. You just read a query plan — a Week-5 skill, early.

## 🐍 You already know this
Spark SQL *is* the SQL you write — `GROUP BY`, `JOIN`, `CASE WHEN` all there. The DataFrame API is just
the **same operations as Python method chains** (`df.filter(...).withColumn(...)`), and it compiles to the
identical plan. You're not learning a new language; you're learning a second *syntax* for one you know.

## 📚 Resources (pick ONE)
- Academy → Data Engineering path → "Transform data with Spark" / ETL module.

## 🏁 Done when
- [ ] Same transform written both ways; `.explain()` confirms identical plan.
- [ ] You saw a broadcast join in the Spark UI (no shuffle on the small side).

## 🅿️ Park it
Tomorrow: windows + MERGE, then port the 4 dimension tables (your first real Week-3 build). Note which
DataFrame verbs still feel clumsy — drill those in tomorrow's recreate phase.

## Notes & gotchas
-
