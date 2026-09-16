# Why are `fct_lap_residuals`'s caution flags always FALSE?

**Asked and traced 2026-09-16.** Prompted by the [`11b`](../work/11-parallel-surfaces.md) run,
whose first pass built a Safety Car path in a pit-strategy DP, read the caution flags from
`fct_lap_residuals`, and got a branch that **silently never fired**. The bug produced no error and
no NULL — just a model in which Safety Cars never happen.

**Answer: the columns are real, but the rows they would be TRUE on have already been filtered out
upstream. The flags survive the filter as dead constants.**

---

## The trace

| table | rows | `is_safety_car_lap` TRUE |
| :--- | ---: | ---: |
| `int_event_corrections` | 162,729 | **8,927** |
| `int_stint_geometry` | 162,729 | **8,927** |
| `int_lap_residual_decomposed` | 137,447 | **0** |
| `fct_lap_residuals` | 137,447 | **0** |

**Verified** read-only against `data/dev.duckdb`. `is_vsc_lap` (2,980 → 0) and `is_red_flag_lap`
(426 → 0) behave identically.

`int_lap_residual_decomposed` selects the flag columns through from `int_event_corrections`
([`int_lap_residual_decomposed.sql:172`](../../transform/models/intermediate/int_lap_residual_decomposed.sql#L172)),
so the *columns* are carried faithfully. But the model joins onto a green-lap pace spine, and
**25,282 rows are dropped** in the process — which is every caution lap. The projection is correct;
its input population is already green-only. `fct_lap_residuals` is a thin wrapper over it and
inherits the result.

This is consistent with the model's stated purpose: a residual decomposition of *pace* has nothing
to decompose on a lap run behind a Safety Car. The defect is not the filter. The defect is that the
filtered table still advertises three caution flags, so a consumer can read them, get `FALSE`, and
reasonably conclude no caution occurred.

## What to read instead

**`int_stint_geometry`** carries the real flags at full 162,729-row coverage. For per-circuit
caution *rates* rather than per-lap incidence, `int_sc_hazard_history` has them EB-shrunk — but
note it is keyed on `(circuit_slug, season)` and has **no lap axis** (see
[`../reference/ml_headroom.md`](../reference/ml_headroom.md) §6, corrected 2026-09-16).

## Why this is worth a note rather than a fix

Dropping the columns from `fct_lap_residuals` would be the clean fix, but they are in the ML
feature mart's published schema and the contract tests assert its shape — so it is a contract
change, not a tidy-up, and it belongs to whoever next touches that contract. Until then: **any
model that needs to know a lap was under caution must not get that from `fct_lap_residuals` or
anything derived from it**, including `mart_degradation_predictions`.

A constant-`FALSE` boolean is the worst shape for this failure: it type-checks, it joins, it never
raises, and it makes the branch that depends on it unreachable. `11b` found it only because the
stochastic arm's measured effect was implausibly close to zero.
