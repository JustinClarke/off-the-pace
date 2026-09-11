# Build order — rules, and the ordered task list

**State lives in [`build-log.json`](build-log.json), and only there.** This file holds the
rules that govern it, plus one **generated** task list spliced in at the bottom.

**A hand-written checklist in this file is still a defect.** The rule has not been relaxed —
it has been made enforceable. The task list below is *derived* from the JSON by
`board.py --write-order`, sits between two markers, and `--check` fails if it has fallen out
of sync with the log. So it cannot drift the way a typed list would: either it matches the
log or the checker stops you. Edit the JSON, then regenerate. Never type into the block.

```bash
python3 _improvements/status/board.py                # the board, open decisions, next command
python3 _improvements/status/board.py --check        # invariants only; exit 1 on failure
python3 _improvements/status/board.py --order        # the ordered task list, to stdout
python3 _improvements/status/board.py --write-order  # ...and spliced into this file
```

**Quick start:** Say `proceed` to spawn an agent on the current pointer item and skip all explanation. That's it.

`board.py` never writes to the log — it is a reader, so a malformed edit surfaces as a failed
check rather than as silent drift. `--write-order` writes only to this file, and refuses to
run at all while the log is invalid. Run `--check` after every edit to the JSON.

## What the log holds

| Key | Holds |
| :--- | :--- |
| `pointer` | The single next item to run. Exactly one, always. |
| `stage_vocabulary` | The eight legal stages and what each means. |
| `model_vocabulary` | The four Claude models an item may name, and when each is the right one. |
| `groups` | Work-item groups, each mapping to one leaf doc in [`../work/`](../work/). |
| `items` | `id`, `group`, `stage`, `depends_on`, `title`, `note`, `cost`, `model`, and `closed` for terminal items. |
| `decisions` | Items awaiting a human call. Referenced by `blocked_by_decision`. |
| `history` | Append-only session records, in handoff-protocol shape. |

## Stages

A research item does not have two states. `CLOSED` is a result, not a failure — a
measurement that comes back "not viable" is the programme working, and recording it with its
reason is what stops a later session re-opening it. The vocabulary is in the JSON; the rule
about it is here:

**A number that has not been through [`../foundations/gates.md`](../foundations/gates.md) is
`MEASURED`, never `GATED`, however good it looks.** That is the line the whole tree exists to
hold.

## Rules

**Changing a stage.** Only when the leaf doc's criteria for that stage are met. Stages move
forward, or back to `BLOCKED` with a logged reason — never silently sideways.

**Which model.** Every live item names one, drawn from `model_vocabulary`, and `--check`
rejects a live item without one — the same treatment `cost` gets, for the same reason: it is
part of what running the item costs. `opus-5` is the default. `sonnet-5` is a step down, taken
only where the leaf doc has already made the judgment call and what remains is execution;
`fable-5.1` is a step up, taken where the failure mode is a plausible-looking number rather
than an error. The choice belongs to the item, not to the session — a step down that was right
for one item is not a licence for the next, and a model that turned out to be the wrong call
gets corrected in the log like any other field.

**Running an item is a delegation, not a switch.** The interactive session orchestrates at
whatever model it happens to be running — by standing convention, `haiku-4-5` — and does not
execute a live item itself. It spawns an agent at the item's own `model` field to do the work,
then reviews what comes back before touching the log: re-reads the diff, re-runs the leaf
doc's definition of done and `board.py --check`, and only then records the result. The agent's
own summary of what it did is not verification — an agent's report describes what it intended,
not necessarily what it produced. A stage only advances once the orchestrating session has
checked the work independently, the same way any other tool output gets checked before it is
trusted.

**Order.** Dependency order. `board.py` prints unmet blockers after each item; don't start
one that shows any. A group marked `parallel` has no dependency on the ML ladder and may run
at any time.

**One `▶`.** `pointer` names exactly one non-terminal item. `--check` enforces it.

**Every session appends one `history` entry** with all six fields — `landed`, `verified`,
`assumed`, `gates_run`, `next_command`, `next_action`. `--check` fails if any is missing on
the latest entry. `verified` and `assumed` are the hard epistemic line from
[`../foundations/epistemics.md`](../foundations/epistemics.md): only `verified` if the code
path was traced and the number can be cited.

**Deviation from a leaf doc is logged _and_ the leaf doc corrected**, so the log never
silently diverges from the spec.

**Ad hoc probes are throwaway** — scratchpad only, never committed, and they must not touch
`ml/models/*.json`, warehouse data, or git state. Reuse the production paths
(`ml/src/{train,features,evaluate,attribution,intervals}.py`) rather than reimplementing
fit/score/CV logic.

**Nothing is committed without being asked.** Standing rule for this repo.

## Adding an item

Append to `items` with a unique `id` inside an existing `group`, `stage: "SPEC"`, real
`depends_on` ids, a `cost`, and a `model` — `--check` rejects a live item missing either of
the last two. Then write or extend the group's leaf doc so the item has a definition of done. An item with no leaf doc
section is not runnable, and the checker cannot catch that for you.

---

## The ordered task list

Dependencies first, then the ladder's group order, then id. Read it top-down: it is the
sequence in which the items are actually runnable. `parallel` groups sink to the bottom
because nothing on the ladder waits for them, not because they matter less.

