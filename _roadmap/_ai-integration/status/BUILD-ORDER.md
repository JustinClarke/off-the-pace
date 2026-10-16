# AI-integration build order — rules, and the ordered task list

**State lives in [`build-log.json`](build-log.json), and only there.** This file holds the rules
and one **generated** task list, spliced in at the bottom by the board.

A hand-written checklist here is a defect. Edit the JSON, run `--check`, then `--write-order`.
Never type into the generated block.

```bash
python3 _roadmap/_ai-integration/status/board.py                # the board, open rulings, next command
python3 _roadmap/_ai-integration/status/board.py --check        # invariants only; exit 1 on failure
python3 _roadmap/_ai-integration/status/board.py --order        # the ordered task list, to stdout
python3 _roadmap/_ai-integration/status/board.py --write-order  # ...and spliced into this file
python3 _roadmap/_ai-integration/status/board.py --watch        # the watch list in full
python3 _roadmap/_ai-integration/status/board.py --ship         # exit 1 while a ship-blocker is open
```

**Rules**

1. The pointer is the one item to run next. Run `--check` after every edit.
2. A `BLOCKED` item waits on an open ruling. Put the ruling to the human first, with the options
   translated, before spawning work on it.
3. Close-out (`CO-*`) comes before the assistant (`AI-*`) for anything that changes a number the
   assistant would quote.
4. Nothing is committed or deployed without a yes from the user.

<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-10-16T12:00:00+04:00`. Run `python3 _roadmap/_ai-integration/status/board.py --write-order` after any edit to the log._

**12 live items** (0 blocked). The pointer is on **CO-06** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 5 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Sources | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | [CO-03](../wi/CO-03-v15-gates-rerun.md) | D | MEASURED | 1-2d | `opus-5` | ml/models/manifest.json, ml/src/schema.py, ml/artefacts/15a_traffic_families_arms.log, ml/artefacts/08e_thermal_family_arms_v15.log, transform/models/intermediate/int_lap_anomaly_flags.sql | v15 retrain on the final label, owed gates re-run, ONNX and manifest exported | — |
| 2 | [CO-05](../wi/CO-05-ingestion-review.md) | D | MEASURED | 0.5d | `sonnet-5` | ingestion/verify_bronze.py, ingestion/tests/test_bronze_verification.py, ingestion/tests/test_ingest_hardening.py, _roadmap/_fixes/status/build-log.json | W4 ingestion hardening: review the committed work, fix the one stale test | — |
| 3 | [CO-06](../wi/CO-06-docs-schema-refresh.md) ▶ | D | SPEC | 0.5d | `sonnet-5` | transform/models/marts/schema.yml, transform/models/intermediate/schema.yml, docs/reference/models/ | Docs and schema text: the removed 2018 +0.37 s offset, the old window-mean severity | — |
| 4 | [AI-03](../wi/AI-03-carry-over-closeout.md) | D | SPEC | 0.5d | `sonnet-5` | _roadmap/_fixes/status/build-log.json, scripts/export_app_data.py | Carry-over gate: numbers settled, fixes-log entries corrected, card sources frozen for the launch run | CO-03, CO-06 |
| 5 | [CO-08](../wi/CO-08-flag-chance-calibration.md) | D | BUILDING | 3-5d | `opus-5` | ml/src/survival.py, ml/src/evaluate.py, ml/src/predict.py, scripts/export_app_data.py, app/src/features/degradation-simulator/ | Chance to make the flag: calibrated, final stints only (plus laps-to-flag display cap) | — |
| 6 | [CO-09](../wi/CO-09-stint-label-fix.md) | D | SPEC | 1-2d | `opus-5` | transform/models/intermediate/int_stint_end_regime.sql, ml/src/schema.py | Stint labels: join same-tyre splits, censor red-flag tyre changes (dbt), version bump | — |
| 7 | [AI-01](../wi/AI-01-grounding-contract.md) | A | SPEC | 2-3d | `opus-5` | transform/models/marts/mart_race_driver_summary.sql, transform/models/marts/mart_driver_season_summary.sql, transform/models/marts/mart_metric_benchmark.sql, ml/src/predict.py, transform/models/intermediate/int_pit_strategy_value.sql, scripts/export_app_data.py | Grounding contract: fact cards (value, n, interval, source) for ratings, tyre predictions and pit calls, published with the app data | — |
| 8 | [AI-02](../wi/AI-02-honesty-policy.md) | A | SPEC | 1-2d | `opus-5` | docs/app/blind-test-scoreboard.mdx, docs/ml/ci/evaluation-gates.mdx, docs/app/model-metrics.mdx, _roadmap/_fixes/status/build-log.json | Honesty policy: the docs' uncertainty rules as a machine-checkable list the assistant cannot talk around | — |
| 9 | [AI-04](../wi/AI-04-assistant-core.md) | B | SPEC | 2d | `sonnet-5` | app/src/data/duckdb/client.ts, app/src/data/manifest.ts, docs/app/degradation-simulator.mdx | Assistant core: one fact-card tool and a bounded answer loop, runnable headless | AI-01, AI-02 |
| 10 | [AI-06](../wi/AI-06-proxy-and-key-safety.md) | C | SPEC | 2d | `sonnet-5` | firebase.json, docs/platform/architecture-decisions.mdx, _roadmap/_wip/AI_PLAN.md | Cloudflare Worker proxy to Workers AI: key never in the bundle, App Check or equivalent, rate limit, daily allowance guard, pause state, usage counter, CSP updated | — |
| 11 | [AI-07](../wi/AI-07-analyst-eval-set.md) | C | SPEC | 3d | `opus-5` | docs/app/race-lost.mdx, docs/app/pit-strategy.mdx, docs/app/tyre-cliff-survival.mdx, docs/app/families/ | Analyst eval: about 40 fan questions, a grader, a pass bar fixed before the first run, and a measured baseline | AI-01, AI-02, AI-04 |
| 12 | [AI-08](../wi/AI-08-chat-ui.md) | C | SPEC | 3d | `sonnet-5` | app/src/ui/layout/AppShell.tsx, app/src/ui/feedback/, app/src/nav/ | Chat drawer: streamed answer, every number linked to its card and page, caveats inline; launch run of the eval | AI-03, AI-04, AI-06, AI-07 |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **CD4** (blocks `CO-08`) — Acceptance rule for the flag-chance line. The 10-bins-within-5-pp rule cannot be met reliably on one season. A: keep it (chance stays hidden, cap only). B: a race-clustered rule: average gap within 3 pp, intercept CI contains 0, slope CI contains 1. C: 5 wider bins pooled over the two latest seasons. _Recommended: A for now. Revisit with 2026 data as the first clean test._
- **CD5** (blocks `CO-08`) — Where the chance number may appear. A: parquet and race replay only (E4 needs live field context, the browser simulator cannot run it), cap only in the simulator. B: E6 instead (simulator-known inputs, 0.0872 vs 0.0855 on selection; not scored on 2025 and cannot be now without another look). C: cap only everywhere. _Recommended: C for the simulator now; A later if the 2026 test passes under the rule chosen in CD4._

<!-- END GENERATED TASKS -->
