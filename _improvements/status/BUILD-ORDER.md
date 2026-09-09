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

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-09-09`. Run `python3 _improvements/status/board.py --write-order` after any edit to the log._

**27 live items** (5 blocked), **14 terminal**. The pointer is on **08g** — that is the one to run next; the rest of the order is what becomes runnable after it.

| # | Item | Group | Stage | Cost | Model | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `05c` | [05](../work/05-model-family.md) | MEASURED | 1-2d | `opus-5` | GPBoost variance-components probe - measurement only, ships nothing | — |
| 2 | `08c` | [08](../work/08-foundations-repair.md) | SPEC | hours | `sonnet-5` | Two silent assumptions, written down | — |
| 3 | `08d` | [08](../work/08-foundations-repair.md) | SPEC | 1-2d | `opus-5` | Real Pirelli C1-C5 compound identity per race (2019-present), hand-sourced from press.pirelli.com | — |
| 4 | `08e` | [08](../work/08-foundations-repair.md) | GATED | 1-2d | `opus-5` | Thermal-proxy stint baseline reaches forward - rebuild as a trailing window | — |
| 5 | `08f` | [08](../work/08-foundations-repair.md) | GATED | 2-3d | `opus-5` | Cross-season pooled statistics in the feature lineage - season-lag or rule | — |
| 6 | `08g` ▶ | [08](../work/08-foundations-repair.md) | SPEC | 1d | `opus-5` | Decompose the 08e/08f regression on the BEFORE substrate; rule cliff_candidate_flag dead or damaged | — |
| 7 | `09b` | [09](../work/09-scoring-instruments.md) | SPEC | 0.5d | `fable-5.1` | e-value pre-registration per arm, and campaign-level e-BH | — |
| 8 | `04a` | [04](../work/04-campaign-audit.md) | SPEC | 1d | `sonnet-5` | Enumerate the real test family | — |
| 9 | `04c` | [04](../work/04-campaign-audit.md) | SPEC | 0.5d | `sonnet-5` | Apply BH (or BY) at campaign level; report which CLEARS survive | — |
| 10 | `10b` | [10](../work/10-competing-risks.md) | BLOCKED | days | `opus-5` | Cause-specific AFT arm - non-green endings treated as censored | 09b |
| 11 | `10c` | [10](../work/10-competing-risks.md) | BLOCKED | days | `fable-5.1` | Competing-risks evaluation, with the dependent-censoring caveat stated | 10b |
| 12 | `02b` | [02](../work/02-feature-expansion.md) | SPEC | 1d | `sonnet-5` | Tier 1 - qualifying | — |
| 13 | `02d` | [02](../work/02-feature-expansion.md) | SPEC | 1d | `opus-5` | Tier 3 - SC hazard, with the expanding-window rebuild | — |
| 14 | `02g` | [02](../work/02-feature-expansion.md) | SPEC | 0.5-1d | `opus-5` | Rebuild the corner field median as a trailing window | — |
| 15 | `02c` | [02](../work/02-feature-expansion.md) | BLOCKED | 2-3d | `opus-5` | Tier 2 - corner-level driver inputs | 02g |
| 16 | `03a` | [03](../work/03-driver-vs-car.md) | SPEC | 1d | `sonnet-5` | Mover panel; exclude the Force India rename; confirm the connected set survives | — |
| 17 | `03b` | [03](../work/03-driver-vs-car.md) | SPEC | 2d | `sonnet-5` | Jolpica ingest 2011-2017 | — |
| 18 | `03c` | [03](../work/03-driver-vs-car.md) | BLOCKED | 1-2w | `fable-5.1` | AKM two-way FE on degradation slope + Kline-Saggio-Solvsten leave-out | 03a, 03b |
| 19 | `05a` | [05](../work/05-model-family.md) | SPEC | days-weeks | `opus-5` | GBT vs hierarchical / GAM | — |
| 20 | `05d` | [05](../work/05-model-family.md) | SPEC | 1-2d | `opus-5` | The training window - is a proper subset of seasons better than all of them? | — |
| 21 | `07a` | [07](../work/07-causal-pit-timing.md) | SPEC | hours | `opus-5` | Feasibility - does the first stage survive conditioning? | — |
| 22 | `07b` | [07](../work/07-causal-pit-timing.md) | BLOCKED | 1-2w | `fable-5.1` | The IV estimator, with the exclusion restriction argued per outcome | 07a |
| 23 | `06a` | [06](../work/06-publication.md) | SPEC | 1d | `sonnet-5` | Pit-timing tail, by constructor | — |
| 24 | `06b` | [06](../work/06-publication.md) | SPEC | 1-2d | `opus-5` | Dirty-air coefficient per season - the 2022 regulation question | — |
| 25 | `06c` | [06](../work/06-publication.md) | SPEC | 1d | `opus-5` | Corner-phase skill, incl. the Verstappen braking anomaly | — |
| 26 | `11a` | [11](../work/11-parallel-surfaces.md) | SPEC | 1-2d | `opus-5` | Mondrian-conformal recalibration of the degradation band, keyed on circuit | — |
| 27 | `11b` | [11](../work/11-parallel-surfaces.md) | SPEC | days | `opus-5` | Assemble the stochastic DP over pit timing | — |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **D2** (blocks nothing) — CDN publish / app deploy - v11 is committed but production still serves v6.
- **D3** (blocks nothing) — Land 08e + 08f? It supersedes the published v11 headline on all five targets.

### Terminal

- `00a` **LANDED** — Feature count is 33, not 24, everywhere it is quoted (landed)
- `00b` **LANDED** — Falsify research_program 1a's 'no SC signal exists' claim (landed)
- `00c` **LANDED** — LORO leakage ruling - barred; 'LORO' was leave-one-DRIVER-out, not leave-one-race-out (landed)
- `04b` **CLOSED** — Decide the floor-ratio to p-value conversion (2026-09-07)
- `01a` **LANDED** — Learning curves - loss vs training-set size, extrapolated (landed)
- `01b` **CLOSED** — Empirical noise floor - difference-based, stratified, bracketed (CLOSED 2026-09-09 as a completed measurement, not as a failure. Every clause of the definition of done was delivered: the synthetic recovery passed at the claimed shape (sigma^2 -1.98% +/- 2.14%, end-to-end p50 floor +3.4%), the admissible-neighbour distance was measured (median 4.275 vs 6.829 for random pairs, ratio 0.626, distribution nowhere near zero), the floor was published as a bracket with the metric, NaN treatment and weighting rule stated, the falsification gate was checked at all 18 ladder x quantile points and every violation reported as an instrument failure, and the result was reconciled against 01a. THE ANSWER IS THAT THE INSTRUMENT DOES NOT BIND on p10 or p50: at the three-coordinate headline level the floor comes back ABOVE the loss it is meant to bound (0.5654 vs 0.5188; 1.0641 vs 1.0163). The mechanism is measured, not guessed -- the conditioning ladder is still falling at L3 (-10.4% to L4, a further -13.3% to L5), so the residual mean-function bias at three matched coordinates is larger than the headroom being resolved. R1's dimension constraint therefore binds harder than it was stated to: it is not only that 33-D is outside the regime, it is that the <=3-D fallback lacks the resolution to answer the question either. p90 is the only head where floor and achieved separate (0.4914 vs 0.5600, +12.3%), and the separation is about the size of its own error bar once the 4.5% race component is added back -- handed to 11a as directional, not established. DO NOT RE-OPEN without one of: (a) an eval population with repeated circuits inside a season, which would restore the different-race constraint this one had to drop because every 2024 circuit hosts exactly one race; (b) 08d's C1-C5 identity, which would make a cross-season same-circuit match well defined; or (c) a lower-dimensional target. A better fitter is not new evidence -- unit.py shows the arithmetic recovers to +/-0.5%.)
- `02a` **LANDED** — Tier 2 leakage ruling - the 5-lap field-median bucket (NOT the centred/backward binary) (landed)
- `02e` **CLOSED** — Weather / air density features (2026-08-23)
- `02f` **CLOSED** — FP1/2/3 ingest (Phase 10c) (2026-09-07)
- `08a` **LANDED** — Backfill dim_compounds_season for SUPERSOFT / ULTRASOFT / HYPERSOFT (landed)
- `08b` **LANDED** — Extend audit_forward_window to aggregation scope (2026-09-09)
- `09a` **LANDED** — CRPS alongside the pinball trio, with its decomposition (landed)
- `10a` **LANDED** — Stint end-regime label - why did this stint end? (landed)
- `05b` **CLOSED** — Monotone constraints arm (2026-09-08)

<!-- END GENERATED TASKS -->
