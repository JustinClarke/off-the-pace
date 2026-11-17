# AI-integration build order v2: assistant data access. Rules, and the ordered task list

**State lives in [`build-log.json`](build-log.json), and only there.** This file holds the rules
and one **generated** task list, spliced in at the bottom by the board. v1 is archived at
[`../../_archive/_ai-integration-v1/`](../../_archive/_ai-integration-v1/ARCHIVED.md).

A hand-written checklist here is a defect. Edit the JSON, run `--check`, then `--write-order`.

```bash
python3 _roadmap/_ai-integration/status/board.py                # the board, open rulings, next command
python3 _roadmap/_ai-integration/status/board.py --check        # invariants only; exit 1 on failure
python3 _roadmap/_ai-integration/status/board.py --order        # the ordered task list, to stdout
python3 _roadmap/_ai-integration/status/board.py --write-order  # ...and spliced into this file
python3 _roadmap/_ai-integration/status/board.py --watch        # the watch list in full
python3 _roadmap/_ai-integration/status/board.py --ship         # exit 1 while a ship-blocker is open
```

**Rules**

1. The pointer is the one item to run next. Run `--check` after every edit to the log.
2. A `BLOCKED` item waits on an open ruling (HD-\*) or on another track (XW wake calibration, XM ML redo). Put the ruling to the owner, with the options translated, before spawning work on it.
3. **Transform first.** TX items fix numbers the assistant would otherwise quote wrongly. No card (AX-07 onward) is built on a mart whose TX item is open.
4. **Class rule.** A card may only be published for a class that is live. Transform class goes live at AX-07; dirty-air-dependent at AX-15; traffic-cost at AX-16; ML at AX-17.
5. **Published-only rule.** Cards and query views are built from `app/public/data`, never straight from `data/dev.duckdb`. Parallel dbt work uses its own scratch folder with the copy named `dev.duckdb`.
6. **No model-written SQL, chart code or URLs**, ever.
7. Nothing is committed, published to the CDN or deployed without a yes from the owner. Agents never run `git add`, `commit` or `push`.
8. PK1 (2026-10-24: transform only; ML and assistant parked) still stands for AX items until HD1 is ruled. TX and AP items are inside it.
9. No archived dirty-air (DA-03) number and no chance-line number gets a card, as a fallback or otherwise.

