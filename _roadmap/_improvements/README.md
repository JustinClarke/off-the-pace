# `_improvements/` — the ML/transform lab tree

Working documentation for the off-the-pace ML and transform programme. Not shipped, and never
referenced from `ml/`, `transform/` or `app/`.

> **Corrected 2026-09-07.** This paragraph used to claim the tree was "not tracked by git
> (`.gitignore:122`)". It is **tracked** — `.gitignore:122` is `docs/project-graph.html`,
> `git check-ignore` reports the tree as not ignored, and 8 files under `_improvements/` are
> already in the index, this README among them. Nothing here is throwaway-by-default: the
> only thing keeping it out of a commit is the standing "nothing is committed without being
> asked" rule. Write accordingly.
The code repo describes what it does and why, in place; this tree describes what is being
attempted, what has been measured, and what stage each thing is at.

Structured after `DataScope/_implementation/`, adapted for a research programme rather than
a feature build: work items carry a **stage**, not a checkbox, because a measurement can
come back "closed, not viable" and that is a result rather than a failure.

## Layout

| Folder | Concern |
| :--- | :--- |
| [`status/`](status/) | **Where the programme stands** — [`build-log.json`](status/build-log.json) (authoritative state: items, stages, decisions, append-only history), [`board.py`](status/board.py) (render + validate), and [`BUILD-ORDER.md`](status/BUILD-ORDER.md) (the rules that govern the log, plus a generated ordered task list) |
| [`foundations/`](foundations/) | **Constraints every work item answers to** — [`epistemics.md`](foundations/epistemics.md) (Verified vs Assumed, the two statistical protocols, the handoff protocol) and [`gates.md`](foundations/gates.md) (the standing admission gate for any contract change) |
| [`work/`](work/) | **One leaf doc per work item**, numbered in build order. Each carries objective → dependencies → method → acceptance → definition of done |
| [`reference/`](reference/) | The lab notebooks. Cited by work items for evidence; **not** edited as trackers any more |
| [`research/`](research/) | **Round R1 — the state-of-the-art scan** (2026-09-07). What the current literature offers this data, across ML, statistics, causal inference, the transform layer and the published F1 field. Start at [`research/README.md`](research/README.md)'s ranked findings table. Progress tracked in [`research-log.json`](research-log.json); it holds **no** work-item state, and findings become items only once promoted into `status/build-log.json` |

## Reading order for a fresh session

```bash
python3 _improvements/status/board.py
```

1. **Run the board.** It prints every item with its stage and unmet blockers, the open
   decisions, and the literal next command from the last session's handoff entry.
2. [`foundations/epistemics.md`](foundations/epistemics.md) — **read before quoting any
   number.** The programme's recurring failure mode is a figure from one statistical
   protocol diffed against a figure from another.
3. The leaf doc in [`work/`](work/) that the `▶` points at.
4. [`status/BUILD-ORDER.md`](status/BUILD-ORDER.md) — its generated task list is the whole
   ladder in runnable order, if you want the shape of the programme rather than just the next
   step. Read its rules section only if you are changing the log rather than reading it.

Open the `reference/` notebooks only when a leaf doc cites a specific section of one. They
are long — `ml_execution_plan.md` is 4,500+ lines and exceeds the Read tool's cap; grep its
headers rather than reading it whole.

## What moved here, and where each thing went

| Was | Now | Why |
| :--- | :--- | :--- |
| `ml_execution_plan.md` | [`reference/`](reference/ml_execution_plan.md) | **Closed** as a tracker — 22 checkpoints, Series 1 and 2 both complete. Still the authoritative record of what was tried and measured |
| `ml_research_program.md` | [`reference/`](reference/ml_research_program.md) | Superseded as a tracker. Its §3/§3a split into [`work/01`](work/01-ceiling-instrument.md), §5 into [`work/04`](work/04-campaign-audit.md), §6 into [`work/05`](work/05-model-family.md). §4 stays closed. §3a's probe evidence is still cited, not duplicated |
| — | [`work/03`](work/03-driver-vs-car.md), [`work/06`](work/06-publication.md) | New. The external-findings direction, which no notebook covered |
| `ml_feature_expansion.md` | [`work/02-feature-expansion.md`](work/02-feature-expansion.md) | Already leaf-doc shaped; became the work item unchanged |
| `PLAN.md`, `transform_gaps.md`, `ml_headroom.md`, `ml_headroom_ii.md` | [`reference/`](reference/) | Closed. Historical record |

Nothing was deleted. A work item cites its source notebook by section; it does not copy it.

## Conventions

- **Stage, not a checkbox.** Every work item carries one of eight stages (`stage_vocabulary`
  in the log). `CLOSED` is a legitimate terminal stage, recorded with its reason, so a later
  session that has forgotten does not re-open it.
- **State lives in exactly one file** — `status/build-log.json`. Prose files describe rules
  and method; they never restate an item, a stage or a decision. Run
  `board.py --check` after every edit to the log.
- **One generated exception**, added 2026-09-07: `BUILD-ORDER.md` carries an ordered task
  list between two markers, written by `board.py --write-order` and derived wholly from the
  log. It is not a second source of truth — `--check` fails when it drifts, and
  `--write-order` refuses to run from an invalid log. Regenerate it; never type into it.
- **Exactly one `▶`.** `pointer` names the single next item; `--check` enforces it.
- **Every session appends one `history` entry** with all six handoff fields — `landed`,
  `verified`, `assumed`, `gates_run`, `next_command`, `next_action`. `--check` fails an entry
  missing any of them. See [`foundations/epistemics.md`](foundations/epistemics.md).
- **Verified vs Assumed is a hard line.** Only "Verified" if the code path was traced and the
  number can be cited.
- **Ad hoc probes are throwaway.** Measurement scripts live in the session scratchpad, are
  never committed, and must not touch `ml/models/*.json`, warehouse data, or git state.
  Reuse the production paths (`ml/src/{train,features,evaluate,attribution,intervals}.py`)
  rather than reimplementing fit/score/CV logic.
- **Running an item is a delegation, not a switch.** The interactive session (by standing
  convention, `haiku-4-5`) never executes a live item itself — it spawns an agent at the
  item's own `model` field, then independently verifies what comes back before the log is
  touched. See `BUILD-ORDER.md`'s rules section.
- **Nothing is committed without being asked.** Standing rule for this repo, unchanged.
