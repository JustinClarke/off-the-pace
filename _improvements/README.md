# `_improvements/` — the ML/transform lab tree

Working documentation for the off-the-pace ML and transform programme. Not shipped, not
tracked by git (`.gitignore:122`), and never referenced from `ml/`, `transform/` or `app/`.
The code repo describes what it does and why, in place; this tree describes what is being
attempted, what has been measured, and what stage each thing is at.

Structured after `DataScope/_implementation/`, adapted for a research programme rather than
a feature build: work items carry a **stage**, not a checkbox, because a measurement can
come back "closed, not viable" and that is a result rather than a failure.

## Layout

| Folder | Concern |
| :--- | :--- |
| [`status/`](status/) | **Where the programme stands** — [`BUILD-ORDER.md`](status/BUILD-ORDER.md) (the only place stage lives), its append-only [`BUILD-ORDER-HISTORY.md`](status/BUILD-ORDER-HISTORY.md), and [`OPEN-DECISIONS.md`](status/OPEN-DECISIONS.md) (items waiting on a human call) |
| [`foundations/`](foundations/) | **Constraints every work item answers to** — [`epistemics.md`](foundations/epistemics.md) (Verified vs Assumed, the two statistical protocols, the handoff protocol) and [`gates.md`](foundations/gates.md) (the standing admission gate for any contract change) |
| [`work/`](work/) | **One leaf doc per work item**, numbered in build order. Each carries objective → dependencies → method → acceptance → definition of done |
| [`reference/`](reference/) | The lab notebooks. Cited by work items for evidence; **not** edited as trackers any more |

## Reading order for a fresh session

1. [`status/BUILD-ORDER.md`](status/BUILD-ORDER.md) — the checklist and the single `▶`.
2. The tail of [`status/BUILD-ORDER-HISTORY.md`](status/BUILD-ORDER-HISTORY.md) — the last
   two or three entries say what now works and what to run next.
3. [`foundations/epistemics.md`](foundations/epistemics.md) — **read before quoting any
   number.** The programme's recurring failure mode is a figure from one statistical
   protocol diffed against a figure from another.
4. The leaf doc in [`work/`](work/) that the `▶` points at.

Open the `reference/` notebooks only when a leaf doc cites a specific section of one. They
are long — `ml_execution_plan.md` is 4,500+ lines and exceeds the Read tool's cap; grep its
headers rather than reading it whole.

## What moved here, and where each thing went

| Was | Now | Why |
| :--- | :--- | :--- |
| `ml_execution_plan.md` | [`reference/`](reference/ml_execution_plan.md) | **Closed** as a tracker — 22 checkpoints, Series 1 and 2 both complete. Still the authoritative record of what was tried and measured |
| `ml_research_program.md` | [`reference/`](reference/ml_research_program.md) | Superseded as a tracker. Its §3/§3a split into [`work/01`](work/01-ceiling-instrument.md), §5 into [`work/04`](work/04-campaign-audit.md), §6 into [`work/05`](work/05-model-family.md). §4 stays closed. §3a's probe evidence is still cited, not duplicated |
| `ml_feature_expansion.md` | [`work/02-feature-expansion.md`](work/02-feature-expansion.md) | Already leaf-doc shaped; became the work item unchanged |
| `PLAN.md`, `transform_gaps.md`, `ml_headroom.md`, `ml_headroom_ii.md` | [`reference/`](reference/) | Closed. Historical record |

Nothing was deleted. A work item cites its source notebook by section; it does not copy it.

## Conventions

- **Stage, not a checkbox.** Every work item carries one of the stages in
  [`BUILD-ORDER.md`](status/BUILD-ORDER.md)'s stage table. `CLOSED — not viable` is a
  legitimate terminal stage and is recorded with its reason, so it is never re-opened by a
  later session that has forgotten.
- **Exactly one `▶`** in `BUILD-ORDER.md` at all times, marking the next thing to run.
- **Status lives in exactly one file.** `BUILD-ORDER.md` holds stage and nothing else; every
  narrative, number, deviation and reason goes in `BUILD-ORDER-HISTORY.md`.
- **Every session appends one history entry** — what landed, what was verified vs assumed,
  gates run, open decisions, and the first command the next session should run. This is the
  handoff protocol the programme already used; see
  [`foundations/epistemics.md`](foundations/epistemics.md).
- **Verified vs Assumed is a hard line.** Only "Verified" if the code path was traced and the
  number can be cited.
- **Ad hoc probes are throwaway.** Measurement scripts live in the session scratchpad, are
  never committed, and must not touch `ml/models/*.json`, warehouse data, or git state.
  Reuse the production paths (`ml/src/{train,features,evaluate,attribution,intervals}.py`)
  rather than reimplementing fit/score/CV logic.
- **Nothing is committed without being asked.** Standing rule for this repo, unchanged.
