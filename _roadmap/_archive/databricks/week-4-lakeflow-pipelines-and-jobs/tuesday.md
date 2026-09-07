# Week 4 · Tuesday — Expectations + a 2-task Job

⏱️ **~2.5 hrs** · 50% learn / 50% build · **Domain:** Lakeflow (16%)
🎯 **One-liner:** learn the 3 data-quality expectation actions, then build a tiny multi-task Job with a
dependency and a retry.

> ▶️ **Start here (first 15 min):** add one `EXPECT` to your toy MV from Monday with
> `ON VIOLATION DROP ROW`, feed it a bad row, and watch the row vanish from the output. Data quality, live.

---

## 🎯 If you only do one thing today
See all **three expectation actions** fire (warn / drop / fail) on the toy pipeline. That trio is a
guaranteed exam question and the whole replacement for your dbt tests.

## Parts (tick as you go)

### ⬜ Part 1 — Expectations · ~45 min  *(learn + build)*
- [ ] Docs: **"Manage data quality with pipeline expectations"**.
- [ ] On the toy MV, demonstrate each action:
  - [ ] **warn** (track only) - [ ] **drop** (`ON VIOLATION DROP ROW`) - [ ] **fail** (`ON VIOLATION FAIL UPDATE`)

### ⬜ Part 2 — Lakeflow Jobs basics · ~40 min  *(learn)*
- [ ] Docs: **"Create and run Lakeflow Jobs"**, **"Task dependencies"**, **"Retries and timeouts"**,
      **"Triggers and schedules"**.
- [ ] Notes: task types (notebook, pipeline, SQL, Python); a Job can **run a declarative pipeline as one task**.

### ⬜ Part 3 — Build a 2-task Job · ~45 min  *(build)*
- [ ] Task A → Task B with an explicit `depends_on`.
- [ ] Add a **retry** to Task A and a **cron schedule**. Run it; confirm B waits for A.

## 🐍 You already know this
Expectations are **assertions on a table**, the same idea as your 443 dbt tests — just declared *inside*
the pipeline so they run as data flows, with a choice of warn/drop/fail. A Job is a **DAG of tasks** —
think Makefile targets with `depends_on`, retries, and a cron, but managed.

## 📚 Resources (pick ONE)
- Academy → "Orchestrate workflows / Lakeflow Jobs" module.

## 🏁 Done when
- [ ] warn / drop / fail all demonstrated on the toy pipeline.
- [ ] A 2-task Job runs with a dependency + retry + schedule.

## 🅿️ Park it
Tomorrow you express the **whole medallion** as one declarative pipeline. Note which dbt tests you'll port
as expectations first (the mart PK not-nulls are easy wins).

## Notes & gotchas
-
