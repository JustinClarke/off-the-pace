# AX-28 — Card kinds and qv_* query views for the new measured marts

**Group:** 1b new-data · **Depends on:** AP-09 · **Blocker:** HD14 (owner: is the assistant unparked?) · **Model / cost:** `opus-5`, 2d

## Why
Once the marts and pages exist, the assistant can answer track-limits, speed-trap, race-control-detail, pit-cross-check and qualifying-corner questions from cards and bounded query views. All are transform class (rule 4: live). Rule 3: no card on a mart whose TX item is open. Rule 9 does not bite: none of these reads dirty air or the chance line.

## Method
New card kinds in `app/src/assistant/cards/kinds.ts` and `registry.ts`, built headless from the AP-09 pages (HD3 A); narrow `qv_*` views in `scripts/assistant_query_views.py` (observed measures only, HD4 A); deny-list and lineage tests extended; catalogue version bumped. No model calls, no Worker change.

## Done when
Lineage test classes every new kind as transform; parity tests pass on a scratch export; deny-list unchanged for modelled columns.

## Sources
`app/src/assistant/cards/kinds.ts`, `app/src/assistant/cards/registry.ts`, `scripts/assistant_query_views.py`, `app/src/assistant/cards/lineage.test.ts`.
