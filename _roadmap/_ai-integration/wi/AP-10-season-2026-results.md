# AP-10 — 2026 season results and race recaps page, with speed traps and track-limit counts

**Group:** 0b-new-data · **Depends on:** AP-09, TX-24, TX-25 · **Model / cost:** `sonnet-5`, 1.5d · **Stage:** SPEC (nothing built)

**Ruling (HD21, owner, 2026-11-17):** "okay cool just add it to build order we shall revisit once thats done". 2026 is used for measured, descriptive pages only: no fit, no model, no label, no rating, no "expected" or "predicted". This page is the first. The owner will revisit 2026 use once it is done. HD17 (2026-11-16) still holds: 2026 is not the holdout, and no fit or evaluation reads it. The guard test from TX-29 (`holdout_guard.py`, `assert_no_fit_reads_holdout.sql`) covers 2025; this item extends the same rule to 2026 on the page side.
**How to run:** export to a scratch `--out`, never over `app/public/data/` without the owner. Nothing committed or published by an agent.

## Purpose
A fan-facing record of the 2026 season so far, drawn only from measured data, with the data window stated on the page.

## What it shows
- Race classification, grid, points and laps completed per race.
- Fastest lap per race.
- A season table (drivers and constructors, points as scored).
- Speed traps per driver and per team (TX-25 mart).
- Track-limit counts per driver, per race and per turn (TX-24 mart).

## What it must NOT show
Predicted finishes, expected points, ratings, degradation or any other fit output, or any model-derived number.

## Labels
- Everything shown is labelled "measured".
- Bahrain R is held back (TyreLife): label it "provisional".
- Monaco R has thin telemetry (about 9% of laps): label its speed-trap and telemetry-based figures "provisional", with the coverage stated.
- The data window (rounds in Bronze, last round included) is stated on the page and comes from the manifest.

## Acceptance
1. Page-side guard test (see Waiting items): fails if any model or seed table or fit input reads race_year 2026; passes otherwise. Prove it fails on a planted 2026 row.
2. Export check: the page's exported data contains no 2026 rows in any fit input.
3. Missing values render as unavailable with the reason (AP-01); provenance from the manifest (AP-02); docs page under `docs/app/` with docs-drift passing.

## Waiting items
- Page-side 2026 guard test (not a separate board item): the test in acceptance 1. Written after AP-09 lands, so it covers the new-data pages too. It extends TX-29's `holdout_guard.py` rule to race_year 2026 for every model, seed and fit input; it does not edit `transform/` or `ml/` until this item is run.
- AP-09 (the new-data pages) and the TX-25 and TX-24 marts.

## Sources
`scripts/export_app_data.py`, `app/src/features/`, `app/src/nav/routes.ts`, `docs/app/`.
