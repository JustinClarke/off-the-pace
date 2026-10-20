# CO-10 — 2026 flag-chance test: one pre-registered score

**Status:** SPEC (nothing run). **Group:** D carry-over · **Depends on:** `CO-09` (label fix) · **Blocker:** owner ruling `CD4` (acceptance rule).

**Sources:** `ml/src/flag_chance.py`, `ml/src/survival.py`, `app/src/ml/flagChance.ts`, `app/public/models/flag_chance_lookup.json`.

---

## Why this item exists

The experimental chance line on the degradation simulator (see `CO-08`) failed its 2025 acceptance bar, and 2025 has now been scored several times. The only clean season left is 2026, and only as its races finish. This item says what gets measured, with what rule, before any 2026 outcome is looked at, so that one scoring is a real test and not a fourth look at the same data.

## Pre-registration (must be frozen before 2026 outcomes enter the warehouse)

1. **Method.** The `last3` Platt lookup as shipped in `app/public/models/flag_chance_lookup.json`, with its sha256 recorded in the freeze.
   **Fold scheme (CD6):** pending owner ruling. Expanding window (the project's existing CV) is the recommendation, and the shipped lookup already matches it. Leave-one-season-out gives different values and a different 2024 weighting pick, so the chosen scheme must be written here before the freeze.
2. **Model.** The served v14 artefacts, with their sha256 from `ml/models/manifest.json`. Gate 0 (below) must pass first.
3. **Label rule.** The CO-09 stint-end rule, with red-flag tyre changes censored and same-tyre splits joined. The rule's version is recorded.
4. **Acceptance rule.** Whatever `CD4` is ruled as. The 10-bin, within-5-pp rule is the default unless the owner rules otherwise.
5. **Split.** Primary: all of 2026 scored once. Secondary (reported, not gating): early-2026 races fit the map, late-2026 races test it, with the cut date fixed in advance.
6. **Score once.** One scoring on 2026 races finished at freeze time. Later races are reported as they finish, under the same frozen rule, and are not used to change the method.

## Gate 0 — the stint-life model still works on 2026

2026 has new cars and tyres. Before the chance line is scored, the served stint-life model must pass its own 2026 check. If it fails, the test is void, not failed, and the result says so.

## Method

1. Ingest 2026 stints and pit stops from OpenF1 (ingest only; no scoring) into the warehouse, and check coverage against the 2026 calendar.
2. Freeze the pre-registration above, with checksums, before the first 2026 score is written.
3. Compute the raw chance and the calibrated chance on 2026 final-stint rows only.
4. Score with the same bins, Brier, ECE and base-rate guess used for 2025, so the numbers line up.

## Definition of done

Frozen pre-registration with checksums; OpenF1 2026 ingest with coverage recorded; gate 0 result; one scored result with bins, Brier, ECE and base rate; the owner's decision recorded against the frozen rule. Nothing promoted or committed without the owner's yes.

## Risks and limits

- 2026 is one season, so bins with fewer than 100 rows will be thin, and a pass is one test, not proof.
- OpenF1 and FastF1 disagree on the 2026 calendar, so the race list must be fixed from one source before the freeze.
- The OpenF1 ingest is new code and needs its own checks.
