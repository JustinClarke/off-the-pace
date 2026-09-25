# Fixes build order — rules, and the ordered task list

**State lives in [`build-log.json`](build-log.json), and only there.** This file holds the
rules that govern it, plus one **generated** task list spliced in at the bottom.

This is the same mechanism as [`../../_improvements/status/BUILD-ORDER.md`](../../_improvements/status/BUILD-ORDER.md),
applied to the audit fixes in [`../`](../README.md). The differences are listed at the end.

A hand-written checklist in this file is a defect. The task list below is *derived* from the
JSON by `board.py --write-order`, sits between two markers, and `--check` fails if it has
fallen out of sync with the log. Edit the JSON, then regenerate. Never type into the block.

```bash
python3 _roadmap/_fixes/status/board.py                # the board, open decisions, next command
python3 _roadmap/_fixes/status/board.py --check        # invariants only; exit 1 on failure
python3 _roadmap/_fixes/status/board.py --order        # the ordered task list, to stdout
python3 _roadmap/_fixes/status/board.py --write-order  # ...and spliced into this file
python3 _roadmap/_fixes/status/board.py --watch        # the watch list in full
python3 _roadmap/_fixes/status/board.py --ship         # exit 1 while a ship-blocker is open
```

**Quick start:** say `proceed` to spawn an agent on the current pointer item and skip all
explanation. Two exceptions, both from the improvements tree's experience:

1. **A decision blocks the pointer item.** If the item is `BLOCKED` on an open `FD*` decision,
   stop and put the decision to the human first, in plain language with the options
   translated. Spawning blind spends the item's full cost against the wrong premise.
2. **The pointer item is already `MEASURED`.** Don't respawn it: read the last history
   entry's `next_action`, and let the user pick the next item.

`board.py` never writes to the log — a malformed edit surfaces as a failed check, not as silent
drift. `--write-order` writes only to this file and refuses to run while the log is invalid.
Run `--check` after every edit to the JSON.

## What the log holds

