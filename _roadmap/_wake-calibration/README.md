# _wake-calibration - traffic loss per corner, against the driver's own clean pace

**Goal.** Measure the time a car loses in traffic, corner by corner, against the driver's own clean passes of the same corner a few laps either side. The gap is measured before the corner, and "held up" is kept separate from "dirty air". Every number carries a label: measured, modelled or unavailable.

**Status: plan only.** Nothing is registered, built, fitted or run. Replaces the archived [`../_dirty-air/`](../_dirty-air/ARCHIVED.md) method; no old-method number is used.

Design: [`wi/WC-design-note.md`](wi/WC-design-note.md). Work items: `wi/WC-01` to `wi/WC-06`, one per phase.

## Layout

```
_wake-calibration/
├── README.md              this file
├── status/                execution state - start here
│   ├── board.py           renderer + validator (never writes to the log)
│   ├── build-log.json     AUTHORITATIVE state: items, phases, open decisions, watch rules, handoffs
│   └── BUILD-ORDER.md     the rules, and the generated, ordered task list
├── wi/                    one doc per phase, plus the design note
└── _evidence/             per-item artefacts, one folder per item and date: <item>-<date>/ with PROVENANCE.txt
```

Same mechanism as [`../_dirty-air/`](../_dirty-air/README.md): a JSON log, a read-only board, a generated task list.

## Running it

```bash
python3 _roadmap/_wake-calibration/status/board.py            # phases, what each waits on, open decisions, next command
python3 _roadmap/_wake-calibration/status/board.py --check    # invariants; run after any edit to build-log.json
```

**State lives in `status/build-log.json` and nowhere else.** If a work-item doc seems to record that something is done, the log wins.

## Phases

| Phase | Item | Weeks (rough) | Done when |
| :-- | :-- | :-- | :-- |
| 0 Data and reference | WC-01 | 2-3 | Per-corner pass table built on a scratch copy, with exclusions tested and coverage counted |
| 1 Measurement checks | WC-02 | 1-2 | Timing agreement per race, the 1,124 car-ahead-pits events, minimum-speed agreement recorded |
| 2 Estimator | WC-03 | 3-5 | Pre-registration committed and hashed first; monotone curve per corner class and era |
| 3 Validation | WC-04 | 2-3 | Held-out season scorecard read by the owner |
| 4 Modelled stints and labels | WC-05 | 2-4 | Modelled references checked; every stint labelled measured, modelled or unavailable |
| 5 App output | WC-06 | 2-3 | Labels on every number; totals show the modelled share; owner reviews |

Stints with no clean lap: 16.7% (1,177). About 86% of those can be filled from another stint of the same driver or the teammate; about 2% of all stints (162) are unavailable.

## Owner decisions

Open in the log: **DD-WC1** (approve starting Phase 0) and **DD-WC2** (confirm the disclaimer wording for modelled stints).
