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
8. Working artefacts (pass tables, intermediate parquet, scorecards) are written to
   `_roadmap/_wake-calibration/_artifacts/<item>/`, never to session scratch. Each folder has a
   `SHA256SUMS`. The parquet is git-ignored and rebuildable; the provenance, counts and hashes
   are committed under `_evidence/`.

<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-11-01T01:30:00+04:00`. Run `python3 _roadmap/_wake-calibration/status/board.py --write-order` after any edit to the log._

**20 live items** (9 blocked). The pointer is on **WC-16** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 8 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Sources | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | [WC-07](../wi/WC-07-replay-dashboard.md) | 6-replay | SPEC | 1-2 wk | `opus-5` | transform/tasks/wake_calibration/, data/bronze/telemetry/, data/bronze/laps/ | Archived-race replay dashboard: per-lap gap (s and m) to the car ahead, reference status and label; measurement only | — |
| 2 | [WC-09](../wi/WC-09-2026-ingest.md) | 7-ingest | SPEC | 1-2 wk | `sonnet-5` | ingestion/src/ingest.py, data/bronze/manifests/ | Ingest the 2026 season into bronze (archived FastF1 timing); count with the WC-01 builder, no fit | — |
| 3 | [WC-11](../wi/WC-11-interim-placeholder-values.md) | 9-interim | MEASURED | 2-3 d | `opus-5` | transform/seeds/wake_placeholder_values.csv, transform/models/intermediate/int_lap_wake_placeholder_cost.sql, transform/models/intermediate/int_lap_proximity.sql, app/src/features/dirty-air-cost/, scripts/export_app_data.py | Interim placeholder wake values per circuit (assumed s/lap within 1 s, tapering to 0 at 2 s) for the dirty-air cost page; labelled modelled/placeholder, never ML | — |
| 4 | [WC-12](../wi/WC-11-interim-placeholder-values.md) | 9-interim | MEASURED | 1-2 d | `opus-5` | transform/seeds/wake_placeholder_rule.csv, transform/seeds/wake_placeholder_race_structure.csv, transform/tasks/wake_calibration/wc12_structure.py, transform/models/intermediate/int_wake_placeholder_race_loss.sql, transform/models/intermediate/int_lap_wake_placeholder_cost.sql, app/src/features/dirty-air-cost/ | Per-race placeholder wake loss: a transparent rule from the layout's corner mix (structure columns only) x an assumed regulation-era factor, bounded 0.15-0.55 s; flagged class fallback; still modelled/placeholder, never ML | WC-11 |
| 5 | [WC-13](../wi/WC-11-interim-placeholder-values.md) | 9-interim | MEASURED | 1 d | `opus-5` | transform/seeds/wake_placeholder_compound_factor.csv, transform/seeds/wake_placeholder_constructor_factor.csv, transform/seeds/wake_placeholder_rule.csv, transform/models/intermediate/int_lap_wake_placeholder_cost.sql, transform/tests/assert_wake_placeholder_factors.sql, app/src/features/dirty-air-cost/ | Placeholder wake loss per lap: race value x an assumed bounded tyre factor (relative dry compound: SOFT 1.10, MEDIUM 1.00, HARD 0.96; wet/inter neutral) x a car factor (per season x constructor_id, neutral 1.00 for every team), clamped 0.15-0.55 s; missing keys neutral and flagged; still modelled/placeholder, never ML | WC-12 |
| 6 | [WC-14](../wi/WC-11-interim-placeholder-values.md) | 9-interim | MEASURED | 0.5 d | `opus-5` | app/src/features/dirty-air-cost/ | Dirty Air Cost page visuals: per-driver bar chart and a lap-by-lap "how the cost is built" diagram (measured exposure strip above the assumed cost strip), display only | WC-13 |
| 7 | [WC-15](../wi/WC-11-interim-placeholder-values.md) | 9-interim | MEASURED | 0.5 d | `opus-5` | app/src/features/dirty-air-cost/, transform/models/intermediate/int_lap_wake_placeholder_cost.sql | Dirty Air Cost table redesign (collapsible rows, tidied notes block with an Assumptions disclosure) and a zero-exposure check on GAS/TSU (2025 round 5): finding is no bug, both retired on lap 1 and lap 1 is neutralised; correlation of the Lap Air Map air-state lap counts with the placeholder cost reported | WC-14 |
| 8 | [WC-16](../wi/WC-11-interim-placeholder-values.md) ▶ | 9-interim | MEASURED | 1 d | `opus-5` | transform/seeds/wake_placeholder_tyre_allocation.csv, transform/seeds/wake_placeholder_c_number_factor.csv, transform/models/intermediate/int_lap_wake_placeholder_cost.sql, transform/tests/assert_wake_placeholder_tyre_allocation.sql, transform/tests/assert_wake_placeholder_factors.sql, app/src/features/dirty-air-cost/, _roadmap/_wake-calibration/_evidence/WC-16-2026-10-31/ | Placeholder tyre factor by Pirelli C-number (step by C-number distance from the race medium: 0.93/0.96/1.00/1.10/1.17, clamped 0.90-1.17; medium shift dropped by DD-WC29; 2018 relative class), verified 173-race allocation seed, DD-WC2 reworded, car factor research (all neutral) | WC-13 |
| 9 | [WC-10e](../wi/WC-10-exploratory-levels-PLAN-DRAFT.md) | 8-levels | BLOCKED | 1-2 wk | `opus-5` | transform/tasks/wake_calibration/, _roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/, _roadmap/_wake-calibration/_artifacts/WC-10/sidecar/ | Stage 2: discovery fit of design A on 2022-23 (pace, min speed, exit speed, lap arm, held-up/dirty split, tyre carry-over) and the registered diagnostics | **DD-WC24** (human call) |
| 10 | [WC-10f](../wi/WC-10-exploratory-levels-PLAN-DRAFT.md) | 8-levels | BLOCKED | 2-3 d | `opus-5` | _roadmap/_wake-calibration/_evidence/, _roadmap/_wake-calibration/wi/WC-10-exploratory-levels-PLAN-DRAFT.md | Stage 2b: level cut points from the discovery fit; one 2023 race as a static per-lap level table (exploratory, in-sample) | WC-10e, **DD-WC24** (human call) |
| 11 | [WC-10g](../wi/WC-10-exploratory-levels-PLAN-DRAFT.md) | 8-levels | BLOCKED | 2-3 d | `opus-5` | _roadmap/_wake-calibration/wi/WC-10-exploratory-levels-PLAN-DRAFT.md, _roadmap/_wake-calibration/_evidence/ | Stage 3a: confirmatory registration draft: fixed cut points, gates C1-C5 with Holm, bracketed-subset tolerance, draws and seed, data gate, restart rule, labels | WC-10f, **DD-WC24** (human call) |
| 12 | [WC-10h](../wi/WC-10-exploratory-levels-PLAN-DRAFT.md) | 8-levels | BLOCKED | 3-5 d | `opus-5` | transform/tasks/wake_calibration/, _roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/, _roadmap/_wake-calibration/_artifacts/WC-10/sidecar/ | Stage 3b: one confirmatory run on 2024-25 under the signed registration | WC-10g, **DD-WC21** (human call), **DD-WC24** (human call) |
| 13 | [WC-10i](../wi/WC-10-exploratory-levels-PLAN-DRAFT.md) | 8-levels | BLOCKED | 2-3 d | `opus-5` | _roadmap/_wake-calibration/_evidence/, _roadmap/_wake-calibration/wi/WC-10-exploratory-levels-PLAN-DRAFT.md | Stage 3c: scorecard: which of pace / aero / tyre get a level, per C1-C5 | WC-10h, **DD-WC24** (human call) |
| 14 | [WC-05](../wi/WC-05-modelled-stints-and-labels.md) | 4-modelled | SPEC | 2-4 wk | `fable-5.1` | transform/models/intermediate/, transform/models/marts/ | Modelled-stint calibration (own other stint, teammate) and the measured / modelled / unavailable labels | WC-10i |
| 15 | [WC-06](../wi/WC-06-app-output.md) | 5-app | SPEC | 2-3 wk | `opus-5` | app/src/features/dirty-air-cost/, app/src/features/dirty-air-lap-map/, transform/models/marts/ | App output: measured / modelled / unavailable labels; totals show the modelled share | WC-05 |
| 16 | [WC-08](../wi/WC-08-replay-loss-scale.md) | 6-replay | SPEC | 1 wk | `opus-5` | transform/tasks/wake_calibration/, transform/tasks/coefficients/ | Loss scale on the replay dashboard, only after WC-03, WC-04 and WC-05; every value labelled, disclaimer on modelled | WC-10i, WC-05, WC-07 |
| 17 | [WC-10j](../wi/WC-10-exploratory-levels-PLAN-DRAFT.md) | 8-levels | BLOCKED | 3-5 d | `opus-5` | _roadmap/_wake-calibration/wi/WC-07-replay-dashboard.md, transform/tasks/wake_calibration/, _roadmap/_wake-calibration/_evidence/ | Stage 4a: replay levels spec and levels(season, race) input on WC-07: three chips per lap and car with label, confidence, 'extrapolated' flag and disclaimer | WC-10i, WC-07, **DD-WC19** (human call), **DD-WC24** (human call) |
| 18 | [WC-10k](../wi/WC-10-exploratory-levels-PLAN-DRAFT.md) | 8-levels | BLOCKED | 3-5 d | `sonnet-5` | transform/tasks/wake_calibration/, _roadmap/_wake-calibration/wi/WC-07-replay-dashboard.md | Stage 4b: replay levels wiring and label tests | WC-10j, **DD-WC24** (human call) |
| 19 | [WC-10l](../wi/WC-10-exploratory-levels-PLAN-DRAFT.md) | 8-levels | BLOCKED | 1-2 wk | `opus-5` | _roadmap/_wake-calibration/wi/WC-10-exploratory-levels-PLAN-DRAFT.md, transform/tasks/wake_calibration/ | Optional (stage 5): trailing-only (causal) level variant under its own registration; agreement with the retrospective v1 | WC-10i, **DD-WC24** (human call) |
| 20 | [WC-10m](../wi/WC-10-discovery-preregistration-DRAFT.md) | 8-levels | BLOCKED | 3-5 d | `opus-5` | transform/tasks/wake_calibration/, _roadmap/_wake-calibration/_artifacts/WC-03-run/pass-table/, _roadmap/_wake-calibration/wi/WC-10-discovery-preregistration-DRAFT.md | FALLBACK CANDIDATE (built later): pooled general dirty-air estimator: all drivers pooled, controls for race, lap, corner, compound, tyre age and one fixed effect per driver per race; loss per gap bin; run beside design A | WC-10e, **DD-WC24** (human call) |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **DD-WC3** (blocks nothing) — Licence the OpenF1 live data feed (paid; non-commercial, share-alike licence) for any live use of the method?
- **DD-WC19** (blocks `WC-10j`) — Relax WC-07's 'no loss, delta, coefficient, curve or scale' rule so the replay can show WC-10 levels after the confirmatory scorecard (WC-10i), making WC-10 the successor to WC-08's gate? _Recommended: Yes, only for levels whose gate passed in WC-10i, each labelled modelled with the disclaimer._
- **DD-WC21** (blocks `WC-10h`) — OWNER GATE: sign the WC-10 confirmatory registration (WC-10g), commit it alone, record its SHA-256 here, and say yes to one run on 2024-25?
- **DD-WC23** (blocks `WC-10e`) — Amendment B2: rows with missing tyre_life are left out of step 1 (design A and lap arm), counted under their own reason, with the parameter layout (registration 6d) computed AFTER the drop. Draft B2, commit it alone, record its SHA-256 here. _Recommended: Layout AFTER the drop (the layout then describes the data actually fitted)._
- **DD-WC24** (blocks `WC-10e`, `WC-10f`, `WC-10g`, `WC-10h`, `WC-10i`, `WC-10j`, `WC-10k`, `WC-10l`, `WC-10m`) — Resume the paused WC-10 chain (WC-10e to WC-10l and the WC-10m fallback)?

### Watch list — kept an eye on, not tasks and not rulings

_Generated from the watch rules in [`build-log.json`](build-log.json) (`watch_rules`); watch entries update automatically as items land or decisions resolve. A rule whose trigger needs something the log cannot see (a commit, a re-export, a rebuild, your ruling) stays open until its `resolved` and `resolution` are recorded._

**8 open** (0 ship-blockers). Full detail: `python3 _roadmap/_wake-calibration/status/board.py --watch`. `python3 _roadmap/_wake-calibration/status/board.py --ship` exits 1 while a ship-blocker is open.

Each watch rule is tagged with the recommended model (haiku/sonnet/opus) for token efficiency (2 haiku, 4 sonnet, 2 opus). The tag is the smallest model that can work the rule to its `clears_when`; step up a tier the moment the rule turns out to leave a choice open that the tag assumed was made.

- **`haiku`** — Maps to haiku-4-5. A binary check, or recording a resolution the evidence or the user has already settled: is it committed, did the named tests pass on the rebuild, write down the accept. The output has a mechanical check (a test result, a file list, git log).
- **`sonnet`** — Maps to sonnet-5. The fix or the options are written down in the rule: pick between two named options, run a named rebuild or export and check the pages, review a diff, reconcile counts, reword text to a meaning already settled.
- **`opus`** — Maps to opus-5 (fable-5.1 if the rule turns into a new estimator). Rules on a trade-off, designs the fix, audits a decision, or turns a measurement into a claim: label-moving changes, leakage boundaries, gate runs before a promotion.

| ID | Kind | Item | Model | What | Clears when |
| :--- | :--- | :--- | :--- | :--- | :--- |
| W2 | hazard | WC-06 | `sonnet` | No archived dirty-air (DA-03) number may appear in the product, as a fallback or otherwise | WC-06 has landed and its tests show no old-method value in any app output. |
| W8 | hazard | WC-10h, DD-WC21 | `opus` | 2024-25 are sealed: no 2024-25 outcome is read, and no cut point or gate changes after the confirmatory registration is hashed | DD-WC21 is resolved and WC-10h has landed. |
| W11 | hazard | WC-10k | `sonnet` | No archived dirty-air (DA-03) number in any WC-10 output, as a fallback or otherwise | WC-10k has landed and its grep test shows no DA-03 value or identifier. |
| W16 | hazard | WC-11 | `sonnet` | Placeholder wake values must never become an ML feature or target, or be labelled measured | The placeholder seed is replaced by calibrated values and value_kind is no longer placeholder. |
| W13 | uncommitted | WC-10a | `haiku` | WC-10 plan, its review note and the WC-10 entries in this log live only in the working tree | The owner commits them, or rules them out. |
| W17 | uncommitted | WC-11 | `haiku` | WC-11 seed, model, tests, app page, docs and this log's pause entries live only in the working tree | The owner commits them, or rules them out. |
| W15 | stale-artifact | WC-10e | `sonnet` | Pre-fix SG partial results are not valid evidence | SG1-SG7 are re-run after B2 and the code fix, and the pre-fix files are marked superseded. |
| W14 | gate-gap | WC-10e | `opus` | run_wc10 real mode does not check that SG1-SG7 passed or that B1/B2 are committed | run_wc10 real mode refuses without them, with a test. |

<!-- END GENERATED TASKS -->