<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-11-17T16:30:00+04:00`. Run `python3 _roadmap/_ai-integration/status/board.py --write-order` after any edit to the log._

**30 live items** (5 blocked). The pointer is on **TX-15** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 42 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Sources | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | [TX-15](../wi/TX-15-bronze-rebuild-parity.md) ▶ | 0a-bronze-honesty | MEASURED | 1d | `sonnet-5` | app/public/data/_manifest.json, data/bronze/MANIFEST.json, ingestion/known_gaps.txt, transform/dbt_project.yml, scripts/export_app_data.py | Rebuild on the 2026-11-16 Bronze in a scratch copy and diff against the published Nov-8 export (dropped races, row deltas, top movers) | — |
| 2 | [TX-16](../wi/TX-16-2018-italian-gp.md) | 0a-bronze-honesty | MEASURED | 0.5d | `sonnet-5` | ingestion/known_gaps.txt, scripts/export_app_data.py, app/src/features/data-quality-audit/, data/bronze/manifests/ | 2018 Italian GP: re-ingest, recorded gap shown as unavailable, or archived copy, as HD15 rules | TX-15 |
| 3 | [TX-17](../wi/TX-17-stint-dirty-air-null.md) | 0a-bronze-honesty | MEASURED | 1d | `opus-5` | transform/models/marts/fct_stint_features.sql, transform/models/marts/schema.yml, scripts/assistant_query_views.py | fct_stint_features: unmeasured dirty air becomes NULL with a reason, not 0 | TX-15 |
| 4 | [TX-19](../wi/TX-19-spa-clip-measure.md) | 0a-bronze-honesty | MEASURED | 0.5d | `sonnet-5` | transform/models/staging/stg_telemetry.sql, transform/models/reference/dim_corners.sql, transform/models/intermediate/int_corner_metrics.sql, transform/models/marts/mart_corner_skill_driver.sql | Measure what the 6,500 m telemetry distance clip removes, per circuit (Spa first), for HD16 | — |
| 5 | [TX-20](../wi/TX-20-spa-clip-lift.md) | 0a-bronze-honesty | MEASURED | 0.5-1d | `opus-5` | transform/models/staging/stg_telemetry.sql, transform/models/staging/stg_circuit_info.sql, transform/models/marts/mart_corner_skill_driver.sql | Change the telemetry distance clip as HD16 rules; diff the corner marts | TX-19 |
| 6 | [TX-21](../wi/TX-21-doc-fixes-track-status-gaps.md) | 0a-bronze-honesty | MEASURED | 0.25d | `sonnet-5` | transform/models/staging/src_formula1.yml, ingestion/SCHEMA.md, ingestion/known_gaps.txt, transform/models/staging/stg_laps.sql | Doc fixes: track-status codes (5=red, 6/7=VSC), 2018 R (not Q) Bahrain empty channels, the 2024 race-control clock note | — |
| 7 | [AX-24](../wi/AX-24-car-ahead-off-published.md) | 1-transform | SPEC | 1d | `sonnet-5` | transform/models/intermediate/int_lap_air_state.sql, transform/models/intermediate/int_lap_proximity.sql | No published number depends on DriverAhead or DistanceToDriverAhead (D2) | — |
| 8 | [TX-29](../wi/TX-29-holdout-2025.md) | 1-transform | MEASURED | 1-2d | `opus-5` | transform/dbt_project.yml, ml/src/holdout_config.py, ml/src/features.py, transform/tasks/coefficients/fit_compound_cliff.py, transform/tasks/coefficients/fit_dirty_air_microsector.py, transform/tasks/wake_calibration/, ml/src/card.py | Move the holdout to 2025 across transform and ML (train strictly 2018-2024); guard test that no fit reads 2025 or 2026 | — |
| 9 | [AX-23](../wi/AX-23-dirty-air-off-surface.md) | 2-app-fixes | SPEC | 0.5d | `sonnet-5` | app/src/nav/routes.ts, app/src/features/dirty-air-cost | Take dirty-air cost off the product surface (D1) | — |
| 10 | [AX-26](../wi/AX-26-held-wording-and-tax-label.md) | 2-app-fixes | SPEC | 0.5d | `sonnet-5` | app/src/assistant/cards/sql/heldStubs.ts, app/src/assistant/honesty/policy.json | Held-card wording and the unvalidated label on the flat tax (D4 and D5) | — |
| 11 | [AX-27](../wi/AX-27-denoising-rules.md) | 3-foundations | SPEC | 0d | `sonnet-5` | _roadmap/_ai-integration/status/build-log.json | Denoising rules for any future lap-time measure (constraint) | — |
| 12 | [TX-18](../wi/TX-18-ghost-zero-fills.md) | 0a-bronze-honesty | MEASURED | 1d | `opus-5` | transform/models/marts/fct_ghost_race_finish.sql, transform/models/marts/fct_ghost_car_pace.sql, transform/models/marts/schema.yml, app/src/features/hidden-performance/, scripts/mc_finish_order.py | Ghost marts: rule which 0-fills are a declared field-average prior (flag it) and which are missing (NULL); no SE filled with 0 | TX-15, **HD20** (human call) |
| 13 | [TX-30](../wi/TX-30-transform-honesty-sweep.md) | 0a-bronze-honesty | SPEC | 3d | `opus-5` | transform/models/intermediate/int_lap_residual_decomposed.sql, transform/models/marts/fct_stint_features.sql, transform/models/marts/fct_ghost_car_pace.sql, transform/models/marts/fct_ghost_race_finish.sql, transform/models/staging/stg_telemetry.sql, transform/tests/assert_stg_telemetry_distance_bound.sql, transform/seeds/race_to_track.csv, docs/reference/models/stg/stg_telemetry.mdx, transform/tests/model_hashes.baseline.json | Transform honesty sweep: one scratch rebuild, one diff review | TX-15, TX-16, TX-17, TX-18, TX-19, TX-20, TX-21 |
| 14 | [TX-23](../wi/TX-23-quali-corner-skill.md) | 0b-new-data | SPEC | 2-3d | `opus-5` | transform/models/staging/src_formula1.yml, transform/models/staging/stg_telemetry.sql, transform/models/intermediate/int_corner_metrics.sql, transform/models/marts/mart_corner_skill_driver.sql, transform/models/staging/stg_telemetry_qualifying.sql (new) | Qualifying telemetry into a separate qualifying corner-skill mart (Q glob is missed today) | TX-30 |
| 15 | [TX-26](../wi/TX-26-race-control-detail.md) | 0b-new-data | SPEC | 1-2d | `opus-5` | transform/models/staging/stg_race_control.sql, transform/models/staging/src_formula1.yml, ingestion/src/ingest.py, transform/models/marts/fct_race_control_events.sql (new) | Race-control detail (blue flags, investigations, sector yellows) joined to laps on the corrected clock and to circuit markers | TX-30 |
| 16 | [TX-27](../wi/TX-27-jolpica-pit-crosscheck.md) | 0b-new-data | MEASURED | 1d | `sonnet-5` | transform/models/staging/stg_pits.sql, transform/models/staging/stg_lap_tyre_qa.sql, ingestion/src/jolpica_client.py, transform/models/marts/fct_pit_stop_crosscheck.sql (new) | Jolpica pit_stops as an independent cross-check of stg_pits, shown as a separate measured source | TX-30 |
| 17 | [AP-09](../wi/AP-09-new-data-pages.md) | 0b-new-data | SPEC | 2-3d | `sonnet-5` | scripts/export_app_data.py, app/src/features/, app/src/nav/routes.ts, docs/app/ | App pages for the new measured marts: qualifying corner skill, track limits, speed traps, race-control detail, pit cross-check | TX-23, TX-26, TX-27, TX-30 |
| 18 | [AX-28](../wi/AX-28-new-data-cards.md) | 0b-new-data | SPEC | 2d | `opus-5` | app/src/assistant/cards/kinds.ts, app/src/assistant/cards/registry.ts, scripts/assistant_query_views.py, app/src/assistant/cards/lineage.test.ts | Card kinds and qv_* query views for the new measured marts (transform class) | AP-09, AX-24, TX-29, TX-30, TX-23, TX-26, TX-27 |
| 19 | [TX-28](../wi/TX-28-raw-channels.md) | 0b-new-data | SPEC | 2d+ | `opus-5` | transform/models/staging/stg_telemetry_position.sql, transform/models/intermediate/int_lap_proximity.sql, data/bronze/telemetry_full/, data/bronze/pos_data/ | Raw pos_data and car_data (telemetry_full) channels into staging, with per-session coverage; no mart until a consumer is ruled | TX-30, AX-24 |
| 20 | [TX-09](../wi/TX-09.md) | 1-transform | BLOCKED | 0.5d | `sonnet-5` | data/fits/degradation_isotonic.parquet, transform/tasks/coefficients/fit_degradation_isotonic.py, transform/models/marts/mart_degradation_history_envelope.sql | Refit the degradation-envelope isotonic file | **XM** (human call) |
| 21 | [AX-10](../wi/AX-10.md) | 4-assistant | MEASURED | 2d | `sonnet-5` | app/src/nav/assistantTools.ts, worker/src/, app/src/assistant/honesty/ | Assistant core v2: dispatcher for the 7 tools, page-card pre-load, loop cap 4, per-slot budget meter, checker repair turn, headless CLI | AX-24, TX-29, TX-30, TX-23, TX-26, TX-27 |
| 22 | [AX-12](../wi/AX-12.md) | 4-assistant | MEASURED | 1-2d | `sonnet-5` | worker/src/handler.ts, worker/src/config.ts, worker/src/ledger.ts, firebase.json | Worker v2: one ticket per question, per-question limit, cap at or under the free allowance, generated tools, 409 on version skew, CSP | AX-24, TX-29, TX-30, TX-23, TX-26, TX-27 |
| 23 | [AX-13](../wi/AX-13.md) | 4-assistant | MEASURED | 3d | `sonnet-5` | docs/app/, app/src/assistant/ | Analyst eval v2: questions per class, grader, pass bar fixed before the first run, measured baseline | AX-10, AX-24, TX-29, TX-30, TX-23, TX-26, TX-27 |
| 24 | [AX-14](../wi/AX-14.md) | 4-assistant | MEASURED | 3d | `sonnet-5` | app/src/ui/layout/AppShell.tsx, app/src/ui/feedback/, app/src/nav/ | Chat drawer with render-time grounding and measured / modelled / unavailable rendering, behind a flag (off) | AX-10, AX-12, AX-24, TX-29, TX-30, TX-23, TX-26, TX-27 |
| 25 | [AX-15b](../wi/AX-15b.md) | 5-held-classes | BLOCKED | 2-3d | `opus-5` | transform/models/marts/, app/src/features/, scripts/export_app_data.py | Make the dirty-air-dependent cards live once wake calibration is settled and the label is re-sealed if it moves | TX-17, TX-18, **XW** (human call) |
| 26 | [AX-16](../wi/AX-16.md) | 5-held-classes | BLOCKED | 2d | `opus-5` | _roadmap/_archive/_wake-calibration/wi/WC-06-app-output.md, app/src/features/dirty-air-cost/ | Traffic-cost cards from the wake-calibration outputs (WC-06) | AX-15b, **XW** (human call) |
| 27 | [AX-17](../wi/AX-17.md) | 5-held-classes | BLOCKED | 2d | `opus-5` | ml/models/manifest.json, ml/src/predict.py, scripts/export_app_data.py, app/src/ml/ | ML cards: prediction bands, in-envelope flag, cliff probabilities, model metrics, blind test | **XM** (human call) |
| 28 | [AX-18](../wi/AX-18.md) | 5-held-classes | BLOCKED | 1d | `opus-5` | transform/models/intermediate/int_pit_strategy_value.sql, app/src/features/pit-strategy/ | Pit-call verdict cards with the measured reproduction rate | AX-17, **XM** (human call) |
| 29 | [AX-19](../wi/AX-19.md) | 6-launch | SPEC | 0.5d | `sonnet-5` | app/public/data/_manifest.json | Freeze: snapshot of manifest version, card checksums, catalogue, label and model versions | AX-13, AX-14 |
| 30 | [AX-20](../wi/AX-20.md) | 6-launch | SPEC | 1d | `sonnet-5` | app/src/ui/layout/AppShell.tsx, firebase.json | Launch run through the real drawer and Worker on the frozen snapshot; owner switches the flag on | AX-19 |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **XW** (blocks `AX-15b`, `AX-16`) — EXTERNAL: wake calibration reaches WC-06 (app output) with its labels. _Recommended: Not an owner call; wait._
- **XM** (blocks `AX-17`, `AX-18`, `TX-09`) — EXTERNAL: the ML redo lands, CD10 (promotion) is ruled, and the D9/D14 re-measures are recorded. _Recommended: Not an owner call; wait._
- **HD18** (blocks nothing) — Delete old data: PENDING the owner's confirmation of WHAT to delete. Two reads of the instruction: (a) delete data/_archive-2026-11-14/ and data/staging/; (b) delete the old models the new ones replace (ml/models/ v14 boosters and ONNX, ml/artefacts/, any fits). Nothing is deleted until you say which. _Recommended: Confirm which read (recommendation): if (a), wait until TX-15's parity report and HD15 are done, because the archived DBs hold the only built 2018_14 rows; if (b), wait until models retrained on 2018-2024 (TX-29) exist. No agent deletes data._
- **HD20** (blocks `TX-18`) — Ghost-car 0 fills (TX-18): when a constructor has no pace cell (1,122 lap rows) or no degradation cell for a compound (about 77,000 lap rows each side), the ghost car uses 0, i.e. 'the same as the field average'. A: keep 0 as a declared prior, flagged per row (*_is_prior, already added) and named in the page method note. B: treat it as missing: those laps (or scenarios) get no ghost prediction (NULL with a reason). C: A for the degradation slopes (ego == host must cancel exactly), B for constructor pace. _Recommended: C (recommendation, not a ruling): the slope fill is a modelling choice the code documents (ego == host is exactly 0); a missing constructor pace is a missing car, which a 0 hides._

### Watch list — kept an eye on, not tasks and not rulings

_Generated from the watch rules in [`build-log.json`](build-log.json) (`watch_rules`); watch entries update automatically as items land or decisions resolve. A rule whose trigger needs something the log cannot see (a commit, a re-export, a rebuild, your ruling) stays open until its `resolved` and `resolution` are recorded._

**7 open** (1 ship-blocker). Full detail: `python3 _roadmap/_ai-integration/status/board.py --watch`. `python3 _roadmap/_ai-integration/status/board.py --ship` exits 1 while a ship-blocker is open.

Each watch rule is tagged with the recommended model (haiku/sonnet/opus) for token efficiency (0 haiku, 5 sonnet, 2 opus). The tag is the smallest model that can work the rule to its `clears_when`; step up a tier the moment the rule turns out to leave a choice open that the tag assumed was made.

- **`haiku`** — Maps to haiku-4-5. A binary check, or recording a resolution the evidence or the user has already settled: is it committed, did the named tests pass on the rebuild, write down the accept. The output has a mechanical check (a test result, a file list, git log).
- **`sonnet`** — Maps to sonnet-5. The fix or the options are written down in the rule: pick between two named options, run a named rebuild or export and check the pages, review a diff, reconcile counts, reword text to a meaning already settled.
- **`opus`** — Maps to opus-5 (fable-5.1 if the rule turns into a new estimator). Rules on a trade-off, designs the fix, audits a decision, or turns a measurement into a claim: label-moving changes, leakage boundaries, gate runs before a promotion.

| ID | Kind | Item | Model | What | Clears when |
| :--- | :--- | :--- | :--- | :--- | :--- |
| AXW1 | ship-blocker | AX-12 | `sonnet` | No public Worker route without the per-question limit and a cap at or under the free allowance | AX-20 lands with the real cap. |
| AXW2 | hazard | AX-16 | `sonnet` | No archived DA-03 number, and no flat 0.331 x share price presented as measured traffic cost | AX-16 lands with the deny-list test in CI. |
| AXW4 | hazard | AX-08 | `sonnet` | Catalogue and tool skew between the app and the Worker | The 409 version check is tested and deployed (AX-12). |
| AXW7 | unverified | AX-12 | `sonnet` | gpt-oss-20b: tool calls confirmed; effort parameter and reasoning-token accounting against MAX_OUTPUT_TOKENS (2500) still unconfirmed | Confirmed from the model page and measured in AX-13. |
| AXW14 | stale-artifact | TX-15 | `sonnet` | The published export and every card were built on the old (pre-2026-11-14) Bronze | TX-15's parity report is read by the owner, TX-16/17/18 have landed, TX-30's single diff review is done (step k), and an owner-approved re-export and card rebuild on the new Bronze are recorded here. |
| AXW6 | pending-ruling | AX-17 | `opus` | The chance line stays EXCLUDE (AD5): no card kind may read flag_chance_lookup.json | The registry guard test exists (AX-17). |
| AXW8 | pending-ruling | AX-18 | `opus` | D9/D14 re-measures owed on the redo model; pit-verdict cards stay held | The re-measure is recorded (XM resolved). |

<!-- END GENERATED TASKS -->
