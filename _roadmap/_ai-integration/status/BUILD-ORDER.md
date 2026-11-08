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

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-11-08T23:55:00+04:00`. Run `python3 _roadmap/_ai-integration/status/board.py --write-order` after any edit to the log._

**12 live items** (5 blocked). The pointer is on **TX-14** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 36 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Sources | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | [TX-14](../wi/TX-14.md) ▶ | 1-transform | MEASURED | 1d | `sonnet-5` | transform/models/marts/fct_driver_isolation_stint.sql, transform/models/intermediate/int_pit_strategy_cost_curve.sql, transform/models/intermediate/int_sector_residual_decomposed.sql, transform/scripts/snapshot_model_hashes.py | Three models change output between identical builds: find the cause before the baselines are re-taken | — |
| 2 | [AX-10](../wi/AX-10.md) | 4-assistant | MEASURED | 2d | `sonnet-5` | app/src/nav/assistantTools.ts, worker/src/, app/src/assistant/honesty/ | Assistant core v2: dispatcher for the 7 tools, page-card pre-load, loop cap 4, per-slot budget meter, checker repair turn, headless CLI | — |
| 3 | [AX-12](../wi/AX-12.md) | 4-assistant | MEASURED | 1-2d | `sonnet-5` | worker/src/handler.ts, worker/src/config.ts, worker/src/ledger.ts, firebase.json | Worker v2: one ticket per question, per-question limit, cap at or under the free allowance, generated tools, 409 on version skew, CSP | — |
| 4 | [AX-13](../wi/AX-13.md) | 4-assistant | MEASURED | 3d | `sonnet-5` | docs/app/, app/src/assistant/ | Analyst eval v2: questions per class, grader, pass bar fixed before the first run, measured baseline | AX-10 |
| 5 | [AX-14](../wi/AX-14.md) | 4-assistant | MEASURED | 3d | `sonnet-5` | app/src/ui/layout/AppShell.tsx, app/src/ui/feedback/, app/src/nav/ | Chat drawer with render-time grounding and measured / modelled / unavailable rendering, behind a flag (off) | AX-10, AX-12 |
| 6 | [AX-19](../wi/AX-19.md) | 6-launch | SPEC | 0.5d | `sonnet-5` | app/public/data/_manifest.json | Freeze: snapshot of manifest version, card checksums, catalogue, label and model versions | AX-13, AX-14 |
| 7 | [AX-20](../wi/AX-20.md) | 6-launch | SPEC | 1d | `sonnet-5` | app/src/ui/layout/AppShell.tsx, firebase.json | Launch run through the real drawer and Worker on the frozen snapshot; owner switches the flag on | AX-19 |
| 8 | [TX-09](../wi/TX-09.md) | 1-transform | BLOCKED | 0.5d | `sonnet-5` | data/fits/degradation_isotonic.parquet, transform/tasks/coefficients/fit_degradation_isotonic.py, transform/models/marts/mart_degradation_history_envelope.sql | Refit the degradation-envelope isotonic file | **XM** (human call) |
| 9 | [AX-15b](../wi/AX-15b.md) | 5-held-classes | BLOCKED | 2-3d | `opus-5` | transform/models/marts/, app/src/features/, scripts/export_app_data.py | Make the dirty-air-dependent cards live once wake calibration is settled and the label is re-sealed if it moves | **XW** (human call) |
| 10 | [AX-16](../wi/AX-16.md) | 5-held-classes | BLOCKED | 2d | `opus-5` | _roadmap/_wake-calibration/wi/WC-06-app-output.md, app/src/features/dirty-air-cost/ | Traffic-cost cards from the wake-calibration outputs (WC-06) | AX-15b, **XW** (human call) |
| 11 | [AX-17](../wi/AX-17.md) | 5-held-classes | BLOCKED | 2d | `opus-5` | ml/models/manifest.json, ml/src/predict.py, scripts/export_app_data.py, app/src/ml/ | ML cards: prediction bands, in-envelope flag, cliff probabilities, model metrics, blind test | **XM** (human call) |
| 12 | [AX-18](../wi/AX-18.md) | 5-held-classes | BLOCKED | 1d | `opus-5` | transform/models/intermediate/int_pit_strategy_value.sql, app/src/features/pit-strategy/ | Pit-call verdict cards with the measured reproduction rate | AX-17, **XM** (human call) |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **XW** (blocks `AX-15b`, `AX-16`) — EXTERNAL: wake calibration reaches WC-06 (app output) with its labels. _Recommended: Not an owner call; wait._
- **XM** (blocks `AX-17`, `AX-18`, `TX-09`) — EXTERNAL: the ML redo lands, CD10 (promotion) is ruled, and the D9/D14 re-measures are recorded. _Recommended: Not an owner call; wait._

### Watch list — kept an eye on, not tasks and not rulings

_Generated from the watch rules in [`build-log.json`](build-log.json) (`watch_rules`); watch entries update automatically as items land or decisions resolve. A rule whose trigger needs something the log cannot see (a commit, a re-export, a rebuild, your ruling) stays open until its `resolved` and `resolution` are recorded._

**7 open** (1 ship-blocker). Full detail: `python3 _roadmap/_ai-integration/status/board.py --watch`. `python3 _roadmap/_ai-integration/status/board.py --ship` exits 1 while a ship-blocker is open.

Each watch rule is tagged with the recommended model (haiku/sonnet/opus) for token efficiency (1 haiku, 4 sonnet, 2 opus). The tag is the smallest model that can work the rule to its `clears_when`; step up a tier the moment the rule turns out to leave a choice open that the tag assumed was made.

- **`haiku`** — Maps to haiku-4-5. A binary check, or recording a resolution the evidence or the user has already settled: is it committed, did the named tests pass on the rebuild, write down the accept. The output has a mechanical check (a test result, a file list, git log).
- **`sonnet`** — Maps to sonnet-5. The fix or the options are written down in the rule: pick between two named options, run a named rebuild or export and check the pages, review a diff, reconcile counts, reword text to a meaning already settled.
- **`opus`** — Maps to opus-5 (fable-5.1 if the rule turns into a new estimator). Rules on a trade-off, designs the fix, audits a decision, or turns a measurement into a claim: label-moving changes, leakage boundaries, gate runs before a promotion.

| ID | Kind | Item | Model | What | Clears when |
| :--- | :--- | :--- | :--- | :--- | :--- |
| AXW1 | ship-blocker | AX-12 | `sonnet` | No public Worker route without the per-question limit and a cap at or under the free allowance | AX-20 lands with the real cap. |
| AXW2 | hazard | AX-16 | `sonnet` | No archived DA-03 number, and no flat 0.331 x share price presented as measured traffic cost | AX-16 lands with the deny-list test in CI. |
| AXW4 | hazard | AX-08 | `sonnet` | Catalogue and tool skew between the app and the Worker | The 409 version check is tested and deployed (AX-12). |
| AXW13 | uncommitted | AX-00 | `haiku` | This restructure lives only in the working tree: the archive, the new board, the evidence folder and the wi docs | Owner commits it and records it here. |
| AXW7 | unverified | AX-12 | `sonnet` | gpt-oss-20b tool-call support on Workers AI, and reasoning tokens against MAX_OUTPUT_TOKENS=800, not re-confirmed | Confirmed from the model page and measured in AX-13. |
| AXW6 | pending-ruling | AX-17 | `opus` | The chance line stays EXCLUDE (AD5): no card kind may read flag_chance_lookup.json | The registry guard test exists (AX-17). |
| AXW8 | pending-ruling | AX-18 | `opus` | D9/D14 re-measures owed on the redo model; pit-verdict cards stay held | The re-measure is recorded (XM resolved). |

<!-- END GENERATED TASKS -->
