# ARCHIVED 2026-11-09 - the wake-calibration plan

**This plan is closed.** Owner decision, 2026-11-09: drop wake calibration. Nothing here is run, extended or maintained, and no wake-calibration number is used anywhere in the product. Work on time lost behind a car continues in a new plan.

## Why

- **No registered result exists.** WC-03 and WC-04 closed with no verdict (DD-WC15: G3.4 digest mismatch on NFC path names; nothing fitted or scored). The WC-10 discovery registration was signed, but its fit (WC-10e) never ran: it is blocked on amendment B2 (DD-WC23, open). Nothing was fitted on real data.
- **Replaced by a simpler per-track analysis of time lost behind a car.** That work continues in a new plan; this file does not describe it.
- **The owner's stated reasons:** _(to be filled in by the owner, in the owner's words)_

## What was done (state as of archive)

Pointer at archive: **WC-10e** in [`status/build-log.json`](status/build-log.json). The log was not edited when the plan was archived.

| Phase | Items | State at archive |
| :-- | :-- | :-- |
| 0 Data and reference | WC-01 | LANDED (per-corner pass table) |
| 1 Measurement checks | WC-02 | CLOSED |
| 2 Estimator | WC-03 | CLOSED, no verdict (DD-WC15) |
| 3 Validation | WC-04 | CLOSED, no verdict (DD-WC15) |
| 4 Modelled stints and labels | WC-05 | SPEC, never started |
| 5 App output | WC-06 | SPEC, never started |
| 6 Replay | WC-07, WC-08 | SPEC, never started |
| 7 2026 ingest | WC-09 | SPEC, never started |
| 8 Levels (WC-10) | WC-10a, WC-10b, WC-10c, WC-10d | LANDED (counts, sidecar, data gate, discovery registration) |
| | WC-10e | BUILDING, blocked on amendment B2 (DD-WC23); not run |
| | WC-10f, WC-10g, WC-10h, WC-10j | BLOCKED |
| | WC-10i, WC-10k, WC-10l, WC-10m | SPEC |

Decisions still open at archive: DD-WC3, DD-WC19, DD-WC21, DD-WC23. They are not ruled; they lapse with the plan.

## What is not used

No wake number (no loss, curve, coefficient, level or label from this plan) is used anywhere in the product, as a fallback or otherwise.

## Where the record lives (kept in full, frozen)

| What | Where |
| :-- | :-- |
| WC-10 discovery registration | [`wi/WC-10-discovery-preregistration-DRAFT.md`](wi/WC-10-discovery-preregistration-DRAFT.md), committed alone in `6fd0330` (2026-10-30). The file still reads "DRAFT, unsigned"; the sign-off is the commit and DD-WC20. |
| Lock (the registered file's SHA-256) | `4d679bf6c94b12cf186776467478400c1feef89930be87d3fe36be49f1e8d248`, recorded in the DD-WC20 resolution in [`status/build-log.json`](status/build-log.json) |
| Decisions | DD-WC1 to DD-WC23 in [`status/build-log.json`](status/build-log.json) (`decisions`); DD-WC15 closes WC-03 and WC-04, DD-WC20 signs WC-10d, DD-WC23 is the open B2 blocker |
| Evidence | [`_evidence/`](_evidence/): `WC-01-2026-10-27/`, `WC-02-2026-10-27/`, `WC-03-2026-10-27/`, `WC-03-prep-2026-10-28/`, `WC-04-2026-10-29/`, `WC-10-2026-10-29/` |
| Working parquet (git-ignored, not committed) | [`_artifacts/`](_artifacts/): `WC-03-run/pass-table/`, `WC-10/sidecar/`, each with `SHA256SUMS` |
| Code | `transform/tasks/wake_calibration/`, left where it stands. Its path constants still point at `_roadmap/_wake-calibration/`; whether to freeze, repoint or remove it is an owner call. |

## State of the log

The log is left as it stood on 2026-10-30: items were not moved to terminal stages when the plan was archived. `python3 _roadmap/_archive/_wake-calibration/status/board.py --check` still runs and passes.
