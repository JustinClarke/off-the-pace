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
10. **Model policy (owner, 2026-11-18).** Every task runs on `sonnet-5`. Sonnet agents do the execution: rebuilds, diffs, test edits, doc fixes, clip and seed edits once the rule is set. Anything that settles a feature's logic (a NULL-vs-prior choice, a ruling, a leakage boundary, a contract change) is put to the owner as a decision in `build-log.json` and is not decided by a model. The owner may name an Opus pass for a specific decision; none is set yet.

## At a glance

Detail lives in `build-log.json` and the `wi/` docs; the tables below hold only id, name, stage, waits and owner decision.

**Categories** (item counts in the generated tables)

1. Transform close (data honesty): TX-15 to TX-21, TX-29, TX-30, TX-31, DM-01, DM-02, DM-03, DM-07, AX-27, AUD-01 to AUD-14.
2. Launch of the assistant (AI work): AP-09, AP-10, AX-28, AX-10, AX-12, AX-13, AX-14.
3. New data features: TX-23, TX-26, TX-27, TX-28.
4. Launch: AX-19, AX-20.
5. Held or after launch: dirty air (AX-23, AX-24, AX-26, AX-15b, AX-16, DM-04), ML (AX-17, AX-18, ML-01, DM-06, TX-09, AUD-15), UNC-01, DM-05 (ghost, waits on HD20).

**Critical path:** 1. TX-15, 2. TX-16/17/19/20/21, 3. TX-30, 4. TX-31/TX-29/TX-23/26/27/28, 5. AP-09, 6. AX-28/AX-10/AX-12, 7. AX-13/AX-14, 8. AX-19, 9. AX-20 (owner switch-on). Held items start only after AX-20.

**Owner decisions waiting**

- HD20: ghost-car 0 fills, keep as flagged prior or NULL (gates TX-18, DM-05).
- HD18: which old data to delete.
- DM-02: all-wet race gets a no-estimate row with a reason?
- TX-30: one diff review and re-export.
- AX-20: the yes to switch on.

Dirty air is held because the car-ahead field is internal only (`assert_car_ahead_field_internal_only`) and the 0.331 tax is unvalidated.

<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->

_Generated from [`build-log.json`](build-log.json) at `updated: 2026-11-19T12:59:00+04:00`. Run `python3 _roadmap/_ai-integration/status/board.py --write-order` after any edit to the log._

**58 live items** (5 blocked). The pointer is on **TX-15** — that is the one to run next; the rest of the order is what becomes runnable after it, with anything waiting on one of your rulings sorted behind the work that isn't. 42 terminal items are finished and not listed here — run `board.py` for the per-group view, or read their `closed` field in [`build-log.json`](build-log.json).

#### 1. Transform close (data honesty) (29)

_Fix the numbers the assistant would otherwise quote wrongly._

