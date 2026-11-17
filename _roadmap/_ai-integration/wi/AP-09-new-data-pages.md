# AP-09 — App pages for the new measured marts

**Group:** 1b new-data · **Depends on:** TX-23, TX-24, TX-25, TX-26, TX-27 · **Model / cost:** `sonnet-5`, 2-3d

**How to run:** export to a scratch `--out` (TX-12 flags), never over `app/public/data/` without the owner (HD12 pattern). Nothing committed or published by an agent.

## Why
Each new mart is a fan feature: qualifying corner skill, track-limits counts, speed traps, race-control detail, pit-stop cross-check. Pages come before cards: under HD3 a card is the page's own `queries.ts` + `transform.ts` run headless.

## Method
One feature folder each under `app/src/features/`, following the existing pattern (`queries.ts`, `transform.ts`, `page.tsx`, `methodology.tsx`, tests). Provenance from the manifest (AP-02). Missing values render as unavailable with the reason (AP-01). Export additions in `scripts/export_app_data.py`. Docs page per feature under `docs/app/` (docs-drift check must pass).

## Done when
Each page renders on a scratch export, its tests pass, and the docs-drift check passes.

## Sources
`scripts/export_app_data.py`, `app/src/features/`, `app/src/nav/routes.ts`, `docs/app/`.
