# AX-07c - pit-strategy cards vs AP-08, wilson_95, calibration_flag on cards

**Group:** 3 foundations · **Depends on:** AX-07b, AP-08 · **Model/cost:** sonnet-5, 0.5d · **Blocker:** none.

**Sources:** `_evidence/AX-07b-2026-11-08/PROVENANCE.txt`, `_evidence/AP-08-2026-11-08/PROVENANCE.txt`, `_evidence/TX-13-2026-11-08/PROVENANCE.txt`, `app/src/assistant/cards/headless/headless.parity.test.ts`, `app/src/features/pit-strategy/{queries,transform,cards}.ts`, `app/src/assistant/cards/card.schema.json`, `sql/seasonKinds.ts`.

## 1. Pit-strategy parity (regression)
With `AX04_DATA_DIR` set to a scratch export (e.g. scratchpad/laneL/out) three headless.parity pit-strategy cases fail (2024_8, 2019_1, 2022_5) since AP-08 changed the page's stint ordering (fct_stint_features stint number, `next_compound`, the 734 previously missing stints now present). The card kinds must agree with the page: update the pit-strategy card kind(s) and the parity oracle to the new ordering. Never relax a tolerance. Report which of the 3 cases changed because of the extra stints versus the ordering.

## 2. wilson_95
`race_control.pooled_rate` has no interval because the page's Wilson interval has no kind in the card interval enum. Add `wilson_95` to `card.schema.json`, regenerate `card.types.ts` and `scripts/assistant_cards/card_types.py` (see app/scripts/gen-card-types.mjs), and carry the page's Wilson interval on the card, with a test that the interval equals the page's.

## 3. calibration_flag
`dim_circuits.calibration_flag` is exported (TX-13) but no card reads it. Add it as a policy field on circuit-scoped cards so CALIBRATION_FLAGGED_CIRCUIT can fire; add a test where a REVIEW_REQUIRED circuit makes the rule fire and a SKIPPED one does not. Use the scratch export only.

## Acceptance
Parity tests pass with AX04_DATA_DIR set; schema validates the new interval kind; the full app vitest keeps only the 2 pre-existing CHANCE_LINE failures; typecheck clean. Do not commit, do not open data/*.duckdb, do not write app/public/data.
