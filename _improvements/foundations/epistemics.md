# Epistemics — read before quoting any number

The programme's recurring failure mode, named repeatedly inside `reference/ml_execution_plan.md`,
is **a claim traced down one path and generalised, or a number computed under one statistical
protocol quoted as if comparable to a number from another.** Everything below exists to stop
that.

## Verified vs Assumed

A hard line, not a hedge.

- **Verified** — you traced the actual code path and can cite the number, with the artefact
  or query that produced it.
- **Assumed** — anything generalised from one example, inferred from a mechanism, or carried
  over from a previous session without re-checking. It must say so.

Both stages appear in every `history` entry in [`../status/build-log.json`](../status/build-log.json),
and `board.py --check` fails an entry that omits either. An entry with an empty `assumed`
list is usually a session that did not look hard enough.

## The two statistical protocols, which are not interchangeable

**Never quote a delta as clearing or missing a floor computed under the other protocol.**

| | `ml/src/intervals.py::paired_t` | `ml/src/attribution.py::refit_noise_floor` |
| :--- | :--- | :--- |
| What it is | Paired t-test over the 5 season-grouped CV folds (`train._season_folds`), n=5, df=4 | The N-reseed floor: same config at several seeds on one fixed train/eval split |
| The statistic | A p-value | A scale: `2*sqrt(2)*sd` across reseeds |
| Used for | Coordinate probes (one hyperparameter stepped, everything else fixed) and joint searches (full Optuna re-search) | Ablation and add-ablation deltas, quoted as "N.NNx floor — CLEARS" or "inside" |

Two consequences that have already bitten:

1. **A coordinate probe cannot see a joint move.** Proven directly in the 2026-08-26
   checkpoint (item 21), where the two instruments disagreed.
2. **A floor ratio is not a p-value.** `2*sqrt(2)*sd` from five reseeds is a noise *scale*.
   Converting it into a p-value needs a distributional assumption and df, and that conversion
   is the whole of work item `04b` — it is not something to do inline while quoting a result.

## Protocol anchoring

When a probe reproduces a production number under a different population, **say so before
using it**, and never diff the two.

The worked example is `reference/ml_research_program.md` §3a: its constant-predictor pinball
floors are 1.2911 / 2.0094 / 0.8972 against the artefact's 1.2512 / 1.9536 / 0.7859. That 2–4%
gap is *population, not disagreement* — the probe pools all seasons, the artefact is
`cv_final_fold` on `eval_season` 2024. It is used only to confirm the probe's arithmetic
matches `evaluate.py`'s, which is the only thing it can be used for.

## Handoff protocol

Every session appends one `history` entry with six fields. This is the same protocol
`ml_execution_plan.md` used across 22 checkpoints; it now lives in the JSON so it can be
checked mechanically.

| Field | Holds |
| :--- | :--- |
| `landed` | What now exists that did not before. |
| `verified` | List. Each item traceable to a code path or artefact. |
| `assumed` | List. Each item flagged as inference. |
| `gates_run` | The gates from [`gates.md`](gates.md) that were actually run, or "None" plainly. |
| `next_command` | The literal first command the next session should run. |
| `next_action` | One sentence on what that command is for. |

Optional: `method_findings` for a result about an instrument rather than about the models —
the 2026-09-07 entry uses it to record that `ml_research_program.md` §3b is unsafe to build
as written.

## Standing constraints

- **Ad hoc probes are throwaway.** Scratchpad only, never committed, and never left modifying
  `ml/models/*.json`, warehouse data, or git state.
- **Reuse production code paths** — `ml/src/{train,features,evaluate,attribution,intervals}.py` —
  rather than reimplementing fit/score/CV logic. Fidelity beats convenience; a reimplemented
  scorer is a new instrument with its own bugs.
- **Read the warehouse read-only.** `duckdb.connect(..., read_only=True)`.
- **Nothing is committed without being asked.**
