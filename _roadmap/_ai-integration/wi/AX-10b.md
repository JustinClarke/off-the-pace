# AX-10b - teammate_id as a policy field on race.teammate_gap

**Group:** 4 assistant · **Depends on:** AX-10 · **Model/cost:** sonnet-5, 0.25d.

**Sources:** `_evidence/AX-10-2026-11-08/PROVENANCE.txt` (owner decision 1), `app/src/assistant/cards/sql/raceKinds.ts`, `card.schema.json` (policy_fields), `app/src/assistant/core/cardStore.ts`, `app/src/assistant/prompt/bundles.ts` (resolveBundle takes scope.teammate_id or a teammateOf callback).

## Problem
The card store derives the teammate from the race.teammate_gap card's display text ("vs PER"), else from the one other driver on the same constructor in that race's results. That breaks if the display text changes. The mart already has the teammate column.

## Method
Add `teammate_id` to `policy_fields` in `card.schema.json` (regenerate card.types.ts and scripts/assistant_cards/card_types.py with app/scripts/gen-card-types.mjs), set it in the race.teammate_gap kind from the mart column (scratch export only), have cardStore/resolveBundle prefer it, and keep the old derivation as a fallback with a test.

## Acceptance
The five demo races (2024_1 VER, 2020_14 HAM, 2018_1 RIC, 2021_16 HAM, 2024_5 NOR) resolve the same teammate via the field as before; a card whose display text is changed still resolves; unavailable gap cards keep a teammate_id when the mart has one. Full app vitest keeps only the 2 pre-existing failures; typecheck clean. Use scratch exports only; never open data/*.duckdb; do not write app/public/data. Do not commit.
