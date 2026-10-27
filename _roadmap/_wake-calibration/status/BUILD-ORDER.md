# Wake-calibration build order: rules and the ordered task list

**State lives in [`build-log.json`](build-log.json), and only there.** This file holds the rules
and one **generated** task list, spliced in at the bottom by the board.

A hand-written checklist here is a defect. Edit the JSON, run `--check`, then `--write-order`.
Never type into the generated block.

```bash
python3 _roadmap/_wake-calibration/status/board.py                # the board, open decisions, next command
python3 _roadmap/_wake-calibration/status/board.py --check        # invariants only; exit 1 on failure
python3 _roadmap/_wake-calibration/status/board.py --order        # the ordered task list, to stdout
python3 _roadmap/_wake-calibration/status/board.py --write-order  # ...and spliced into this file
python3 _roadmap/_wake-calibration/status/board.py --watch        # the watch list in full
python3 _roadmap/_wake-calibration/status/board.py --ship         # exit 1 while a ship-blocker is open
```

**Rules**

1. The pointer is the one item to run next. Run `--check` after every edit.
2. A `BLOCKED` item waits on an open decision. Put the decision to the owner first, with the options
   translated, before spawning work on it.
3. Nothing is committed or deployed without a yes from the owner.
4. Nothing is fitted, and no coefficient or gate result is computed, before the pre-registration is
   committed alone and its SHA-256 recorded in the log. Thresholds are not changed after seeing a result.
5. Work runs on a scratch copy of the warehouse, never on `data/dev.duckdb` directly.
6. No number from the archived dirty-air method (DA-03) is used, as a fallback or otherwise.
7. Every modelled value carries the disclaimer recorded in DD-WC2, word for word; unavailable is
   shown as "—" with a reason, never 0; totals print the modelled share.

<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-10-27T12:00:00+04:00`. Run `python3 _roadmap/_wake-calibration/status/board.py --write-order` after any edit to the log._

**6 live items** (0 blocked). The pointer is on **WC-01** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 0 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Sources | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | [WC-01](../wi/WC-01-data-and-reference.md) ▶ | 0-data | SPEC | 2-3 wk | `opus-5` | data/bronze/telemetry/, data/bronze/laps/, data/bronze/track_status/, data/bronze/race_control/, data/bronze/weather/, data/bronze/circuit_info/, transform/models/intermediate/ | Per-corner pass table from bronze: gap 300-50 m before the corner, own clean reference within ±4 laps, exclusions | — |
| 2 | [WC-02](../wi/WC-02-measurement-checks.md) | 1-checks | SPEC | 1-2 wk | `opus-5` | data/bronze/laps/, data/bronze/reference/jolpica/pit_stops/, transform/tests/ | Measurement checks: timing agreement per race, the 1,124 car-ahead-pits events, minimum-speed agreement | WC-01 |
| 3 | [WC-03](../wi/WC-03-estimator.md) | 2-estimator | SPEC | 3-5 wk | `fable-5.1` | transform/tasks/coefficients/, transform/models/intermediate/ | Estimator: monotone loss curve per corner class and era; held up / dirty air / racecraft / under attack | WC-02 |
| 4 | [WC-04](../wi/WC-04-validation.md) | 3-validation | SPEC | 2-3 wk | `opus-5` | transform/tests/, transform/tasks/coefficients/ | Validation on a held-out season: scorecard incl. car-ahead-pits, physics sign, flat reference band, vs 0.331 × share | WC-03 |
| 5 | [WC-05](../wi/WC-05-modelled-stints-and-labels.md) | 4-modelled | SPEC | 2-4 wk | `fable-5.1` | transform/models/intermediate/, transform/models/marts/ | Modelled-stint calibration (own other stint, teammate) and the measured / modelled / unavailable labels | WC-04 |
| 6 | [WC-06](../wi/WC-06-app-output.md) | 5-app | SPEC | 2-3 wk | `opus-5` | app/src/features/dirty-air-cost/, app/src/features/dirty-air-lap-map/, transform/models/marts/ | App output: measured / modelled / unavailable labels; totals show the modelled share | WC-05 |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Watch list — kept an eye on, not tasks and not rulings

_Generated from the watch rules in [`build-log.json`](build-log.json) (`watch_rules`); watch entries update automatically as items land or decisions resolve. A rule whose trigger needs something the log cannot see (a commit, a re-export, a rebuild, your ruling) stays open until its `resolved` and `resolution` are recorded._

**2 open** (0 ship-blockers). Full detail: `python3 _roadmap/_wake-calibration/status/board.py --watch`. `python3 _roadmap/_wake-calibration/status/board.py --ship` exits 1 while a ship-blocker is open.

Each watch rule is tagged with the recommended model (haiku/sonnet/opus) for token efficiency (0 haiku, 1 sonnet, 1 opus). The tag is the smallest model that can work the rule to its `clears_when`; step up a tier the moment the rule turns out to leave a choice open that the tag assumed was made.

- **`haiku`** — Maps to haiku-4-5. A binary check, or recording a resolution the evidence or the user has already settled: is it committed, did the named tests pass on the rebuild, write down the accept. The output has a mechanical check (a test result, a file list, git log).
- **`sonnet`** — Maps to sonnet-5. The fix or the options are written down in the rule: pick between two named options, run a named rebuild or export and check the pages, review a diff, reconcile counts, reword text to a meaning already settled.
- **`opus`** — Maps to opus-5 (fable-5.1 if the rule turns into a new estimator). Rules on a trade-off, designs the fix, audits a decision, or turns a measurement into a claim: label-moving changes, leakage boundaries, gate runs before a promotion.

| ID | Kind | Item | Model | What | Clears when |
| :--- | :--- | :--- | :--- | :--- | :--- |
| W1 | hazard | WC-03 | `opus` | Nothing is registered: no fit, curve or gate before a committed, hashed pre-registration | The pre-registration is committed alone and its SHA-256 is recorded on WC-03. |
| W2 | hazard | WC-06 | `sonnet` | No archived dirty-air (DA-03) number may appear in the product, as a fallback or otherwise | WC-06 has landed and its tests show no old-method value in any app output. |

<!-- END GENERATED TASKS -->
