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

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-10-17T12:00:00+04:00`. Run `python3 _roadmap/_ai-integration/status/board.py --write-order` after any edit to the log._

**16 live items** (0 blocked). The pointer is on **CO-06** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 5 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Sources | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | [CO-03](../wi/CO-03-v15-gates-rerun.md) | D | MEASURED | 1-2d | `opus-5` | ml/models/manifest.json, ml/src/schema.py, ml/artefacts/15a_traffic_families_arms.log, ml/artefacts/08e_thermal_family_arms_v15.log, transform/models/intermediate/int_lap_anomaly_flags.sql | v15 retrain on the final label, owed gates re-run, ONNX and manifest exported | — |
| 2 | [CO-05](../wi/CO-05-ingestion-review.md) | D | MEASURED | 0.5d | `sonnet-5` | ingestion/verify_bronze.py, ingestion/tests/test_bronze_verification.py, ingestion/tests/test_ingest_hardening.py, _roadmap/_fixes/status/build-log.json | W4 ingestion hardening: review the committed work, fix the one stale test | — |
| 3 | [CO-06](../wi/CO-06-docs-schema-refresh.md) ▶ | D | SPEC | 0.5d | `sonnet-5` | transform/models/marts/schema.yml, transform/models/intermediate/schema.yml, docs/reference/models/ | Docs and schema text: the removed 2018 +0.37 s offset, the old window-mean severity | — |
| 4 | [AI-03](../wi/AI-03-carry-over-closeout.md) | D | SPEC | 0.5d | `sonnet-5` | _roadmap/_fixes/status/build-log.json, scripts/export_app_data.py | Carry-over gate: numbers settled, fixes-log entries corrected, card sources frozen for the launch run | CO-03, CO-06 |
| 5 | [CO-08](../wi/CO-08-flag-chance-calibration.md) | D | BUILDING | 3-5d | `opus-5` | ml/src/survival.py, ml/src/evaluate.py, ml/src/predict.py, scripts/export_app_data.py, app/src/features/degradation-simulator/ | Chance to make the flag: calibrated, final stints only (plus laps-to-flag display cap) | — |
| 6 | [CO-09](../wi/CO-09-stint-label-fix.md) | D | SPEC | 1-2d | `opus-5` | transform/models/intermediate/int_stint_end_regime.sql, ml/src/schema.py | Stint labels: join same-tyre splits, censor red-flag tyre changes (dbt), version bump | — |
| 7 | [CO-10](../wi/CO-10-flag-chance-2026-test.md) | D | SPEC | 3-5d | `opus-5` | ml/src/flag_chance.py, ml/src/survival.py, app/src/ml/flagChance.ts, app/public/models/flag_chance_lookup.json | 2026 flag-chance test: decide CD4, ingest 2026 stints (OpenF1), freeze pre-registration, score once | CO-09 |
| 8 | [CO-11](../wi/CO-11-relabel-flag-chance.md) | D | SPEC | 0.5d | `sonnet-5` | app/src/ml/flagChance.ts, app/src/features/degradation-simulator/DegradationSimulatorChart.tsx, app/src/features/degradation-simulator/methodology.tsx, docs/app/degradation-simulator.mdx, app/public/models/flag_chance_lookup.json | Relabel the experimental chance number as a refit of the v14 configuration, not v14 | — |
| 9 | [CO-12](../wi/CO-12-openf1-2026-spike.md) | D | SPEC | 2-4d | `sonnet-5` | ingestion/ | OpenF1 2026 ingest spike: ingest only, nothing scored | — |
| 10 | [CO-13](../wi/CO-13-commit-split.md) | D | SPEC | 0.5d | `sonnet-5` | app/src/ml/flagChance.ts, app/src/features/degradation-simulator/, ml/src/flag_chance.py, _roadmap/_ai-integration/status/build-log.json, _roadmap/_ai-integration/wi/CO-08-flag-chance-calibration.md | Commit the experimental chance line and the restored CO-08 records as separate commits | CO-11 |
| 11 | [AI-01](../wi/AI-01-grounding-contract.md) | A | SPEC | 2-3d | `opus-5` | transform/models/marts/mart_race_driver_summary.sql, transform/models/marts/mart_driver_season_summary.sql, transform/models/marts/mart_metric_benchmark.sql, ml/src/predict.py, transform/models/intermediate/int_pit_strategy_value.sql, scripts/export_app_data.py | Grounding contract: fact cards (value, n, interval, source) for ratings, tyre predictions and pit calls, published with the app data | — |
| 12 | [AI-02](../wi/AI-02-honesty-policy.md) | A | SPEC | 1-2d | `opus-5` | docs/app/blind-test-scoreboard.mdx, docs/ml/ci/evaluation-gates.mdx, docs/app/model-metrics.mdx, _roadmap/_fixes/status/build-log.json | Honesty policy: the docs' uncertainty rules as a machine-checkable list the assistant cannot talk around | — |
| 13 | [AI-04](../wi/AI-04-assistant-core.md) | B | SPEC | 2d | `sonnet-5` | app/src/data/duckdb/client.ts, app/src/data/manifest.ts, docs/app/degradation-simulator.mdx | Assistant core: one fact-card tool and a bounded answer loop, runnable headless | AI-01, AI-02 |
| 14 | [AI-06](../wi/AI-06-proxy-and-key-safety.md) | C | SPEC | 2d | `sonnet-5` | firebase.json, docs/platform/architecture-decisions.mdx, _roadmap/_wip/AI_PLAN.md | Cloudflare Worker proxy to Workers AI: key never in the bundle, App Check or equivalent, rate limit, daily allowance guard, pause state, usage counter, CSP updated | — |
| 15 | [AI-07](../wi/AI-07-analyst-eval-set.md) | C | SPEC | 3d | `opus-5` | docs/app/race-lost.mdx, docs/app/pit-strategy.mdx, docs/app/tyre-cliff-survival.mdx, docs/app/families/ | Analyst eval: about 40 fan questions, a grader, a pass bar fixed before the first run, and a measured baseline | AI-01, AI-02, AI-04 |
| 16 | [AI-08](../wi/AI-08-chat-ui.md) | C | SPEC | 3d | `sonnet-5` | app/src/ui/layout/AppShell.tsx, app/src/ui/feedback/, app/src/nav/ | Chat drawer: streamed answer, every number linked to its card and page, caveats inline; launch run of the eval | AI-03, AI-04, AI-06, AI-07 |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **CD4** (blocks `CO-08`, `CO-10`) — Acceptance rule for the flag-chance line. The 10-bins-within-5-pp rule cannot be met reliably on one season. A: keep it (chance stays hidden, cap only). B: a race-clustered rule: average gap within 3 pp, intercept CI contains 0, slope CI contains 1. C: 5 wider bins pooled over the two latest seasons. _Recommended: A for now. Revisit with 2026 data as the first clean test._
- **CD5** (blocks `CO-08`) — Where the chance number may appear. A: parquet and race replay only (E4 needs live field context, the browser simulator cannot run it), cap only in the simulator. B: E6 instead (simulator-known inputs, 0.0872 vs 0.0855 on selection; not scored on 2025 and cannot be now without another look). C: cap only everywhere. _Recommended: C for the simulator now; A later if the 2026 test passes under the rule chosen in CD4._
- **CD6** (blocks `CO-10`) — Which fold scheme defines the flag-chance lookup and its 2026 test? A: expanding window (the project's existing CV; the shipped lookup matches it exactly). B: leave-one-season-out within 2018-2024 (the lookup differs by up to 0.012, and the 2024 weighting pick changes from last3 to uniform). _Recommended: A. It is the project's existing CV and the shipped lookup already matches it._
- **CD7** (blocks nothing) — How is dirty air priced below lap grain? int_sector_residual_decomposed allocates the sector dirty-air tax on the CURRENT lap's dirty_air_share_lap, while the lap tax it must sum to is priced on the PREVIOUS lap's share (theta_air 0.331, the causal lag), so assert_sector_aggregates_to_lap fails on 10,706 dev laps by exactly 0.331 s and stays warn. A: sector tax = lap tax x sector time share (one-line fix, identity holds, no relabel). B: lap and sector both switch to the current-lap share (refit theta, about 0.473; label bump, relabel, ML retrain; gives up the one-lap ordering argument). C: micro-sector pricing: persist int_lap_proximity's 100-bin gaps, aggregate to 10-20 micro-sectors, fit theta within lap on the entry gap (predetermined for the micro-sector it prices), lap tax = sum of micro-sector taxes (new models, fit script outside dbt, full relabel and retrain; 2018_1-2 have no telemetry). D: keep the lagged lap tax, allocate it across sectors by real-time exposure (identity holds, no relabel; on 2023 it moves little from time share). _Recommended: A now (closes the warning; promote the test to error). Then C as its own reviewed label-version project, keeping the 06b/WI-12 lag series as a comparison arm. Not B._

<!-- END GENERATED TASKS -->

### Things to watch

- **Hash baseline gate is red.** `transform/tests/model_hashes.baseline.json` (`snapshot_model_hashes.py --check`) was taken on full data (about 161k rows) but CI runs on the fixture (about 2.5k rows), so every hash differs. Re-take it on full data, or turn the gate off, before relying on it.
- **`assert_sector_aggregates_to_lap` warns on 152 rows.** Known latent defect in `int_sector_residual_decomposed`: the sector term uses the current lap's air share, the lap total uses the previous lap's. Warn-only until CD7 is ruled.
- **`assert_prior_season_labels_frozen` warns on 2 rows.** Fixture artifact: the frozen baselines come from full history and the fixture has only 3 small races.
- **Tactical grade set to `unvalidated` in `driver_isolation_method_scores.csv`.** The validator actually recorded `cancelled`, but the schema only accepts A/B/C/F/unvalidated, so the row was set to `unvalidated` to pass the not-null check. Revisit if tactical is re-run or if `cancelled` should be a distinct state (that would mean adding it to the schema's accepted values). Its `report_path` now points at the `wi-16-2026-10-03` report, matching the other rows.
