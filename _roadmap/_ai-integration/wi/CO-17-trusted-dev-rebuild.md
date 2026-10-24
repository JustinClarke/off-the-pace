# CO-17 — Trusted full rebuild of the dev warehouse

**Status:** LANDED in the working tree 2026-10-24 (build log, item CO-17). W6 (byte-oracle re-snapshot) and W21 (dev or ci baseline) are the owner's and not done here. Build log: `status/build-log.json`.

**Group:** 1 data settled · **Depends on:** `CO-09`, `CO-15`, `CO-16`, `CO-21`, `CO-22` · **Blocker:** none. (CO-21 and CO-22 were added 2026-10-23: both change numbers this build is trusted to carry.)

**Sources:** `Makefile` (`dbt-dev-full`), `transform/dbt_project.yml`, `transform/models/`, `transform/tests/`, `transform/models/intermediate/int_lap_anomaly_flags.sql`.

---

## Why

`data/dev.duckdb` was built on 2026-10-17 from older code. On 2026-10-22 it was partly rebuilt (the session-status views, the Monaco probe). No dev number is evidence for current code (watch W3). Everything after this item reads this build: the clean test (CO-14), the retrain (CO-18), the cards (AI-01) and the freeze (AI-03).

## Method

1. Start from a clean working tree with CO-09, CO-15 and CO-16 in it, and nothing else unreviewed. Record the commit and the `git status`.
2. Before the build, snapshot the row counts per model, and keep copies of the label tables to compare against.
3. `make dbt-dev-full`: seed check, car-FE refits, full `dbt build` (models and tests).
4. The label moves, so `assert_prior_season_labels_frozen` will fail where it should. Refresh its frozen values deliberately, with a note in `dbt_project.yml` and the label-version record (see `dbt_project.yml` around line 339). Never silence a real drift.
5. `training_weight_f9` (CD1, left over from CO-03): delete it if the build stays green, or leave it with a note. Do not wire it.
6. Run the singular tests and the coefficient tests (`pytest transform/tasks/coefficients/tests`).
7. Diff against the snapshot. Every changed table must trace to CO-09, CO-15 or CO-16.
8. Refresh the CI fits fixtures if the refits changed them (watch W4). Re-snapshot the byte oracle on this build if it is clean (watch W6).

## Acceptance

- `dbt build` passes with 0 errors. The only warn is the two seeds' `fit_date` staleness checks, unless another warn is explained.
- `assert_field_pace_honest_range`, `assert_sector_aggregates_to_lap` and CO-15's two new tests pass.
- Row-count diff per model recorded. Changes are only in tables downstream of the three fixes.

## Definition of done

Build log, test counts and the diff table recorded in the log. Watch W3 clears. Do not commit; do not export to the CDN.

Step up to `opus-5` if a failure needs a ruling rather than a named fix.
