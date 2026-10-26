# Dirty-air build order: rules and the ordered task list

**State lives in [`build-log.json`](build-log.json), and only there.** This file holds the rules
and one **generated** task list, spliced in at the bottom by the board.

A hand-written checklist here is a defect. Edit the JSON, run `--check`, then `--write-order`.
Never type into the generated block.

```bash
python3 _roadmap/_dirty-air/status/board.py                # the board, open decisions, next command
python3 _roadmap/_dirty-air/status/board.py --check        # invariants only; exit 1 on failure
python3 _roadmap/_dirty-air/status/board.py --order        # the ordered task list, to stdout
python3 _roadmap/_dirty-air/status/board.py --write-order  # ...and spliced into this file
python3 _roadmap/_dirty-air/status/board.py --watch        # the watch list in full
python3 _roadmap/_dirty-air/status/board.py --ship         # exit 1 while a ship-blocker is open
```

**Rules**

1. The pointer is the one item to run next. Run `--check` after every edit.
2. A `BLOCKED` item waits on an open decision. Put the decision to the owner first, with the options
   translated, before spawning work on it.
3. Nothing is committed or deployed without a yes from the owner.
4. No label moves before the Phase 4 gate. Path B is a label-version change and goes through the
   ML retrain plan.

<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-10-26T13:06:32+04:00`. Run `python3 _roadmap/_dirty-air/status/board.py --write-order` after any edit to the log._

**5 live items** (1 blocked). The pointer is on **DA-02P** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 1 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

| # | Item | Group | Stage | Cost | Model | Sources | Task | Waiting on |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | [DA-02](../wi/DA-02-tables.md) | 1-tables | SPEC | 3-4 wk | `opus-5` | transform/models/intermediate/, transform/tests/ | Sample-level and micro-sector proximity tables, tests, and loss-versus-gap curves | — |
| 2 | [DA-02P](../wi/DA-02P-prerequisites.md) ▶ | 1-tables | MEASURED | 1-2 wk | `opus-5` | transform/models/intermediate/, transform/models/staging/stg_telemetry_position.sql, _roadmap/_dirty-air/wi/DA-03-preregistration.md | Prerequisites before the fit: P3 corner-class map, DRS state, pre-registration amendment | DA-02 |
| 3 | [DA-03](../wi/DA-03-identification.md) | 2-identification | SPEC | 4-6 wk | `fable-5.1` | transform/tasks/coefficients/ | Identification: pre-registered fit, placebos P1-P3, era split (2018-21 vs 2022+) | DA-02, DA-02P |
| 4 | [DA-04](../wi/DA-04-validation.md) | 3-validation | SPEC | 3-4 wk | `opus-5` | transform/tests/ | Held-out season fit, honesty tests, out-of-sample gain check | DA-03 |
| 5 | [DA-05](../wi/DA-05-label-and-app.md) | 4-label-app | BLOCKED | 3 wk (A) / 6+ wk (B) | `opus-5` | transform/models/marts/, app/src/features/ | Label and app decision: path A (sit beside) or path B (replace tax, label version) | DA-04, **DD2** (human call) |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **DD2** (blocks `DA-05`) — Path A first (sit beside the label, no label version, about 3 weeks of app work), path B later? Or path B from the start (label version, about 6+ weeks)? _Recommended: A first. It answers the question and ships without touching the label; B is decided on A's evidence._

### Watch list — kept an eye on, not tasks and not rulings

_Generated from the watch rules in [`build-log.json`](build-log.json) (`watch_rules`); watch entries update automatically as items land or decisions resolve. A rule whose trigger needs something the log cannot see (a commit, a re-export, a rebuild, your ruling) stays open until its `resolved` and `resolution` are recorded._

**2 open** (0 ship-blockers). Full detail: `python3 _roadmap/_dirty-air/status/board.py --watch`. `python3 _roadmap/_dirty-air/status/board.py --ship` exits 1 while a ship-blocker is open.

Each watch rule is tagged with the recommended model (haiku/sonnet/opus) for token efficiency (1 haiku, 1 sonnet, 0 opus). The tag is the smallest model that can work the rule to its `clears_when`; step up a tier the moment the rule turns out to leave a choice open that the tag assumed was made.

- **`haiku`** — Maps to haiku-4-5. A binary check, or recording a resolution the evidence or the user has already settled: is it committed, did the named tests pass on the rebuild, write down the accept. The output has a mechanical check (a test result, a file list, git log).
- **`sonnet`** — Maps to sonnet-5. The fix or the options are written down in the rule: pick between two named options, run a named rebuild or export and check the pages, review a diff, reconcile counts, reword text to a meaning already settled.
- **`opus`** — Maps to opus-5 (fable-5.1 if the rule turns into a new estimator). Rules on a trade-off, designs the fix, audits a decision, or turns a measurement into a claim: label-moving changes, leakage boundaries, gate runs before a promotion.

| ID | Kind | Item | Model | What | Clears when |
| :--- | :--- | :--- | :--- | :--- | :--- |
| W1 | stale-artifact | DA-01 | `haiku` | Dev warehouse is stale until CO-17 rebuilds it (in the _ai-integration log) | CO-17 has landed in _roadmap/_ai-integration/status/build-log.json and the audit is re-run on it. |
| W2 | pending-ruling | DA-01 | `sonnet` | IsAccurate may drop 2018 race laps for a reason unrelated to the lap | Split the is_accurate false share by season for race laps, and record whether 2018 is an outlier. Then decide whether to keep the gate for 2018 or flag it. |

<!-- END GENERATED TASKS -->

## Audit recommendations (hand-written, 2026-10-25)

Source: Opus audit of this track. Advice only. The generated block above does not track these. Record each item in build-log.json when it starts.

**Summary.** Design is mostly sound. Nothing has been fitted on real data. Blockers are your commits and one hash. None of this work moves the cliff or stint-life labels, so the seal is safe.

**Order of work**
1. **Agent:** add a gap spec at boundary m-1 (shares no crossing with the outcome), so timing noise cannot pass the main gate on its own. Add an overall gate verdict to the fit that checks the sign of beta(lt1), P1, P2 and P3. Add a hash check that confirms the file is committed and matches the logged hash. Fix the DRS wording in the "not ruled out" paragraph of the amendment draft. Fix DD9 (old P3 rule) and DD10 (280 still "to be confirmed").
2. **You:** approve the amendment text after step 1.
3. **You:** commit the model, test and estimator edits, then the pre-registration alone, then record its SHA-256 in build-log.json.
4. **Agent (bookkeeping):** mark DA-02 LANDED (committed in 82796dc, evidence present). Clear W1 (CO-17 landed, audit re-run on the rebuilt dev: 20 of 21 CSVs identical).
5. **Agent:** register the DA-04 out-of-sample gain metric before any run.
6. **Agent:** run DA-03 on a scratch copy, using the recorded hash. Run it alone, not alongside dbt (about 3M rows, roughly 158k lap effects, run pooled and per era).
7. **You:** read the gate result before anything else.
8. **Only if everything passes:** path A replay first. Path B later, as a separate label version with its own retrain.

**Can be deferred:** marshal-sector ingestion (DD3), W2 (2018 is_accurate check), the 10-micro-sector sensitivity, metres, the sample-level table.

**Would not do**
- Start path B, or fold it into the seal.
- Change thresholds after seeing a coefficient.
- Let drs_closed or a passing sensitivity rescue a failed primary result.
- Run the fit against data/dev.duckdb directly.

**Known risks**
- P1 and P2 may fail on small real effects with about 3M rows. Expect possible false fails and read them as caveats.
- Results cover 2018 to 2025 only, and say nothing about 2026 (no DRS, new rules).
