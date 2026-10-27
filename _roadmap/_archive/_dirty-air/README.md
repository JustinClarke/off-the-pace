# _dirty-air - ARCHIVED 2026-10-27 (see [ARCHIVED.md](ARCHIVED.md); superseded by [`../_wake-calibration/`](../_wake-calibration/README.md)) - a continuous, distance-based traffic cost, measured in real time

**Goal.** Replace the per-lap dirty-air flag with a measure built on each position sample's time gap to the car ahead. Summed per micro-sector, sector and lap, it gives a cost that can be shown as a session replay. It is built in phases, and no label moves until the final gate.

Design: [`wi/DA-design-note.md`](wi/DA-design-note.md). Work items: `wi/DA-01` to `wi/DA-05`, one per phase.

## Layout

```
_dirty-air/
├── README.md              this file
├── status/                execution state - start here
│   ├── board.py           renderer + validator (never writes to the log)
│   ├── build-log.json     AUTHORITATIVE state: items, phases, open decisions, watch rules, handoffs
│   └── BUILD-ORDER.md     the rules, and the generated, ordered task list
├── wi/                    one doc per phase, plus the design note
└── _evidence/             per-item artefacts, one folder per item and date: <item>-<date>/ with PROVENANCE.txt
```

Same mechanism as [`../_ai-integration/`](../_ai-integration/README.md) and [`../_fixes/`](../_fixes/README.md): a JSON log, a read-only board, a generated task list.

## Running it

```bash
python3 _roadmap/_dirty-air/status/board.py            # phases, what each waits on, open decisions, next command
python3 _roadmap/_dirty-air/status/board.py --check    # invariants; run after any edit to build-log.json
```

**State lives in `status/build-log.json` and nowhere else.** If a work-item doc seems to record that something is done, the log wins.

## Phases

| Phase | Item | Weeks | Gate to continue |
| :-- | :-- | :-- | :-- |
| 0 Audit | DA-01 | 2-3 | At least 90% of green samples valid; gap disagreement under 0.1 s for gaps under 2 s |
| 1 Tables | DA-02 | 3-4 | Loss rises as the gap shrinks |
| 2 Identification | DA-03 | 4-6 | Effect under 1 s excludes 0; placebos pass |
| 3 Validation | DA-04 | 3-4 | Out-of-sample gain |
| 4 Label and app | DA-05 | 3 (A) or 6+ (B) | Tests green; owner reviews the label diff |

Total about 16-24 weeks.

## Dependencies on other tracks

- **CO-17** in [`../_ai-integration/`](../_ai-integration/README.md) rebuilds the dev warehouse. Phase 0 runs on stale dev until then (watch W1).
- Path B moves labels, so it goes through the ML retrain plan on its own branch, not here.

## Owner decisions

Open decisions are in the log: DD1 (approve Phase 0), DD2 (path A or B), DD3 (marshal-sector ingestion), DD4 (wording: causal or adjusted traffic cost).