| # | Item | Stage | Waits on | Owner decision |
| ---: | :--- | :--- | :--- | :--- |
| 1 | [TX-15](../wi/TX-15-bronze-rebuild-parity.md) ▶ Rebuild on the 2026-11-16 Bronze in a… | MEASURED | — | — |
| 2 | [TX-16](../wi/TX-16-2018-italian-gp.md) 2018 Italian GP: re-ingest, recorded gap… | MEASURED | TX-15 | — |
| 3 | [TX-17](../wi/TX-17-stint-dirty-air-null.md) fct_stint_features: unmeasured dirty air… | MEASURED | TX-15 | — |
| 4 | [TX-19](../wi/TX-19-spa-clip-measure.md) Measure what the 6,500 m telemetry distance… | MEASURED | — | — |
| 5 | [TX-20](../wi/TX-20-spa-clip-lift.md) Change the telemetry distance clip as HD16… | MEASURED | TX-19 | — |
| 6 | [TX-21](../wi/TX-21-doc-fixes-track-status-gaps.md) Doc fixes: track-status codes (5=red… | MEASURED | — | — |
| 7 | [AUD-01](../wi/AUD-00-model-triage.md) Audit staging and reference: 24 models, 24… | SPEC | TX-15 | — |
| 8 | [AUD-02](../wi/AUD-00-model-triage.md) Audit lap spine, fuel, stint regime, SC… | SPEC | AUD-01 | — |
| 9 | [AUD-03](../wi/AUD-00-model-triage.md) Audit telemetry, corners, proximity, air… | SPEC | AUD-02 | — |
| 10 | [AUD-04](../wi/AUD-00-model-triage.md) Audit new-data marts (not in the manifest)… | SPEC | AUD-01 | — |
| 11 | [TX-29](../wi/TX-29-holdout-2025.md) Move the holdout to 2025 across transform… | MEASURED | — | — |
| 12 | [AX-27](../wi/AX-27-denoising-rules.md) Denoising rules for any future lap-time… | SPEC | — | — |
| 13 | [TX-18](../wi/TX-18-ghost-zero-fills.md) Ghost marts: rule which 0-fills are a… | MEASURED | TX-15 | HD20 |
| 14 | [AUD-05](../wi/AUD-00-model-triage.md) Audit compound curve, field pace, thermal… | SPEC | AUD-02 | HD26 |
| 15 | [AUD-06](../wi/AUD-00-model-triage.md) Audit track evolution and its readers: 4… | SPEC | AUD-05 | — |
| 16 | [AUD-07](../wi/AUD-00-model-triage.md) Audit constructor structural pace (race): 1… | SPEC | AUD-06 | — |
| 17 | [AUD-08](../wi/AUD-00-model-triage.md) Audit dirty-air tax: 1 model, 0 ROBUST / 0… | SPEC | AUD-03, AUD-06 | — |
| 18 | [AUD-09](../wi/AUD-00-model-triage.md) Audit lap residual identity and lap marts: 8… | SPEC | AUD-07, AUD-08 | — |
| 19 | [AUD-10](../wi/AUD-00-model-triage.md) Audit driver ratings, affinities, race and… | SPEC | AUD-09 | HD27 |
| 20 | [AUD-11](../wi/AUD-00-model-triage.md) Audit qualifying chain: 6 models, 2 ROBUST /… | SPEC | AUD-09 | HD25, HD27 |
| 21 | [AUD-12](../wi/AUD-00-model-triage.md) Audit stint features, pit strategy, tyre… | SPEC | AUD-09, AUD-05 | HD25, HD26 |
| 22 | [AUD-13](../wi/AUD-00-model-triage.md) Audit ghost chain: 4 models, 0 ROBUST / 1… | SPEC | AUD-07, AUD-09 | — |
| 23 | [AUD-14](../wi/AUD-00-model-triage.md) Audit driver isolation: 8 models, 8 ROBUST /… | SPEC | AUD-12 | — |
| 24 | [TX-30](../wi/TX-30-transform-honesty-sweep.md) Transform honesty sweep: one scratch… | SPEC | TX-15, TX-16, TX-17, TX-18, TX-19, TX-20, TX-21, AUD-01, AUD-02, AUD-03, AUD-05, AUD-06, AUD-07, AUD-08, AUD-09, AUD-10, AUD-11, AUD-12, AUD-13, AUD-14 | — |
| 25 | [DM-01](../wi/TX-30-transform-honesty-sweep.md) int_track_evolution: drop the ambient fill… | SPEC | TX-30 | — |
| 26 | [DM-02](../wi/TX-30-transform-honesty-sweep.md) int_constructor_structural_pace: no-estimate… | SPEC | DM-01 | — |
| 27 | [DM-03](../wi/TX-30-transform-honesty-sweep.md) Carry constructor_pace_is_filled through… | SPEC | DM-02 | — |
| 28 | [TX-31](../wi/TX-31-restart-lap-labels.md) Restart laps tagged green while the safety… | SPEC | TX-30 | — |
| 38 | [DM-07](../wi/TX-30-transform-honesty-sweep.md) Inert SE fills (era rating, structural… | SPEC | DM-02 | — |

#### 2. Launch of the assistant (AI work) (7)

_Pages and cards for the new data, then the assistant core, worker, eval and drawer._

| # | Item | Stage | Waits on | Owner decision |
| ---: | :--- | :--- | :--- | :--- |
| 33 | [AP-09](../wi/AP-09-new-data-pages.md) App pages for the new measured marts… | SPEC | TX-23, TX-26, TX-27, TX-30, AUD-04 | — |
| 34 | [AP-10](../wi/AP-10-season-2026-results.md) 2026 season results and race recaps page… | SPEC | AP-09 | — |
| 36 | [AX-28](../wi/AX-28-new-data-cards.md) Card kinds and qv_* query views for the new… | SPEC | AP-09, TX-29, TX-30, TX-23, TX-26, TX-27, TX-28, TX-31 | — |
| 42 | [AX-10](../wi/AX-10.md) Assistant core v2: dispatcher for the 7… | MEASURED | TX-29, TX-30, TX-23, TX-26, TX-27, TX-28, TX-31 | — |
| 43 | [AX-12](../wi/AX-12.md) Worker v2: one ticket per question… | MEASURED | TX-29, TX-30, TX-23, TX-26, TX-27, TX-28, TX-31 | — |
| 44 | [AX-13](../wi/AX-13.md) Analyst eval v2: questions per class… | MEASURED | AX-10, TX-29, TX-30, TX-23, TX-26, TX-27, TX-28, TX-31 | — |
| 45 | [AX-14](../wi/AX-14.md) Chat drawer with render-time grounding and… | MEASURED | AX-10, AX-12, TX-29, TX-30, TX-23, TX-26, TX-27, TX-28, TX-31 | — |

#### 3. New data features (4)

_New measured sources into staging and marts._

| # | Item | Stage | Waits on | Owner decision |
| ---: | :--- | :--- | :--- | :--- |
| 30 | [TX-23](../wi/TX-23-quali-corner-skill.md) Qualifying telemetry into a separate… | SPEC | TX-30 | — |
| 31 | [TX-26](../wi/TX-26-race-control-detail.md) Race-control detail (blue flags… | SPEC | TX-30 | — |
| 32 | [TX-27](../wi/TX-27-jolpica-pit-crosscheck.md) Jolpica pit_stops as an independent… | MEASURED | TX-30 | — |
| 35 | [TX-28](../wi/TX-28-raw-channels.md) Raw pos_data and car_data (telemetry_full)… | SPEC | TX-30 | — |

#### 4. Launch (2)

_Freeze the snapshot, then the owner switches the assistant on._

| # | Item | Stage | Waits on | Owner decision |
| ---: | :--- | :--- | :--- | :--- |
| 46 | [AX-19](../wi/AX-19.md) Freeze: snapshot of manifest version, card… | SPEC | AX-13, AX-14 | — |
| 47 | [AX-20](../wi/AX-20.md) Launch run through the real drawer and… | SPEC | AX-19 | — |

#### 5. Held or after launch (16)

_Dirty air, ML, uncertainty and the ghost chain; all wait on launch or a ruling._

| # | Item | Stage | Waits on | Owner decision |
| ---: | :--- | :--- | :--- | :--- |
| 29 | [AUD-15](../wi/AUD-00-model-triage.md) Audit ML features and the degradation… | SPEC | AUD-11, AUD-03 | — |
| 37 | [DM-05](../wi/TX-30-transform-honesty-sweep.md) Ghost chain: interaction and deg-sensitivity… | SPEC | DM-03 | HD20 |
| 39 | [TX-09](../wi/TX-09.md) Refit the degradation-envelope isotonic file | BLOCKED | — | XM |
| 40 | [TX-32](../wi/TX-32-cliff-onset-two-part.md) Constructor cliff onset: split… | SPEC | TX-30, TX-29, DM-05 | HD29, HD30, HD31, HD32, HD33, HD34 |
| 41 | [AP-11](../wi/AP-11-quali-segment-flag.md) Qualifying segments flag in the app: say… | SPEC | TX-30 | — |
| 48 | [AX-24](../wi/AX-24-car-ahead-off-published.md) No published number depends on DriverAhead… | SPEC | AX-20 | — |
| 49 | [DM-04](../wi/TX-30-transform-honesty-sweep.md) Dirty air: rebuild air state on proximity… | SPEC | AX-20, AX-24, DM-03 | — |
| 50 | [AX-23](../wi/AX-23-dirty-air-off-surface.md) Take dirty-air cost off the product surface… | SPEC | AX-20 | — |
| 51 | [AX-26](../wi/AX-26-held-wording-and-tax-label.md) Held-card wording and the unvalidated label… | SPEC | AX-20 | — |
| 52 | [AX-15b](../wi/AX-15b.md) Make the dirty-air-dependent cards live once… | BLOCKED | TX-17, TX-18, AX-20 | XW |
| 53 | [AX-16](../wi/AX-16.md) Traffic-cost cards from the wake-calibration… | BLOCKED | AX-15b, AX-20 | XW |
| 54 | [DM-06](../wi/TX-30-transform-honesty-sweep.md) ML-only zeros: drift_s_per_lap, quali SE… | SPEC | AX-20, TX-29, AUD-15 | — |
| 55 | [ML-01](../wi/ML-01-retrain-2018-2024.md) Retrain models on 2018-2024 and score 2025… | SPEC | AX-20, TX-29 | — |
| 56 | [AX-17](../wi/AX-17.md) ML cards: prediction bands, in-envelope… | BLOCKED | ML-01 | XM |
| 57 | [AX-18](../wi/AX-18.md) Pit-call verdict cards with the measured… | BLOCKED | AX-17 | XM |
| 58 | [UNC-01](../wi/UNC-01-uncertainty-methodology.md) Uncertainty methodology for constructor… | SPEC | AX-20, AX-24 | — |

### Which model to run it on

Recorded per item in the log, not chosen at the keyboard, so the choice is reviewable and moves with the item rather than with whoever picks it up.

- **`fable-5.1`** — claude-fable-5-1. Novel statistical construction where a wrong derivation is expensive and hard to detect from the output - estimators, identification arguments, inference machinery. Reach for it when the failure mode is a plausible-looking number, not an error.
- **`opus-5`** — claude-opus-5. The default. Anything that makes a ruling, designs an aggregation, moves the feature contract, or turns a measurement into a claim.
- **`sonnet-5`** — claude-sonnet-5. The method is already written down and the judgment call is made - ingest, enumeration, a named refit, a declared schema note. Step back up to opus-5 the moment the leaf doc leaves a choice open.
- **`haiku-4-5`** — claude-haiku-4-5. Throughput work with a mechanical check on the output. Nothing in the tree currently qualifies: every live item either writes into the contract, rules on leakage, or produces a claim.

### Open decisions — these are yours, not tasks

- **XW** (blocks `AX-15b`, `AX-16`) — EXTERNAL: wake calibration reaches WC-06 (app output) with its labels.
- **XM** (blocks `AX-17`, `AX-18`, `TX-09`) — EXTERNAL: the ML redo lands, CD10 (promotion) is ruled, and the D9/D14 re-measures are recorded.
- **HD18** (blocks nothing) — Delete old data: PENDING the owner's confirmation of WHAT to delete
- **HD20** (blocks `TX-18`, `DM-05`) — Ghost-car 0 fills (TX-18): when a constructor has no pace cell (1,122 lap rows) or no degradation cell for a…
- **HD25** (blocks `TX-17`, `TX-18`, `TX-30`, `DM-02`, `AUD-11`, `AUD-12`) — For each zero-fill the transform writes (dirty-air tax, ghost pace and SE, lap-residual…
- **HD26** (blocks `AUD-05`, `AUD-12`) — Where the transform substitutes a fixed non-zero constant for a missing input, should the row get NULL with a…
- **HD27** (blocks `AUD-10`, `AUD-11`, `DM-02`) — (a) Three rating models pool within-cell variance as AVG(POWER(COALESCE(sd, 0), 2)), so a single-observation…
- **HD28** (blocks `DM-01`) — int_track_evolution clamps the rubber slope to <= 0 (about :80-90), so 36 of 166 races have rubber exactly 0…
- **HD29** (blocks `TX-32`) — Which per-stint cliff event should method A's survival model use? A: fct_stint_features.cliff_lap_in_stint…
- **HD30** (blocks `TX-32`) — A/B (timing in laps via survival, post-cliff cost as a rate) as the fix, and should the minimal x2.5 units…
- **HD31** (blocks `TX-32`) — For a constructor-compound-season cell below the minimum sample, the point is 0 (field-timed by prior)
- **HD32** (blocks `TX-32`) — cliff_onset_shift_laps is clipped to +/-3 laps; the published range is -0.68 to +1.12, so it never binds (max…
- **HD33** (blocks `TX-32`) — Admit an as-of version of method A (fitted only on races strictly before the predicted race, passes…
- **HD34** (blocks `TX-32`) — Method B's ghost term is (B_host - B_ego) * LEAST(laps_past_onset, H)

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
