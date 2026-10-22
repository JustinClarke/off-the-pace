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

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-10-22T23:00:00+04:00`. Run `python3 _roadmap/_ai-integration/status/board.py --write-order` after any edit to the log._

**25 live items** (4 blocked). The pointer is on **CO-05** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 7 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Sources | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | [CO-05](../wi/CO-05-ingestion-review.md) ▶ | 1-data | MEASURED | 0.5d | `sonnet-5` | ingestion/verify_bronze.py, ingestion/tests/test_bronze_verification.py, ingestion/tests/test_ingest_hardening.py, _roadmap/_fixes/status/build-log.json | Ingestion check-up: the data-download safety checks were saved to git long ago; re-run their tests and close the old warning (W4) that says they never were | — |
| 2 | [CO-06](../wi/CO-06-docs-schema-refresh.md) | 1-data | SPEC | 0.5d | `sonnet-5` | transform/models/marts/schema.yml, transform/models/intermediate/schema.yml, docs/reference/models/ | Docs and schema text: the removed 2018 +0.37 s offset, the old window-mean severity | — |
| 3 | [CO-09](../wi/CO-09-stint-label-fix.md) | 1-data | SPEC | 1-2d | `opus-5` | transform/models/intermediate/int_stint_end_regime.sql, ml/src/schema.py | Stint labels: join same-tyre splits, censor red-flag tyre changes (dbt), version bump | — |
| 4 | [CO-15](../wi/CO-15-monaco-wear-hold.md) | 1-data | SPEC | 1-2d | `opus-5` | transform/macros/compound_cliff_wear.sql, transform/dbt_project.yml, transform/models/intermediate/int_compound_cliff_predicted.sql, transform/models/intermediate/int_field_pace_curve.sql, transform/tests/assert_field_pace_honest_range.sql, transform/tasks/coefficients/survival.py, _roadmap/_ai-integration/_evidence/co-15-2026-10-22/proposed_fix_wear_hold.diff | Monaco 2024 field-pace defect: hold the linear tyre-wear term flat past onset + 5 laps, in CO-09's label version, with two new tests | CO-09 |
| 5 | [CO-16](../wi/CO-16-sector-dirty-air-share.md) | 1-data | SPEC | 0.5d | `sonnet-5` | transform/models/intermediate/int_sector_residual_decomposed.sql, transform/models/intermediate/int_dirty_air_tax_component.sql, transform/tests/assert_sector_aggregates_to_lap.sql, scripts/export_app_data.py, _roadmap/_ai-integration/_evidence/co-16-2026-10-22/cd7_option_a.diff | Sector dirty-air tax: lap tax x sector time share, drop the current-share gate, promote assert_sector_aggregates_to_lap to error | — |
| 6 | [CO-17](../wi/CO-17-trusted-dev-rebuild.md) | 1-data | SPEC | 1d | `sonnet-5` | Makefile, transform/dbt_project.yml, transform/models/, transform/tests/, transform/models/intermediate/int_lap_anomaly_flags.sql | Trusted full rebuild of the dev warehouse on the new label version: dbt-dev-full, every test, the frozen-label refresh, row-count diff | CO-09, CO-15, CO-16 |
| 7 | [CO-14](../wi/CO-14-stint-life-clean-test.md) | 1-data | SPEC | 2-3d | `opus-5` | ml/src/evaluate.py, ml/src/survival.py, ml/models/manifest.json | Stint-life clean test: write the rules, then score the v15 configuration once against the v14 configuration, both refit on the new label, leave-one-season-out within 2018-2024 | CO-17 |
| 8 | [CO-18](../wi/CO-18-retrain-new-label.md) | 1-data | SPEC | 1-2d | `opus-5` | ml/src/schema.py, ml/models/manifest.json, ml/src/evaluate.py, ml/README.md, ml/artefacts/ | Retrain the five models on the new label version, owed gates, ONNX and manifest exported, not promoted | CO-17 |
| 9 | [CO-19](../wi/CO-19-mixed-version-probe.md) | 1-data | SPEC | 1-2d | `opus-5` | ml/src/schema.py, ml/src/predict.py, ml/src/features.py, ml/src/export_onnx.py, ml/src/flag_chance.py, ml/models/, ml/artefacts/, transform/models/marts/fct_cliff_prediction_features.sql, Makefile, app/public/models/, app/src/ml/, app/src/data/, app/src/features/degradation-simulator/, scripts/export_app_data.py, _roadmap/_ai-integration/_evidence/co-19-2026-10-22/PROVENANCE.txt | Mixed model versions probe: can stint life stay on v14 while the other four models move to the new label? Scenarios, go/no-go, plain list of what breaks | CO-18 |
| 10 | [AI-01](../wi/AI-01-grounding-contract.md) | 2-assistant | SPEC | 2-3d | `opus-5` | transform/models/marts/mart_race_driver_summary.sql, transform/models/marts/mart_driver_season_summary.sql, transform/models/marts/mart_metric_benchmark.sql, ml/src/predict.py, transform/models/intermediate/int_pit_strategy_value.sql, scripts/export_app_data.py | Grounding contract: fact cards (value, n, interval, source) for ratings, tyre predictions and pit calls, published with the app data | CO-17 |
| 11 | [AI-02](../wi/AI-02-honesty-policy.md) | 2-assistant | SPEC | 1-2d | `opus-5` | docs/app/blind-test-scoreboard.mdx, docs/ml/ci/evaluation-gates.mdx, docs/app/model-metrics.mdx, _roadmap/_fixes/status/build-log.json | Honesty policy: the docs' uncertainty rules as a machine-checkable list the assistant cannot talk around | — |
| 12 | [AI-09](../wi/AI-09-query-builder.md) | 2-assistant | SPEC | 3d | `opus-5` | app/src/data/duckdb/queryLab.ts, app/src/data/duckdb/client.ts, app/src/data/manifest.ts | Query builder: a structured request, built into bounded SQL in the browser, with a fixed result shape | AI-01, CO-16 |
| 13 | [AI-10](../wi/AI-10-navigation-and-explainer.md) | 2-assistant | SPEC | 2d | `sonnet-5` | app/src/nav/, docs/app/ | Navigation and page explainer: shipped routes only, and pre-cut page summaries of 800 tokens or less | — |
| 14 | [AI-11](../wi/AI-11-charts-and-comparison.md) | 2-assistant | SPEC | 2-3d | `sonnet-5` | app/src/ui/feedback/, app/src/data/duckdb/queryLab.ts | Chart and lap-comparison tools: fixed chart description, rows kept out of the model's context, ported from the prototype | AI-09 |
| 15 | [AI-04](../wi/AI-04-assistant-core.md) | 2-assistant | SPEC | 2d | `sonnet-5` | app/src/data/duckdb/client.ts, app/src/data/manifest.ts, docs/app/degradation-simulator.mdx | Assistant core: seven tools, the bounded answer loop, and the 20k-token budget, runnable headless | AI-01, AI-02, AI-09, AI-10, AI-11 |
| 16 | [AI-06](../wi/AI-06-proxy-and-key-safety.md) | 3-launch | SPEC | 2d | `sonnet-5` | firebase.json, docs/platform/architecture-decisions.mdx, _roadmap/_wip/AI_PLAN.md | Cloudflare Worker proxy to gpt-oss-20b on Workers AI: key never in the bundle, Turnstile, per-visitor limit, placeholder daily cap, pause state, usage counter, CSP | — |
| 17 | [AI-07](../wi/AI-07-analyst-eval-set.md) | 3-launch | SPEC | 3d | `opus-5` | docs/app/race-lost.mdx, docs/app/pit-strategy.mdx, docs/app/tyre-cliff-survival.mdx, docs/app/families/ | Analyst eval: fan questions across all seven tools, a grader, a pass bar fixed before the first run, and a measured baseline | AI-01, AI-02, AI-04 |
| 18 | [AI-08](../wi/AI-08-chat-ui.md) | 3-launch | SPEC | 3d | `sonnet-5` | app/src/ui/layout/AppShell.tsx, app/src/ui/feedback/, app/src/nav/ | Chat drawer: streamed answer, every number linked to its card and page, caveats inline, behind a flag (off) | AI-04, AI-06 |
| 19 | [AI-03](../wi/AI-03-carry-over-closeout.md) | 1-data | SPEC | 0.5d | `sonnet-5` | _roadmap/_fixes/status/build-log.json, scripts/export_app_data.py | Data freeze: numbers settled, fixes-log entries corrected, card sources and model version frozen for the launch run | CO-06, CO-14, CO-17, CO-18, CO-19, **CD10** (human call) |
| 20 | [AI-12](../wi/AI-12-launch-run-and-switch-on.md) | 3-launch | SPEC | 1d | `sonnet-5` | _roadmap/_ai-integration/wi/AI-07-analyst-eval-set.md, _roadmap/_ai-integration/wi/AI-03-carry-over-closeout.md, app/src/ui/layout/AppShell.tsx, firebase.json | Launch run and switch-on: AI-07 on the frozen snapshot through the real drawer and proxy, then the owner turns the flag on | AI-03, AI-06, AI-07, AI-08, **AD4** (human call) |
| 21 | [CO-11](../wi/CO-11-relabel-flag-chance.md) | 4-chance | SPEC | 0.5d | `sonnet-5` | app/src/ml/flagChance.ts, app/src/features/degradation-simulator/DegradationSimulatorChart.tsx, app/src/features/degradation-simulator/methodology.tsx, docs/app/degradation-simulator.mdx, app/public/models/flag_chance_lookup.json | Relabel the experimental chance number as a refit of the v14 configuration, not v14 | — |
| 22 | [CO-08](../wi/CO-08-flag-chance-calibration.md) | 4-chance | BLOCKED | 3-5d | `opus-5` | ml/src/survival.py, ml/src/evaluate.py, ml/src/predict.py, scripts/export_app_data.py, app/src/features/degradation-simulator/ | Chance to make the flag: calibrated, final stints only (plus laps-to-flag display cap) | **CD4** (human call), **CD5** (human call) |
| 23 | [CO-12](../wi/CO-12-openf1-2026-spike.md) | 4-chance | BLOCKED | 2-4d | `sonnet-5` | ingestion/ | OpenF1 2026 ingest spike: ingest only, nothing scored | **CD12** (human call) |
| 24 | [CO-10](../wi/CO-10-flag-chance-2026-test.md) | 4-chance | BLOCKED | 3-5d | `opus-5` | ml/src/flag_chance.py, ml/src/survival.py, app/src/ml/flagChance.ts, app/public/models/flag_chance_lookup.json | 2026 flag-chance test: decide CD4, ingest 2026 stints (OpenF1), freeze pre-registration, score once | CO-09, CO-12, **CD4** (human call), **CD6** (human call) |
| 25 | [CO-20](../wi/CO-20-flag-chance-plain-average-probe.md) | 4-chance | BLOCKED | 1-2d | `opus-5` | ml/src/flag_chance.py, ml/src/survival.py, transform/models/intermediate/int_stint_end_regime.sql, app/public/models/flag_chance_lookup.json, _roadmap/_ai-integration/wi/CO-08-flag-chance-calibration.md | Chance line probe: does a plain average of past outcomes (share of final stints that reached the flag, by context) work as the chance number across all seasons? | CO-17, **CD4** (human call), **CD5** (human call), **CD6** (human call) |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **CD4** (blocks `CO-08`, `CO-10`, `CO-20`) — Acceptance rule for the flag-chance line. The 10-bins-within-5-pp rule cannot be met reliably on one season. A: keep it (chance stays hidden, cap only). B: a race-clustered rule: average gap within 3 pp, intercept CI contains 0, slope CI contains 1. C: 5 wider bins pooled over the two latest seasons. _Recommended: A for now. Revisit with 2026 data as the first clean test._
- **CD5** (blocks `CO-08`, `CO-20`) — Where the chance number may appear. A: parquet and race replay only (E4 needs live field context, the browser simulator cannot run it), cap only in the simulator. B: E6 instead (simulator-known inputs, 0.0872 vs 0.0855 on selection; not scored on 2025 and cannot be now without another look). C: cap only everywhere. _Recommended: C for the simulator now; A later if the 2026 test passes under the rule chosen in CD4._
- **CD6** (blocks `CO-10`, `CO-20`) — Which fold scheme defines the flag-chance lookup and its 2026 test? A: expanding window (the project's existing CV; the shipped lookup matches it exactly). B: leave-one-season-out within 2018-2024 (the lookup differs by up to 0.012, and the 2024 weighting pick changes from last3 to uniform). _Recommended: A. It is the project's existing CV and the shipped lookup already matches it._
- **AD4** (blocks `AI-12`) — What is the launch cost and access limit? A: a paid plan with a hard daily spend cap. B: free allowance only. C: serve from the owner's machine through a tunnel. _Recommended: Decide at launch readiness, from AI-07's measured cost per answer. Paid plan with the Worker's counter as the real cap is the working assumption._
- **CD10** (blocks `AI-03`) — Which model version serves at launch? A: promote CO-18's retrain for all five models if the stint-life clean test (CO-14) passes; if it fails, promote it for the four models that pass and keep v14 for stint life. B: launch on v14 for everything and decide promotion after launch. C: promote CO-18's retrain for all five whatever CO-14 shows. _Recommended: None yet: rule on CO-14's, CO-18's and CO-19's results. A is the working assumption, subject to CO-19's go/no-go for its fail branch._
- **CD12** (blocks `CO-12`) — Start the OpenF1 2026 ingest (CO-12)? A: not now; there is no 2026 test under CD11. B: yes, ingest only, so 2026 data is ready if the test or the app ever needs it. _Recommended: A, consistent with CD11._

### Watch list — kept an eye on, not tasks and not rulings

_Generated from the watch rules in [`build-log.json`](build-log.json) (`watch_rules`); watch entries update automatically as items land or decisions resolve. A rule whose trigger needs something the log cannot see (a commit, a re-export, a rebuild, your ruling) stays open until its `resolved` and `resolution` are recorded._

**11 open** (0 ship-blockers). Full detail: `python3 _roadmap/_ai-integration/status/board.py --watch`. `python3 _roadmap/_ai-integration/status/board.py --ship` exits 1 while a ship-blocker is open.

Each watch rule is tagged with the recommended model (haiku/sonnet/opus) for token efficiency (3 haiku, 5 sonnet, 3 opus). The tag is the smallest model that can work the rule to its `clears_when`; step up a tier the moment the rule turns out to leave a choice open that the tag assumed was made.

- **`haiku`** — Maps to haiku-4-5. A binary check, or recording a resolution the evidence or the user has already settled: is it committed, did the named tests pass on the rebuild, write down the accept. The output has a mechanical check (a test result, a file list, git log).
- **`sonnet`** — Maps to sonnet-5. The fix or the options are written down in the rule: pick between two named options, run a named rebuild or export and check the pages, review a diff, reconcile counts, reword text to a meaning already settled.
- **`opus`** — Maps to opus-5 (fable-5.1 if the rule turns into a new estimator). Rules on a trade-off, designs the fix, audits a decision, or turns a measurement into a claim: label-moving changes, leakage boundaries, gate runs before a promotion.

| ID | Kind | Item | Model | What | Clears when |
| :--- | :--- | :--- | :--- | :--- | :--- |
| W17 | hazard | — | `haiku` | Plain python3 is macOS 3.9 on this machine; the project venv is 3.14 | PATH and pipeline.yml fixed, or the owner accepts it. |
| W5 | unverified | — | `haiku` | First green dbt CI run on main not confirmed | A green dbt CI run on main is seen and its run id recorded. |
| W3 | stale-artifact | CO-17 | `haiku` | data/dev.duckdb is not a trusted build | CO-17 (trusted full rebuild) has landed. |
| W12 | pending-ruling | CO-11, CD11 | `sonnet` | Does 'keep the line as it is' (CD11) include the relabel from v14 to 'refit of the v14 configuration'? | CO-11 lands, or the owner says the label stays. |
| W13 | pending-ruling | AI-02, CD11 | `opus` | May the assistant quote the experimental chance number? | AI-02 records the rule, or the owner rules. |
| W15 | pending-ruling | CO-10, CD8 | `opus` | Is 2026 still a clean season for the flag-chance test, given CD8 rejected it for stint life? | Ruled by the owner, or CO-10 closed. |
| W6 | gate-gap | CO-17 | `sonnet` | Byte oracle (CI Gate 1c) is stale and continue-on-error | Re-snapshotted on CO-17's build and continue-on-error removed. |
| W9 | debt | CO-02 | `sonnet` | Simulator CLIFF_SEVERITY_MIN/MAX are tuned to the old severity scale | Constants re-tuned to the current seed, or the clamp shown to be harmless; record which. |
| W10 | debt | CO-04 | `sonnet` | CO-04 leftovers: 4,655 thin-cell isolation laps left out (T18); third restart lap leans -0.18 s | Each is fixed in its own item or recorded as accepted debt by the owner. |
| W11 | debt | CO-16, CD7 | `opus` | Dirty air stays priced at lap grain; micro-sector pricing (CD7 option C) is a future project | Option C is raised as its own item, or dropped by the owner. |
| W16 | debt | — | `sonnet` | OSV-Scanner: 19 known dependency vulnerabilities not triaged | Triaged, with each fixed or accepted. |

<!-- END GENERATED TASKS -->

### Things to watch

- **Hash baseline gate is stale.** `transform/tests/model_hashes.baseline.json` (`snapshot_model_hashes.py --check`) was taken on full data (about 161k rows) but CI runs on the fixture (about 2.5k rows), so every hash differs. Gate 1c is `continue-on-error` since 2026-10-21; re-take the baseline on a reviewed build, then make it blocking again.
- **`assert_sector_aggregates_to_lap` warns on 152 rows.** Known latent defect in `int_sector_residual_decomposed`: the sector term uses the current lap's air share, the lap total uses the previous lap's. Warn-only until CD7 is ruled.
- **`assert_prior_season_labels_frozen` warns on 2 rows on CI only.** Fixture artifact: the frozen baselines come from full history and the fixture has only 3 small races. It is an error on every other target since 2026-10-21.
- **First green dbt CI run not yet confirmed.** dbt CI now runs on push to `main` (it never ran before 2026-10-21). The run on `6a6bdb6` was in progress at handoff.
- **CI fits fixtures go stale silently.** `transform/tests/fixtures/fits/` are copies of `data/fits/`; refresh after a car-FE or isotonic refit (command in `transform/tests/README.md`).
- **OSV-Scanner full scan fails** on known dependency vulnerabilities (19 in the Security tab). Not triaged.
- **Tactical grade set to `unvalidated` in `driver_isolation_method_scores.csv`.** The validator actually recorded `cancelled`, but the schema only accepts A/B/C/F/unvalidated, so the row was set to `unvalidated` to pass the not-null check. Revisit if tactical is re-run or if `cancelled` should be a distinct state (that would mean adding it to the schema's accepted values). Its `report_path` now points at the `wi-16-2026-10-03` report, matching the other rows.
