# Week 1 · Thursday — The parity harness (your safety net)

⏱️ **~3 hrs** · 90% build + make-it-shippable 🔧
🎯 **One-liner:** write the one tool that proves a Spark table equals its dbt-duckdb twin — then get it
**green on all 12 staging views**.

> ▶️ **Start here (first 15 min):** open [`snapshot_model_hashes.py`](../../../transform/scripts/snapshot_model_hashes.py)
> from the original repo. That's the oracle you're re-creating. Skim how it normalises before hashing —
> that's the whole trick.

---

## 🎯 If you only do one thing today
Get `src/parity.py` **green on the 12 staging views**. Green here = the harness is trusted = the rest of
the rebuild is safe. This is the most important single artefact of the week.

## Parts (tick as you go)

### ⬜ Part 1 — Write `src/parity.py` · ~1.5 hrs  *(build)*
Given a model name, the harness should:
- [ ] Read the committed dbt-duckdb parquet baseline (`../off-the-pace/data/**`) and the Spark output.
- [ ] **Normalise both** the same way: sort by PK, round floats to N dp, **drop wall-clock columns**
      (e.g. `fit_timestamp`).
- [ ] Assert column set, row count, and value equality.
- [ ] On mismatch, print the **first N differing rows** so you can debug fast.

> 🧠 **Why the rounding/sorting matters:** a naive row-hash can false-positive because float aggregation
> reorders across partitions and changes a sum at ~1e-14. You'll formally replay this exact incident in
> Week 5 — for now, just round + sort and it disappears.

### ⬜ Part 2 — Go green on 12 · ~45 min  *(build)*
- [ ] Run `parity.py` against all 12 `stg_*` views. Fix until **12/12 green** 🟢.

### ⬜ Part 3 — Make it shippable · ~30 min  *(production engineering)*
Ask the Thursday questions:
- [ ] Is each view in the **right schema** (`staging`)?  Is `parity.py` committed to `src/`?
- [ ] Does the repo README link the contract? Is the run reproducible from a clean checkout?

## 🐍 You already know this
This is just a **diff with tolerance** — the same shape as a pandas `assert_frame_equal` or a pytest
fixture comparison. Nothing Spark-exotic. If you've written a test that compares two DataFrames, you've
written 80% of this already.

## 🏁 Done when
- [ ] `parity.py` exists, is committed, and reports **12/12 green**.
- [ ] You could hand the repo to someone and they'd reproduce the green run.

## 🅿️ Park it
Tomorrow is review + exam reps + ship. You're *ahead* if the harness is green — Friday is a victory lap.

## Notes & gotchas
-
