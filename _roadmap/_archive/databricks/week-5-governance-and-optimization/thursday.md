# Week 5 · Thursday — Replay the float-drift incident 🕵️

⏱️ **~3 hrs** · 90% build + make-it-shippable 🔧
🎯 **One-liner:** the detective day — read a Spark query plan, find where non-determinism hides, and write
the headline artefact explaining the drift in Spark terms.

> ▶️ **Start here (first 15 min):** re-read the original incident:
> [`snapshot_model_hashes.py`](../../../transform/scripts/snapshot_model_hashes.py) +
> [`profiles.yml`](../../../transform/profiles/profiles.yml). The fix was pinning DuckDB's **intra-query**
> thread count (`settings: threads: 1`) — because **non-associative float aggregation reordered across
> threads** changed a sum at ~1e-14. That's the mystery you're re-solving in Spark.

---

## 🎯 If you only do one thing today
Write `notebooks/05_determinism.md`. This single artefact is the project's marquee deliverable *and* the
exact scenario-question shape the exam loves. It's the best portfolio + exam two-for-one of the whole plan.

## Parts (tick as you go)

### ⬜ Part 1 — Read the query plan · ~1 hr  *(learn + investigate)*
- [ ] Docs: **"Spark UI"**, **"Adaptive query execution"**, **"Diagnose query performance"**.
- [ ] In the Spark UI, find a model whose plan has a wide **shuffle** before a float aggregation (the
      residual sums are prime suspects). Spot the shuffle stage; reason about **partition-order non-determinism**.

### ⬜ Part 2 — Write the determinism note · ~1.5 hrs  *(build — the headline artefact)*
- [ ] `notebooks/05_determinism.md` answering:
  - Does Delta's deterministic write path + AQE make this drift **disappear** in Spark, or does it resurface
    as partition-order float reordering?
  - What's the **Spark equivalent of `threads:1`**? (stable sort before aggregate, fixed partitioning,
    `spark.sql.shuffle.partitions`, etc.)
- [ ] This is the §3-Troubleshooting deliverable from [`SPARK_REBUILD_PLAN.md`](../../_wip/SPARK_REBUILD_PLAN.md).

### ⬜ Part 3 — Connect it to the exam · ~30 min  *(production engineering)*
- [ ] Note how this maps to exam concepts: shuffle, partition skew, AQE, caching. You now have a *story* for
      every one of those terms — stories stick far better than definitions.

## 🐍 You already know this
You **lived** this bug already (it's in your repo's history). You're not learning determinism from a
textbook — you're explaining a war story you fought and won, now in Spark's vocabulary. That's why it'll be
unforgettable in the exam: it's *yours*.

## 🏁 Done when
- [ ] `05_determinism.md` written and committed.
- [ ] You can explain, out loud, why identical logic drifts and two Spark fixes that make writes deterministic.

## 🅿️ Park it
Tomorrow = reps + ship. You've now built something genuinely impressive — a documented determinism analysis
most engineers can't write. That's interview gold *and* exam fluency.

## Notes & gotchas
-