| Key | Holds |
| :--- | :--- |
| `pointer` | The single next item to run. Exactly one, always (or `null` when everything is terminal). |
| `stage_vocabulary` | The six legal stages and what each means. |
| `model_vocabulary` | The four Claude models an item may name, and when each is the right one. |
| `groups` | The improvements-tree group each item belongs to (`ref` points at that group's leaf doc). |
| `items` | `id`, `group`, `stage`, `depends_on`, `title`, `findings`, `doc`, `cost`, `model`, `note`, and `closed` for terminal items. |
| `decisions` | `FD*` rulings awaiting a human call. Referenced by an item's `blocked_by_decision` (one id or a list). |
| `watch_vocabulary` | The nine kinds of watch entry and what each means. |
| `watch` | What is being kept an eye on that is neither an item nor a ruling: ship-blockers, standing hazards, uncommitted or unreviewed work, unverified claims, stale artifacts, gate gaps, known debt. Each has `id`, `kind`, `title`, `detail`, `clears_when`, `status`, and an optional `item` / `decision`. |
| `history` | Append-only session records, in handoff-protocol shape. |

## Items, and how they map to the WI docs

Each item points at the WI doc in [`../wi/`](../wi/) that carries its method, acceptance, tests
and definition of done (`doc`), and lists the audit findings it fixes (`findings`). The
per-finding verdicts and the F50–F55 write-ups are in [`../reference/`](../reference/). Four WI docs are executed as
two items each, because part of the doc is blocked and part is not:

| WI doc | Item | Findings | Why split |
| :--- | :--- | :--- | :--- |
| `WI-02` | `WI-02a` | F41, F7, F39 | Provenance first; no ruling needed. |
| | `WI-02b` | F2, F9 | The refit needs `FD3`, `WI-02a` and `WI-05`. |
| `WI-09` | `WI-09` | F13, F14, F17, F18, F19, F20, F54 | Landed 2026-09-25; keeps the doc's id. |
| | `WI-09b` | F12 | Split after the build: what "cleared" means is a ruling (`FD6`). |
| `WI-14` | `WI-14a` | F50, F28, F46 | Independent of the F40 ruling. |
| | `WI-14b` | F40, F44, F45 | The chain that `FD5` gates. |
| `WI-15` | `WI-15a` | F43, F48 (coding) | `WI-01`'s θ_air re-estimate needs F48's coding first. |
| | `WI-15b` | F47, F49 | Thermal; does not feed θ_air. |

Everything else is one item per doc, id = the doc's `WI-NN`.

## Stages

- **SPEC** — reverified and specced in its WI doc. Nothing run.
- **BUILDING** — in progress.
- **MEASURED** — fix applied and its acceptance numbers exist; the orchestrator has not yet
  re-run the doc's definition of done.
- **LANDED** — definition of done re-run by the orchestrator and passing, **in the working
  tree**. Committing or publishing is the user's call and is not part of the stage.
- **BLOCKED** — waiting on an open decision (or a dependency that hit a problem). A plain unmet
  dependency is not `BLOCKED`; dependency order already handles that.
- **CLOSED** — terminal, with the reason recorded. Do not re-open without new evidence.

There is no `GATED` stage here. The improvements tree needs one because a *number* has to pass
[`gates.md`](../../_improvements/foundations/gates.md) before it can be claimed. A fix's gate is its
WI doc's definition of done — the audit's `verify_findings.py` check flipping to CLEARED plus
the new T-tests passing — and that is what `LANDED` means. The exception is a fix that moves a
feature contract or the label (`WI-01`, `WI-15a`, `WI-15b`, `WI-02b`): those also owe the gate,
and the item's `landed` history entry must say which gate steps were run.

## Rules

**Changing a stage.** Only when the WI doc's criteria for that stage are met. Stages move
forward, or back to `BLOCKED` with a logged reason — never silently sideways.

**Which model.** Every live item names one from `model_vocabulary`, and `--check` rejects a
live item without one. `opus-5` is the default; `sonnet-5` is a step down where the WI doc has
already made the judgment call; `fable-5.1` is a step up where the failure mode is a
plausible-looking number rather than an error. The choice belongs to the item, not the session.

**Running an item is a delegation, not a switch.** The interactive session orchestrates and
does not execute a live item itself. It spawns an agent at the item's own `model` to do the
work, then reviews what comes back **before touching the log**: re-reads the diff, re-runs the
WI doc's definition of done and `board.py --check`, and only then records the result. An
agent's summary describes what it intended, not necessarily what it produced. A stage only
advances once the orchestrator has checked the work independently. Expect the WI doc's own
text to need correcting where the result disproves it — see *Deviation* below.

**Order.** Dependency order. `board.py` prints unmet blockers after each item; don't start one
that shows any. Among items that are ready, the task list puts work you can run now ahead of
work waiting on one of your rulings.

**One `▶`.** `pointer` names exactly one non-terminal item. `--check` enforces it.

**Every session appends one `history` entry** with all six fields — `landed`, `verified`,
`assumed`, `gates_run`, `next_command`, `next_action`. `--check` fails if any is missing on the
latest entry. `verified` and `assumed` are the hard epistemic line from
[`epistemics.md`](../../_improvements/foundations/epistemics.md): only `verified` if the code path was
traced and the number can be cited.

**The watch list is where an exception lives.** Items say what to build and decisions say what
to rule; anything else a session leaves behind (an artifact that is now stale, work that is
uncommitted or unreviewed, a claim run in one place only, a gate that does not guard, a known
defect left on purpose, a trap someone could step on) gets a `watch` entry with a `clears_when`,
so it cannot fall off the board when the item that raised it lands. Prose in `assumed` or
`next_action` is not tracked by anything. A resolved entry is marked `RESOLVED` with a date and a
resolution, never deleted. `--check` validates the shape only; `--ship` is the gate to run before
publishing, and fails while a `ship-blocker` is open. The generated task list below carries the
open entries.

**Deviation from a WI doc is logged _and_ the doc corrected**, so the log never silently
diverges from the spec.

**Nothing is committed without being asked.** Standing rule for this repo. `LANDED` means the
change is in the working tree and verified; the human commits.

### What is different from an improvements item

Fixes edit production code (`transform/`, `ml/`, `app/`), so the improvements tree's
"probes never touch the warehouse or `ml/models/`" is narrowed rather than copied:

- **Ad hoc probes are still throwaway** — scratchpad only, `data/dev.duckdb` opened read-only.
- **Fix work edits the working tree.** Rebuilding the dev warehouse (`dbt build`) or a model is
  in scope only where the WI doc's definition of done requires it, and the item's `landed`
  entry says so. Never touch `data/ci.duckdb`.
- **Until `WI-07` lands, do not run `ml.src.features --check`** (it is what `Makefile:195` and
  CI call). It has no read-only mode: it rewrites the shipped `ml/models/encoders.json` from
  whatever the holdout resolver returns (F11/F53). `WI-07` adds `--persist-encoders`, default
  off.
- **`WI-04` must land before the v14 manifest is published to the CDN.** The CDN serves v11
  today; publishing v14 first breaks the Degradation Simulator for everyone.

## Adding an item

Append to `items` with a unique `id`, a `group` that exists, `stage: "SPEC"`, real `depends_on`
ids, `findings`, a `doc` that exists, a `cost` and a `model` — `--check` rejects a live item
missing any of those, and rejects a `doc` path that does not resolve. Then make sure the WI
doc has a definition of done for it.

---

## The ordered task list

Dependencies first, then work you can run now ahead of work waiting on a ruling, then group
order, then id. Read it top-down: it is the sequence in which the items are actually runnable.

<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-09-25T12:28:00Z`. Run `python3 _roadmap/_fixes/status/board.py --write-order` after any edit to the log._

**11 live items** (5 blocked). The pointer is on **WI-15a** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 6 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Fixes | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | [WI-15a](../wi/WI-15-traffic-thermal-feature-semantics.md) ▶ | 02 | SPEC | 1d | `opus-5` | F43, F48 (coding) | Traffic feature semantics: pit-lane cars are not traffic (F43); dirty-air coding monotone in the gap (F48) | — |
| 2 | [WI-15b](../wi/WI-15-traffic-thermal-feature-semantics.md) | 02 | SPEC | 1-2d | `opus-5` | F47, F49 | Thermal feature semantics: fuel-neutral push proxy (F47), reachable surface/bulk ratio (F49) | — |
| 3 | [WI-11](../wi/WI-11-fan-page-truth-pass.md) | 06 | SPEC | 1-2d | `opus-5` | F15, F16, F27, F29, F30, F36, F37 | Fan-page truth pass: pages must state what their SQL computes | — |
| 4 | [WI-14a](../wi/WI-14-rating-chain.md) | 06 | SPEC | 0.5-1d | `sonnet-5` | F50, F28, F46 | Sign-convention truth pass: Synthetic Teammate verdict (F50), the F28 page, Hidden Performance (F46) | — |
| 5 | [WI-03](../wi/WI-03-holdout-policy.md) | 12 | BLOCKED | 0.5d | `sonnet-5` | F4, F20 (card summary) | Holdout policy: pin a season that can hold rows, retire the tautological test | **FD4** (human call) |
| 6 | [WI-01](../wi/WI-01-label-spine.md) | 08 | BLOCKED | 2-3d | `fable-5.1` | F1, F5, F22, F23, F35, F38, F42, F48 (θ), F51 | Label spine: one version bump for F1, F22, F23, F35, F38, F42, F5, F48(θ), F51 | WI-15a, **FD1** (human call), **FD2** (human call) |
| 7 | [WI-02b](../wi/WI-02-compound-seed-provenance.md) | 08 | BLOCKED | 2-3d | `opus-5` | F2, F9 | Compound seed refit under the FD3 ruling, plus F9 eligibility decoupling | **FD3** (human call) |
| 8 | [WI-09b](../wi/WI-09-cleanup-bundle.md) | 08 | BLOCKED | 0.5d | `opus-5` | F12 | F12: what to do about 2018 laps with no telemetry being recorded as clear air | **FD6** (human call) |
| 9 | [WI-08](../wi/WI-08-qualifying-chain.md) | 02 | SPEC | 0.5-1d | `opus-5` | F10 | Qualifying chain stops reading race-day data | WI-02b |
| 10 | [WI-12](../wi/WI-12-06b-remeasure.md) | 06 | SPEC | 0.5-1d | `opus-5` | F23, F48 (θ) | 06b re-measure after the label bump | WI-01 |
| 11 | [WI-14b](../wi/WI-14-rating-chain.md) | 06 | BLOCKED | 1-2d | `opus-5` | F40, F44, F45 | Rating chain: equal-car rating symmetry (F40), affinity as deviation (F44), era offset (F45) | **FD5** (human call) |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **FD1** (blocks `WI-01`) — What is the baseline each lap is compared against? A: a neutral reference - fuel AND tyre-compound effects taken out once, and track rubber/temperature NOT taken out a second time. B: what the field actually did that day, with nothing subtracted again. _Recommended: A (the reverification's recommendation)._
- **FD2** (blocks `WI-01`) — What happens to safety-car / VSC / red-flag / restart laps (9,016 of 139,947 eligible training rows, 6.4%) at training time? Exclude them outright, or keep them at reduced weight via correction_weight (computed today, applied nowhere in ml/src)? _Recommended: Orchestrator's read, not the audit's: exclude. Those laps are slow because the field is queueing behind the safety car, not because tyres wore, so a reduced weight still trains on a label that is not degradation._
- **FD3** (blocks `WI-02b`) — Compound-seed leakage: refit the seed point-in-time (each season fitted only on earlier seasons), or declare a same-race exemption and make training match serving? _Recommended: Orchestrator's read, not the audit's: point-in-time - it is what the model does at serving time and follows int_sc_hazard_history's precedent - accepting the stint-life cost knowingly, since D5 tunes against that family._
- **FD4** (blocks `WI-03`) — Which season is the holdout? No completed season is unspent (2025 was consumed as a selection fold by 02c's admission gate). Pin 2026 explicitly and fill it with the races run so far, or declare that no clean holdout exists yet? _Recommended: Orchestrator's read, not the audit's: pin holdout_season = 2026 in config, state holdout_populated: false until 2026 rows exist, and ingest the 2026 races already run if the data is available - the only option that yields a clean holdout rather than a declared absence._
- **FD5** (blocks `WI-14b`) — Equal-car teammate rating: compare P20 against P20 (keeps the 'kill cruise drag' ceiling logic, applied on both sides), or median against median (simpler, loses the ceiling)? _Recommended: P20-vs-P20 (the WI doc's recommendation): the smaller conceptual change, and it preserves the model header's stated intent._
- **FD6** (blocks `WI-09b`) — About 9% of 2018 laps (about 1,450 training rows) have no telemetry, and the pipeline records them as 'clear air, no traffic', a guess presented as a measurement. What should 'fixed' mean? A: keep the guess, guard it with a per-season check (WI-07's T15). B: record 'unknown' (NULL) instead of the guess. C: drop those laps from training. _Recommended: Orchestrator's read: B, folded into WI-01's bump, plus A's guard now (WI-07's T15) so it cannot regress meanwhile._

### Watch list — kept an eye on, not tasks and not rulings

**17 open** (1 ship-blocker). Full detail: `python3 _roadmap/_fixes/status/board.py --watch`. `python3 _roadmap/_fixes/status/board.py --ship` exits 1 while a ship-blocker is open.

| ID | Kind | Item | What | Clears when |
| :--- | :--- | :--- | :--- | :--- |
| W1 | ship-blocker | WI-13 | Re-export int_pit_strategy_value to app/public/data before the pit-strategy change ships | The parquet is re-exported (the user's call, it rewrites tracked files) and the page is checked against the committed data. |
| W3 | uncommitted | — | WI-02a, WI-13 and WI-09 are landed but uncommitted | The user commits them. |
| W4 | unreviewed | — | Ingestion-hardening agent's partial work is in the working tree, unread and untested | The diff is reviewed and ingestion/tests pass and the change is kept, or the changes are discarded (git checkout on the modified paths plus deleting the four new files; destructive, the user's call). |
| W5 | unverified | WI-09 | WI-09's new tests and one source form have only run on the dev target | A CI-target build runs them (not done: this tree does not touch data/ci.duckdb). |
| W6 | stale-artifact | WI-09 | Dev-warehouse marts stale for WI-09's changes until rebuilt | dbt run on those three marts (or the next full dbt build). |
| W7 | stale-artifact | WI-07 | Drift baselines need regenerating from a CI build | Either: (1) WI-09's fixture data issues are resolved (dbt_expectations test passes on CI; assert_raw_laps_race_depth_is_race_only finds matching bronze parquets), then `dbt build --target ci` and `make lint-oracle-snapshot` complete successfully and the result is committed; OR (2) a design decision is made to pin the fixture to a pre-schema-change baseline (smaller cost, eventual debt). |
| W8 | stale-artifact | — | Generated docs still carry old text | Docs are regenerated in one sweep once the landed items are committed. |
| W9 | pending-ruling | — | Do the 08f-1 and 08o gate results need a note about 2018 weights? | The user decides: add a note to those gate results, or re-run them. |
| W10 | pending-ruling | WI-13 | What value should long-stint tail cells get in survival_weight? | The user picks 1.0 or the 4.0 cap, if IPW is revived. |
| W11 | pending-ruling | WI-13 | Opportunity cost for a stint the model cannot grade: 0.0 or NULL? | The user rules; the allowlist entries are closed one way. |
| W12 | pending-ruling | WI-02a | Does WI-02a's 2025 movement owe the gate? | The user agrees to defer, or asks for the gate now. |
| W17 | gate-gap | WI-07 | The sqlfluff gate does not hold | The size limit is raised or the skip is made loud, and the failing files are fixed or excluded on purpose. |
| W13 | debt | WI-09 | F17: pu_family is keyed on the team name, so every rename needs a hand-added row | The user asks for the entity-keyed rewrite (needs its own item), or accepts the name list plus the warn test. |
| W14 | debt | WI-09 | constructor_power_pace_index_final and constructor_aero_pace_index_final are the same column | The user picks drop or relabel. |
| W15 | debt | WI-13 | WI-13's neighbours, found and not fixed | Each is given an item or an explicit 'accept', one at a time. |
| W18 | debt | WI-09 | 2020_1 (Austrian GP) lap numbering is wrong in bronze | 2020_1 is re-pulled from FastF1 and re-checked (whether a re-pull fixes it is untested). |
| W19 | debt | FD4 | 2026 races are not ingested | FD4 is ruled, the seeds are filled (WI-05's gate lists what is missing) and the rounds are ingested. |

<!-- END GENERATED TASKS -->
