# CO-14 — Stint-life clean test: rules first, then one score

**Corrected 2026-10-22:** the candidate is the **v15 configuration refit on the new label version** (CO-09 + CO-15), not the v15 artefacts, which were trained on the old label. On a pass, what may be promoted is CO-18's retrain under its own version. The ruling is `CD10`.

**Group:** 1 data settled · **Depends on:** `CO-17` (trusted rebuild with the CO-09 + CO-15 label) · **Blocker:** none.

**Ruling:** CD8 (2026-10-22): leave-one-season-out within 2018–2024. 2026 is not used for stint life, because it is a mixed-era season (power-unit change).

**Sources:** `ml/src/evaluate.py`, `ml/src/survival.py`, `ml/models/manifest.json`.

---

## Why this test

v15 fails the beats-baseline check for stint life on 2025 (NLL 2.3286 against 2.3225, p 0.96, won 2 of 5 folds). The other four models pass. 2025 has been used for selection several times, and the served v14 model was trained on 2018–2025, so there is no unused season left. This test is the cleanest available, and its result is provisional.

## Method

1. **Write the rules first**, in the log, before any fit:
   - the candidate list: the v14 and v15 configurations only, no new candidates;
   - the folds: leave-one-season-out, one season held out at a time, from 2018 to 2024;
   - the pass test: v15 must beat the baseline on stint life on a majority of folds with a stated margin.
2. Refit both configurations in every fold on the new label version only (CO-17's build).
3. Score each held-out season once. No changes to candidates or thresholds after the scores are seen.
4. Record the result as provisional, with the seasons already used for other choices named.

## Outcomes

- **Pass:** CO-18's retrain may be promoted for stint life, with the stint-life card marked provisional.
- **Fail:** v14 stays for stint life, and the assistant's cards say so.

Either way the result goes to the owner with CO-18's gate table for `CD10`.

## Acceptance

The rules are in the log before the first fit (checked by the commit order). The result table lists every held-out season.

## Definition of done

The test runs once and its result and the promotion call are recorded in the log. Promotion is the owner's call.
