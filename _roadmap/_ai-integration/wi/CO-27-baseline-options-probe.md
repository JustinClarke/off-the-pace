# CO-27 — Baseline probe: evidence for CD15 and CD16

**Status:** SPEC (nothing run). **Group:** 1 data settled · **Depends on:** `CO-17` (trusted rebuild) · **Blocker:** none. Raised 2026-10-23 on the owner's answer. `CD15` and `CD16` stay open; this probe is evidence for them, not blocked by them.

**Sources:** `transform/tests/assert_constructor_pace_propagates.sql`, `transform/tests/assert_residual_variance_shrinks.sql`, `.github/workflows/pipeline.yml`, `transform/scripts/snapshot_model_hashes.py`, `transform/tests/model_hashes.baseline.json`, `transform/tests/data_profile.baseline.json`.

## Question

- **CD15:** keep a baseline for the two switched-off tests (A: take it from CO-17's build so both run) or remove them (B)?
- **CD16:** re-baseline the pipeline's real-data gates (A: byte oracle and data profile, on CO-17's build, after every drift is traced to a reviewed change) or leave them off (B)?

## Method

Work on a copy of CO-17's build, never on `data/*.duckdb` or the tracked baseline files themselves.

1. CD15 A: build the baseline on the copy, run both tests, record pass/fail and what they would catch. CD15 B: list what coverage is lost.
2. CD16 A: run `snapshot_model_hashes.py --check` and the data-profile check against the copy; list each drift and the reviewed change it traces to, or mark it untraced. CD16 B: state what stays unguarded while the pipeline is off.
3. Write one plain table per decision: option, what changes, what passes or fails, risks.

## Definition of done

Both decisions have a per-option report in `_evidence/co-27-<run date>/` with a PROVENANCE.txt, linked from CD15 and CD16. Nothing tracked changed, nothing committed; the owner rules.
