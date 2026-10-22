# CO-23 — Two baseline-gated tests that never run

**Status:** BLOCKED on `CD15`. **Group:** 1 data settled · **Depends on:** `CO-17` (trusted rebuild). Raised 2026-10-22 from the transform audit.

**Sources:** `transform/tests/assert_constructor_pace_propagates.sql`, `transform/tests/assert_residual_variance_shrinks.sql`.

## Problem

Both tests read `data/silver/_lap_residuals_baseline/fct_lap_residuals.parquet` and compile to an empty check (`WHERE 1 = 0`) when it is absent. It is absent, so both always pass and guard nothing.

## Method (once CD15 is ruled)

- A: take the baseline from a reviewed build (CO-17's) and commit it, so both tests run.
- B: remove both tests and record why.

## Definition of done

Under A: the baseline exists, both tests run and pass on the reviewed build. Under B: tests removed, reason in the log. Do not commit.