<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-09-11`. Run `python3 _improvements/status/board.py --write-order` after any edit to the log._

**26 live items** (1 blocked). The pointer is on **02d** — that is the one to run next; the rest of the order is what becomes runnable after it. 21 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json) for why each one ended as it did.

| # | Item | Group | Stage | Cost | Model | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `05c` | [05](../work/05-model-family.md) | MEASURED | 1-2d | `opus-5` | GPBoost variance-components probe - measurement only, ships nothing | — |
| 2 | `08d` | [08](../work/08-foundations-repair.md) | MEASURED | 0d | `opus-5` | Real Pirelli C1-C5 compound identity per race (2019-present), hand-sourced from press.pirelli.com | — |
| 3 | `08e` | [08](../work/08-foundations-repair.md) | GATED | 1-2d | `opus-5` | Thermal-proxy stint baseline reaches forward - rebuild as a trailing window | — |
| 4 | `08f` | [08](../work/08-foundations-repair.md) | GATED | 2-3d | `opus-5` | Cross-season pooled statistics in the feature lineage - season-lag or rule | — |
| 5 | `08h` | [08](../work/08-foundations-repair.md) | MEASURED | 0.5d | `opus-5` | baseline_observations_n as a feature - the add-ablation 08e deferred | — |
| 6 | `08i` | [08](../work/08-foundations-repair.md) | GATED | 1-2d | `opus-5` | The min_observations floor - the trade 08e priced and did not take | — |
| 7 | `04a` | [04](../work/04-campaign-audit.md) | MEASURED | 1d | `sonnet-5` | Enumerate the real test family | — |
| 8 | `10b` | [10](../work/10-competing-risks.md) | MEASURED | days | `opus-5` | Cause-specific AFT arm - non-green endings treated as censored | — |
| 9 | `10c` | [10](../work/10-competing-risks.md) | MEASURED | days | `fable-5.1` | Competing-risks evaluation, with the dependent-censoring caveat stated | 10b |
| 10 | `10d` | [10](../work/10-competing-risks.md) | MEASURED | 1-2d | `opus-5` | Fix the stint-life calibration defect - the model over-predicts tyre life | 10c |
| 11 | `10e` | [10](../work/10-competing-risks.md) | MEASURED | 1-2d | `opus-5` | Re-tune stint_life_regressor under the honest split and a non-mixture metric | 10d |
| 12 | `02b` | [02](../work/02-feature-expansion.md) | SPEC | 1d | `sonnet-5` | Tier 1 - qualifying | 10e |
| 13 | `02c` | [02](../work/02-feature-expansion.md) | MEASURED | 2-3d | `opus-5` | Tier 2 - corner-level driver inputs | — |
| 14 | `02d` ▶ | [02](../work/02-feature-expansion.md) | SPEC | 1d | `opus-5` | Tier 3 - SC hazard, with the expanding-window rebuild | — |
| 15 | `02g` | [02](../work/02-feature-expansion.md) | GATED | 0.5-1d | `opus-5` | Rebuild the corner field median as a trailing window | — |
| 16 | `03a` | [03](../work/03-driver-vs-car.md) | SPEC | 1d | `sonnet-5` | Mover panel; exclude the Force India rename; confirm the connected set survives | — |
| 17 | `03b` | [03](../work/03-driver-vs-car.md) | SPEC | 2d | `sonnet-5` | Jolpica ingest 2011-2017 | — |
| 18 | `03c` | [03](../work/03-driver-vs-car.md) | BLOCKED | 1-2w | `fable-5.1` | AKM two-way FE on degradation slope + Kline-Saggio-Solvsten leave-out | 03a, 03b |
| 19 | `05a` | [05](../work/05-model-family.md) | SPEC | days-weeks | `opus-5` | GBT vs hierarchical / GAM | — |
| 20 | `05d` | [05](../work/05-model-family.md) | SPEC | 1-2d | `opus-5` | The training window - is a proper subset of seasons better than all of them? | — |
| 21 | `07b` | [07](../work/07-causal-pit-timing.md) | SPEC | 1-2w | `fable-5.1` | The IV estimator, with the exclusion restriction argued per outcome | — |
| 22 | `06a` | [06](../work/06-publication.md) | SPEC | 1d | `sonnet-5` | Pit-timing tail, by constructor | — |
| 23 | `06b` | [06](../work/06-publication.md) | SPEC | 1-2d | `opus-5` | Dirty-air coefficient per season - the 2022 regulation question | — |
| 24 | `06c` | [06](../work/06-publication.md) | SPEC | 1d | `opus-5` | Corner-phase skill, incl. the Verstappen braking anomaly | — |
| 25 | `11a` | [11](../work/11-parallel-surfaces.md) | SPEC | 1-2d | `opus-5` | Mondrian-conformal recalibration of the degradation band, keyed on circuit | — |
| 26 | `11b` | [11](../work/11-parallel-surfaces.md) | SPEC | days | `opus-5` | Assemble the stochastic DP over pit timing | — |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **D2** (blocks nothing) — CDN publish / app deploy - v11 is committed but production still serves v6.
- **D3** (blocks nothing) — Land 08e + 08f? It supersedes the published v11 headline on all five targets.
- **D4** (blocks nothing) — Land 10d's capacity fix (max_depth 8 -> 3, or 2) now, or wait for 10e's re-search?

<!-- END GENERATED TASKS -->
