# Is tyre age measured, or reconstructed?

**Asked and traced 2026-09-07.** Prompted by a direct question: does the model get explicit tyre
life from the data, or is it inferring it? Relevant because
[`../research/R3-competing-risks.md`](../research/R3-competing-risks.md) argues the stint-life
model is mis-targeted, and the first thing to rule out is that it is simply mis-fed.

**Answer: measured, passed through untouched, and of high quality. The input is not the problem.**

---

## The provenance chain — three layers, zero arithmetic

| layer | what happens |
| :--- | :--- |
| source | `src_formula1.yml:52` declares FastF1's `TyreLife` — *"Laps completed on the current tyre set"* |
| staging | `stg_laps.sql:35` — `CAST(tyrelife AS INTEGER) AS tyre_life`. A cast and a rename. |
| intermediate | `int_stint_geometry.sql:65` — `tyre_life AS age_in_stint`. A rename. |
| model | `age_in_stint` enters `FEATURE_GROUPS["stint_position"]` directly. |

**Verified** by grepping every occurrence of `tyre_life` / `tyrelife` / `TyreLife` across
`transform/models`, `transform/macros` and `ml/src`. There is **no `COALESCE`, no imputation, no
back-fill, no reconstruction and no derivation** anywhere in the chain. The value the model sees
is the value the timing feed emitted, which is the value the broadcast graphic renders.

## Quality, measured

Read-only against `data/dev.duckdb`, `int_stint_geometry` (n = 162,729 lap rows, 8,333 stints).

**Verified — completeness.** 343 NULL `age_in_stint` rows, **0.21%**.

**Verified — the counter is flawless.** Stepping `age_in_stint` lap-to-lap within each stint:

| step | n | share |
| :--- | ---: | ---: |
| **+1** | **154,378** | **94.868%** |
| (first lap of stint — no predecessor) | 8,351 | 5.132% |

**Every single within-stint transition is exactly +1. There are no other values.** No jumps, no
mid-stint resets, no gaps. This is a well-formed counter, not a noisy channel.

**Verified — it correctly carries used rubber.** How each of the 8,333 stints opens:

| opening `age_in_stint` | n |
| :--- | ---: |
| 1 — a fresh set | 5,871 |
| > 1 — a used / scrubbed set | 2,137 |
| NULL | 325 |

**This is the proof that it is not computed locally.** A pipeline deriving tyre age as "laps since
the last pit stop" would be **wrong on 2,137 stints**, because a set that ran three laps in Q2
starts the race three laps old. The source knows that; a derivation would not. The header at
`int_stint_geometry.sql:3` already says so — *"age_in_stint uses tyre_life (may exceed lap_in_stint
if set used in qualifying)"* — and the data bears it out.

## The one loose end

**Verified.** 325 of the 343 NULLs (94.8%) sit on **lap 1 of a stint**. That is a pattern, not
random scatter — something about the first lap of a stint occasionally arrives without a tyre-life
reading. Small enough to ignore for now; large enough that it should be explained rather than
assumed benign, since lap 1 of a stint is exactly where `starting_tyre_age_laps` is derived.

## Why this matters for R3

It cleanly separates two quantities that a reader is likely to conflate:

- **"How many laps has this tyre done?"** — explicit in the data, essentially complete, perfectly
  well-formed, and used by the model. ✅
- **"How many laps *could* it have done?"** — **never observed, for any tyre, in any dataset.**
  The moment the car pits, the experiment ends.

The stint-life model has a flawless odometer and no warranty, and is trained as though the
odometer reading at removal *were* the warranty. That is a target problem, not a data problem, and
this note exists so nobody re-opens the data question when reading R3.
