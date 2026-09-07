# Week 1 · Tuesday — Delta Lake + relational entities

⏱️ **~2.5 hrs** · 50% learn / 50% build · **Domain:** Delta foundation of Transform (22%)
🎯 **One-liner:** learn what makes a Delta table *Delta* (the log, ACID, time travel), then carve out
the project's home in Unity Catalog.

> ▶️ **Start here (first 15 min):** in a notebook, run
> `CREATE TABLE probe (id INT, note STRING);` then `INSERT INTO probe VALUES (1, 'hello');`. You just
> made a Delta table — momentum unlocked.

---

## 🎯 If you only do one thing today
Run the **time-travel + schema-enforcement** lab (Part 2). It's the single densest exam payload of the day.

## Parts (tick as you go)

### ⬜ Part 1 — Learn Delta fundamentals · ~45 min  *(learn)*
- [ ] Docs: **"What is Delta Lake?"**, **"Work with Delta Lake table history"** (time travel),
      **"Update Delta Lake table schema"** (enforcement vs evolution).
- [ ] Notes: name the **3 things the `_delta_log` buys you** (ACID, time travel, schema control).

### ⬜ Part 2 — Recreate the canonical Delta lab · ~45 min  *(build)*
On your `probe` table, run each and watch what happens:
- [ ] `DESCRIBE HISTORY probe;` — see the versioned log.
- [ ] `SELECT * FROM probe VERSION AS OF 0;` — time travel.
- [ ] `INSERT INTO probe VALUES (2, 123);` with a **wrong type** — watch **schema enforcement** reject it.
- [ ] (Optional) re-run an `INSERT` with `mergeSchema` and an extra column — watch **evolution** accept it.

### ⬜ Part 3 — Build the project's UC home · ~30 min  *(build)*
- [ ] Create catalog `otp_spark` with schemas `staging`, `silver`, `gold` (and `bronze` for Week 2).
- [ ] Note the **managed vs external** distinction and **table vs view / CTAS** — and the dbt mapping:
      dbt `view` → Spark `VIEW`; dbt `table` → Delta **managed table**.

## 🐍 You already know this
`CREATE TABLE`, `CREATE VIEW`, CTAS, `INSERT` — all standard SQL you've written a hundred times. The
**only new ideas** today: (1) every write appends to a transaction log (`_delta_log`) so you can read the
table *as of* any past version, and (2) **managed** tables → Databricks owns the files (`DROP` deletes
data); **external** → you own them (`DROP` keeps data). That ownership rule is a guaranteed exam question.

## 📚 Resources (pick ONE)
- Docs: **"Create tables"** + **"Managed vs external tables"** — read these two and stop.

## 🏁 Done when
- [ ] `probe` table time-travelled and a bad-type insert rejected (you *saw* enforcement fire).
- [ ] `otp_spark` catalog + `bronze/staging/silver/gold` schemas exist.

## 🅿️ Park it
Tomorrow is a pure build day — porting 12 staging models. Leave a note: *"Wed = open dbt `stg_*`, translate to Spark SQL views."*

## Notes & gotchas
-
