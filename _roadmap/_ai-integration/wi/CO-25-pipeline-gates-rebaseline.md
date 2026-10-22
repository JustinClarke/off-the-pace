# CO-25 — Pipeline real-data gates would fail on dev: re-baseline after review

**Status:** BLOCKED on `CD16`. **Group:** 1 data settled · **Depends on:** `CO-17`. Raised 2026-10-22 from the transform audit.

**Sources:** `.github/workflows/pipeline.yml`, `transform/scripts/snapshot_model_hashes.py`, `transform/tests/model_hashes.baseline.json`, `transform/tests/data_profile.baseline.json`.

## Problem

`pipeline.yml` Stage 2 runs the byte oracle (`snapshot_model_hashes.py --check`) and Stage 3 the data-profile check (`make dq-test`). On the current dev build the audit reports 11 `fct_*` models drifted on the byte oracle and 187 drifts on the data profile (counts not re-run here). The pipeline only runs when `PIPELINE_ENABLED` is set (watch W18).

Overlaps watch W6 (the CI Gate 1c byte oracle, re-snapshot on CO-17's build). This item covers both baselines on the pipeline's real-data path.

## Method (once CD16 is ruled)

1. On CO-17's reviewed build, list each drift and trace it to a reviewed change.
2. Re-snapshot both baselines only if every drift is explained.

## Definition of done

Both checks pass on CO-17's build with the new baselines; the drift list and its traces recorded. Do not commit.
