# Assistant data access: review of the AI roadmap, a proposed architecture, and a draft AX build order

_Drafted 2026-11-07, read-only. Nothing in the repo was edited, staged or committed, and no `data/*.duckdb` was opened. This is a proposal. It is not a ruling and not a board entry. State still lives in `_roadmap/_ai-integration/status/build-log.json`._

**What I read:** `_roadmap/_ai-integration/README.md`; `status/BUILD-ORDER.md`; `status/build-log.json` (items, decisions, watch rules, last history entries, via `board.py`); every `wi/AI-*.md`; the live `wi/CO-*` items through their log notes (the terminal ones only through their `closed`/note fields); `_roadmap/_wip/AI_PLAN.md`; `_roadmap/_ml/ML-RESET-PLAN.md`; `_roadmap/_archive/_dirty-air/ARCHIVED.md`; the `_wake-calibration` README, board and `wi/WC-06-app-output.md`; `docs/platform/architecture-decisions.mdx`; `app/src/assistant/honesty/*`; `app/src/nav/assistantTools.ts`, `routes.ts`, `pageSummaries.*`, `assistant-docs/`; `worker/src/*`; `scripts/export_app_data.py`; `app/public/data/_manifest.json`; `app/src/data/duckdb/*`, `app/src/data/manifest.ts`, `app/src/data/hooks/*`, `app/src/state/FilterContext.tsx`; each feature's `queries.ts`/`transform.ts` table references; and the column lists in `transform/models/**/schema.yml`.

---

## 0. Findings that change the plan

1. **The old board points at an archived method.** The `_ai-integration` pointer is on **CO-32** (micro-sector dirty air), which follows `_roadmap/_dirty-air`. That folder was archived on 2026-10-27 (`_roadmap/_archive/_dirty-air/ARCHIVED.md`: "no number from it is used in the product, as a fallback or otherwise"). Traffic cost now lives in `_roadmap/_wake-calibration`, currently at WC-10e (BUILDING). So CO-32 and watch W11 are superseded, and the board's "next" is stale.
2. **AD2, AD3, AD4 and AD5 exist only in the build log.** `docs/platform/architecture-decisions.mdx` holds ADR-001 to ADR-010 and has no entry for the assistant.
3. **The published app data predates the v16 seal.** `app/public/data/_manifest.json` has `generatedAt: 2026-10-16`, and it was last committed on 2026-10-17. CO-17 (the trusted rebuild) landed on 2026-10-24 and CO-33 (the v16 seal) on 2026-10-26. A card built today from the published files would carry pre-v16 numbers. I did not check whether the CDN copy is newer.
4. **None of the rating marts is published.** `mart_race_driver_summary`, `mart_driver_season_summary`, `mart_metric_benchmark` and `fct_driver_isolation_{race,stint}` are all missing from the 39 tables in the manifest. AI-01 had already noted this for the first three.
5. **The Worker cannot run a multi-call question as built** (`worker/src/handler.ts`):
   - Every model round is one HTTP request. Each request spends a single-use Turnstile token and takes one per-visitor slot. A question with 4 tool calls is 5 rounds: round 2 fails Turnstile, and with `VISITOR_DAILY_LIMIT=10` a visitor gets about 2 questions a day.
   - `DAILY_NEURON_CAP` defaults to 90,909 neurons (about 1 USD of paid usage). Under AD4-B (free allowance only) the cap should be 10,000 or less.
   - `MAX_OUTPUT_TOKENS = 800`, against the 4,000 output slot in AD2's budget. gpt-oss reasoning tokens count as output.
   - `TOOLS = []`, and the system prompt is a placeholder.
6. **AD2's budget fits the window but not the free allowance.** The whole prompt is re-sent on every round. With AD2's slots, a 4-tool question is about 51k input tokens, or about 980 neurons. With 10,000 neurons a day, that is about 10 such answers a day across all visitors (worked in §2.6). The prototype's figure of 460 neurons per answer was measured on a smaller loop.
7. **Global filters are integers, but the data keys are strings.**
   - `FilterContext` and `navigate()` accept only integer `season/race/driver/constructor`.
   - Driver ids are three-letter codes (`dim_drivers.sql`: "FastF1 three-letter code"), and race ids look like `2024_8`.
   - 15 feature folders read their own string params instead (`race`, `race_id`, `circuit`, `compound`, `era`, `mode`, `min`).
   - So a card's page link cannot select a race or driver today.
8. **There is no display-name dimension.** `dim_drivers` has `driver_id, driver_number, debut_year, career_races_in_dataset`, so a fan's "Checo" or "Alfa Romeo" cannot be resolved. `app/src/data/hooks/useDrivers.ts` queries `last_name`, which does not exist (the hook appears unused).
9. **The browser query paths are not bounded.**
   - `runLabQuery` (`queryLab.ts`) calls `result.toArray()` on the whole result before capping at 5,000 rows.
   - `registerPartitionedParquet` (`register.ts`) registers every season as one `UNION ALL` view.
   - A builder on top of these must put `LIMIT` and aggregation into the SQL and register only the partitions it needs, as the feature queries already do (`fct_lap_residuals_${season}` aliases).
   - `query()` in `client.ts` already supports prepared parameters, and `AsyncDuckDBConnection.cancelSent()` exists for a timeout.
10. **Wake-calibration may move much more than the two dirty-air pages.** `WC-06` says that whether it "replaces or sits beside the existing 0.331 × share tax is an owner call at this gate". `dirty_air_tax_s` is inside `total_explained_s` (`fct_lap_residuals`, `race-lost/queries.ts`). If WC replaces the tax, the driver-skill residual moves, and so do every rating, ghost-car and constructor number built on it. This one ruling decides how much of the assistant must wait.
11. **The ML redo branch is not visible and has a naming conflict.** `ML-RESET-PLAN.md` says "branch ml-fresh-start", but `git branch -a` shows only `main` and dependabot branches. The plan also calls the retrain "v16", while D11 ruled v16 = transform label version and v17 = ML model name. Cards carry both, so the clash must be settled before any ML card exists.
12. **Already built, but still marked BLOCKED:**
    - AI-10 is MEASURED: route list, 44 page summaries (30,423 tokens in total, largest 795), tests and CI, in commit b6d8de1.
    - AI-06 is MEASURED: Worker, Durable Object ledger, bundle scanner; 16 of 16 tests pass.
    - AI-02 and AI-14 are LANDED: `policy.json` has 16 rules and 3 recorded contradictions, and a checker.

---

## 1. Inventory of existing items

Verdicts: **keep** (as is), **rewrite** (into the AX item named), **supersede** (another plan owns it), **drop** (out of assistant scope).

"Blocked" means it truly cannot proceed: it needs numbers or artefacts that do not exist yet. "Sequenced" means it is parked by PK1 or waits on earlier work, but nothing technical stops it.

### AI items

| Item | Log stage | Verdict | Reason | Really blocked or sequenced |
| :-- | :-- | :-- | :-- | :-- |
| AI-01 grounding contract | BLOCKED (PK1) | **rewrite → AX-01, AX-04, AX-07, AX-15, AX-17** | The card idea stands. Three things change: cards are built from the app's own feature code over **published** files, so the assistant can only say what a page can show; cards carry a `label` (aligned with WC: measured / modelled / unavailable, plus computed / experimental) and both `label_version` and `model_version`; and cards are split into classes T / T\* / WC / ML (§2.3) so the transform-only part can ship first. | Transform cards (T): sequenced (PK1 only). ML cards: blocked (ML redo). T\* cards: blocked on HD2. |
| AI-02 honesty policy | LANDED | **keep**, extended by AX-09 | Rules are data, they cite their sources, and the checker is tested. It needs rules for `computed_not_card` wording, held cards, the exact WC modelled-value disclaimer, and "unavailable is not zero". | n/a |
| AI-03 data freeze | BLOCKED | **rewrite → AX-19** | The snapshot becomes manifest version + card checksums + label version + model version, or an explicit "no ML cards" freeze if HD5 allows a transform-only launch. CD13 tied the freeze to CD10, which is deferred with the ML branch. | Blocked (CD10 / ML redo), unless HD5 = A. |
| AI-04 assistant core | BLOCKED | **rewrite → AX-10** | Same seven tools (AD2). Changes: a revised budget (§2.6), page cards pre-loaded so typical answers take 0 to 2 calls, a repair pass driven by the checker, budget enforcement per slot. Must also run AI-10's open 5-page check. | Sequenced. Can run on T cards and stubs. |
| AI-05 prediction tool | CLOSED | **drop** (stays closed) | Precomputed bands cover real stints; hypotheticals link the simulator. The ML redo may change the inputs; reopen only if AX-13 shows unserved what-if demand. | n/a |
| AI-06 Worker proxy | BLOCKED (MEASURED code) | **keep the code; rewrite the remainder → AX-12** | Needs: a per-question ticket, the cap at or under the free allowance, tools and prompt generated from the catalogue, a catalogue-version check, the output cap set from measurement, Turnstile hosts in the CSP. Preview deploy is the owner's. | Sequenced (owner Cloudflare login). |
| AI-07 analyst eval | BLOCKED | **rewrite → AX-13** | Keep the bar. Add one question group per card class, so that held classes (ML, traffic) must be refused or hedged until they land. Record neurons per answer, which turns into answers per day. | Sequenced. |
| AI-08 chat drawer | BLOCKED | **keep, small rewrite → AX-14** | Add a render-time grounding check (every number maps to a card id or query-result id from this session) and label rendering (modelled hatch plus the WC disclaimer, unavailable shown as "—"). | Sequenced. |
| AI-09 query builder | BLOCKED | **rewrite → AX-05, AX-06** | The catalogue exposes **observed measures only**; modelled columns go only through cards (a strict reading of AD3). It runs on narrow exported `qv_*` views, binds prepared parameters, registers only the partitions it needs, and cancels on timeout. Its CO-16 dependency is met (LANDED). | Sequenced. |
| AI-10 navigation and explainer | BLOCKED (MEASURED) | **keep**, extended by AX-03 | Route params must carry the string keys pages actually read (finding 7). Its definition of done closes inside AX-10. | Sequenced. |
| AI-11 charts and compare | BLOCKED | **keep → AX-11** (renumbered) | Spec unchanged; `compare_lap_times` sits on `qv_laps`. The prototype `_misc/_chat/f1-chat` was not checked. | Sequenced. |
| AI-12 launch run | BLOCKED | **keep → AX-20** (renumbered) | Same method, run on the AX-19 snapshot. | Blocked on AX-19. |
| AI-13 CI real-data job | SPEC | **supersede**: move to the transform/fixes board | CD17-A ruled a self-hosted real-data job. It is a transform-CI concern that moves no number the assistant quotes, and it needs W18 (pipeline off). | n/a for the assistant |
| AI-14 chance EXCLUDE | LANDED | **keep** | `CHANCE_LINE_QUOTABLE` is active (AD5). | n/a |

### CO items

| Item(s) | Log stage | Verdict | Reason | Really blocked or sequenced |
| :-- | :-- | :-- | :-- | :-- |
| CO-01, 02, 04, 05, 06, 07, 09, 15, 16, 17, 21, 22, 24, 26, 27, 28, 29, 30, 31, 33 | LANDED | **keep as record** | Terminal. Their effects are inputs to this design: CO-01 mart semantics, CO-16 sector identity (satisfies AI-09's dependency), CO-22 teammate-only telemetry deltas, CO-29 constructor lineage (needed by `list_values`), CO-33 v16 seal. | n/a |
| CO-03, 12, 13, 23, 25 | CLOSED | **keep as record** | Terminal. | n/a |
| CO-14 stint-life clean test, CO-18 retrain, CO-19 mixed-version probe | BLOCKED (PK1) | **supersede** by `_roadmap/_ml/ML-RESET-PLAN.md` steps 5 to 10 | Same work, now planned on the ML branch. Re-triage there, then delete them from this board. | Blocked (ML redo). |
| CO-08, CO-10, CO-20 chance line | BLOCKED (PK1) | **drop from the assistant board**; move to the ML redo | AD5 EXCLUDE means no card is ever built from `flag_chance_lookup.json`, so they gate nothing here (CD11 already said so). | Blocked (ML redo), but irrelevant to the assistant. |
| CO-11 chance relabel | LANDED | **keep as record** | n/a | n/a |
| CO-32 micro-sector dirty air | SPEC (board pointer) | **supersede** by `_wake-calibration` | The method is archived (finding 1). Close it and W11 as superseded, and move the pointer. | n/a |

Old decisions that still bind: AD1 to AD5, CD2 (2018 in-sample labelling), CD11, D7, and D11 naming. CD10 stays deferred with the ML branch. W1 (ship-blocker), W2, W7 (D9/D14 re-measures) and W14 carry over; the AX watch list below maps them.

---

## 2. Proposed data-access architecture

### 2.1 Principles

| # | Principle | Consequence |
| :-- | :-- | :-- |
| P1 | **The assistant sees only what the app publishes.** Cards and query views are built from the files in `app/public/data/` (the CDN set), never from the warehouse directly. | If the assistant can quote a number, a page can show it, and AX-19 checksums exactly what users get. The rating marts must be exported first. |
| P2 | **One code path per number.** A card that restates a page number is produced by that page's own `queries.ts` + `transform.ts`, run headless. | A card cannot drift from its page. A parity test is the acceptance. |
| P3 | **Modelled numbers are cards; observed numbers may be queried.** | `query_data` never exposes residuals, components, ratings, predictions, hazards or dirty-air prices (strict AD3). |
| P4 | **The model never writes SQL, chart code or URLs.** It fills fixed JSON shapes; the browser validates against the catalogue and builds the output. | A 0-SQL-from-model check runs on the code path (as in AI-09). |
| P5 | **Every number carries its label, n, interval kind and versions.** "Unavailable" is a value with a reason, never 0 (WC rule). | The checker and the drawer both read these fields. |
| P6 | **The browser holds the rows; the model gets compact projections.** | Token fit (§2.6). Full cards stay in a session store for links and hover. |
| P7 | **The catalogue is versioned with the data.** Tools in the Worker, the catalogue in the app and the cards on the CDN share one `catalogue_version`. | An old tab cannot mix new tool definitions with old data. |

### 2.2 Fact-card schema (v1)

Stored form: one row per card in `assistant_cards`. Nested fields are stored as columns or JSON strings. JSON Schema at `app/src/assistant/cards/card.schema.json` (new), with generated TS and Python types. This replaces the loose `FactCard` interface in `checker.ts`.

```jsonc
{
  "id": "race_lost.component:2024_8:LEC:compound",   // deterministic: kind ':' scope key ':' variant
  "kind": "race_lost.component",                      // registry key (§2.4)
  "metric": "compound_component_s_total",
  "label": "modelled",          // measured | modelled | computed | experimental | unavailable
  "value": -3.412,              // null only when label = unavailable
  "unit": "s",
  "display": "-3.4 s",          // pre-formatted at the page's display precision
  "unavailable_reason": null,   // required when label = unavailable (e.g. "no clean lap in stint")
  "n": { "count": 51, "unit": "laps" },               // required; cards without n are refused
  "interval": {                                       // null allowed ONLY for label measured|computed
    "low": -3.9, "high": -2.9, "level": 0.95,
    "kind": "lap_noise_band",    // ci_bayes | ci_bootstrap | lap_noise_band | pred_band_p10_p90 | se_1 | none
    "source_columns": ["ci_low","ci_high"]            // kind is copied from the registry, never inferred
  },
  "scope": { "season": 2024, "race_id": "2024_8", "driver_id": "LEC",
             "constructor_id": null, "circuit_id": "monaco", "compound": null,
             "stint_id": null, "lap": null },
  "source": { "mart": "fct_lap_residuals", "columns": ["compound_component_s"],
              "feature": "race-lost", "query": "race-lost.driver", "transform": "race-lost/transform.ts#transform" },
  "versions": { "data_version": "30f91247d7cb651e",   // manifest.version (ADR-010 content hash)
                "label_version": "v16",               // transform label version (D11)
                "model_version": null,                // ML model version where it applies (HD8)
                "card_schema": "1", "registry": "<sha256 of registry>" },
  "page": { "route": "/lap-decomposition/race-lost", "params": { "race": "2024_8", "driver": "LEC" },
            "docs_slug": "race-lost" },
  "caveats": ["THIN_SAMPLE"],     // AI-02 policy codes, computed by the builder from registry rules
  "sample": "na",                 // in_sample | holdout | na (policy trigger field)
  "grade": null,                  // validation grade where one exists (VALIDATION_GRADE_BELOW_PASS)
  "status": "active"              // active | held | withdrawn; held cards are published with held_reason
}
```

**Model projection.** This is what `get_fact_cards` returns into context, about 45 to 60 tokens per card:

```json
{"id":"race_lost.component:2024_8:LEC:compound","m":"compound s total","v":-3.41,"u":"s","lbl":"modelled","n":"51 laps","iv":[-3.9,-2.9,"lap_noise_band"],"cav":["THIN_SAMPLE"],"pg":"race-lost"}
```

**Rules**

- A source row with no `n` becomes no card and goes on the ungrounded list (AI-01).
- `label ∈ {modelled, experimental}` requires an interval, or the card is refused.
- A `held` card is published so the assistant can say why a number is not available yet. A held card has no `value`.
- `interval.kind` comes only from the registry entry, so a lap-noise band can never be relabelled as a CI (AI-01 acceptance).
- The chance line has no card kind (AD5). The registry rejects a kind whose source is `flag_chance_lookup.json`.

### 2.3 Card classes: what is quotable when

| Class | Meaning | Available when |
| :-- | :-- | :-- |
| **T** | Transform output not downstream of `dirty_air_tax_s` or any ML artefact | Now, on a v16 re-export (HD12) |
| **T\*** | Transform output downstream of the dirty-air tax (residuals, ratings, ghost car, constructor isolation) | Now if HD2 = "WC sits beside the tax" (only the dirty-air bar is held); after WC-06 plus a relabel if HD2 = "WC replaces it" |
| **WC** | Traffic cost (dirty air, held up, racecraft, tow) | After WC-05/WC-06, with measured / modelled / unavailable labels |
| **ML** | Anything from `mart_degradation_predictions`, `app/public/models/*`, model metrics, blind test | After the ML redo lands and CD10 is ruled |
| **X** | Excluded: chance to make the flag | Never (AD5) |

The class is decided by lineage, not by hand. AX-07 step 1 runs `dbt ls --select +<model>` (read-only, on a scratch copy if needed) for each source and marks a model T\* if `int_dirty_air_tax_component` or `theta_air` is upstream.

The column below is my provisional reading from column names. **Not verified.**

### 2.4 Card kinds: how feature outputs become cards

Each feature folder gets a `cards.ts`. It exports `cardKinds: CardKindSpec[]`, and each spec has:

- `enumerate(index)`: which parameter sets to build, for example every (season, race, driver) in the published index.
- `build(params, q)`: calls the feature's **own** registered query and `transform()`, then maps the result fields to card fields.
- `pageParams(params)`: the deep link.
- `interval` and `n` mapping.
- `caveatRules`.

The registry `app/src/assistant/cards/registry.ts` imports all of them. Kinds backed only by a mart (no page yet, such as `mart_race_driver_summary.rating_s`) use a `sqlKind` spec in the same registry, with SQL over published files.

**Headless runner** (`app/scripts/build-cards.ts`): Node plus `@duckdb/node-api`, or duckdb-wasm in Node, behind an adapter that implements `rawQuery` and `registerParquet` over local `app/public/data` paths. The adapter also gives the eval (AX-13) and parity tests a real engine.

| Feature (route) | Card kinds (v1) | Source | Interval kind | Class |
| :-- | :-- | :-- | :-- | :-- |
| race-control | caution laps per race; SC/VSC onsets; prior-season hazard (shrunk) | `race_caution_timeline`, `int_sc_hazard_history` | none (counts); shrunk rate: none, so label computed with n = prior racing laps; 2018 → unavailable | T |
| field-pace-curve | field pace at lap L; low-sample flag | `int_field_pace_curve` | none, computed (n from window) | T (check lineage) |
| quali-vs-race-skill | quali skill residual, quali-vs-race delta | `int_qualifying_decomposed` | se if present, else refuse | T (check) |
| corner-phase-skill | braking / mid / exit skill (driver-season) | `mart_corner_skill_driver` | se_1 (`*_se_s`), n = cells | T (check) |
| driver-workload | push-load summaries | `fct_cliff_prediction_features` | none, computed | T (check) |
| tyre-cliff-survival (profile, not model chips) | cliff onset and severity per circuit × compound × season | `int_compound_cliff_predicted` (seed fit) | as published; CD2 → 2018 caveat IN_SAMPLE | T |
| tyre-recovery-forecast | recovery probability | `int_tyre_surface_vs_bulk_decoupling` | none → label computed or refuse; ruling in AX-07 | T (check) |
| data-quality-audit | anomaly-flag counts | `int_lap_anomaly_flags` | none, measured counts | T |
| (no page) results | finish, positions gained, DNF, laps completed | `mart_race_driver_summary` (**export first**), `fct_ghost_race_finish` actuals | none, measured | T |
| race-lost, lap-waterfall | component totals per driver-race; closure gap | `fct_lap_residuals` (+ `int_lap_residual_decomposed` identity) | lap_noise_band where the mart has one; else refuse | T\* (dirty-air bar: WC) |
| sector-decomposition | sector components | `int_sector_residual_decomposed` | as above | T\* (sector dirty air: WC) |
| ghost-race-standings, counterfactual-championship, hidden-performance | predicted finish, p_beats_next | `fct_ghost_race_finish`, `int_driver_race_skill_loro` | se_1 (`finish_pos_se`) | T\* |
| era-ratings-timeline, era-translator | era-adjusted rating | `int_era_normalized_driver_rating` | ci (`era_adjusted_rating_ci_*`) | T\* |
| (no page) rating marts | race and season rating, teammate gap | `mart_race_driver_summary`, `mart_driver_season_summary`, `mart_metric_benchmark` (**export first**) | lap_noise_band (`ci_low/high`, per its header) | T\* |
| (no page) driver isolation | pure / relative pace with trust label | `fct_driver_isolation_race` / `_stint` (**export first**) | se_1, plus `grade` from trust label (VALIDATION_GRADE_BELOW_PASS) | T\* |
| driver-consistency, wet-race-specialist | residual sd, wet delta | `fct_driver_skill_features` | none → refuse, or bootstrap at build | T\* |
| driver-circuit-affinity | shrunk affinity | `int_driver_circuit_affinity` | ci (`shrunk_affinity_ci_*`) | T\* |
| synthetic-teammate | gap to synthetic teammate | `int_synthetic_teammate` | check | T\* |
| constructor-structural-pace, party-mode, constructor-circuit-interaction, team-averages | structural pace, interaction, mean components | `int_constructor_structural_pace(_qualifying)`, `int_circuit_x_constructor_interaction`, `fct_lap_residuals` | ci (`constructor_structural_pace_ci_*`) | T\* (CO-30 prices dirty air in the isolation panel) |
| track-evolution | evolution slope | `int_track_evolution` | check | T\* (check) |
| dirty-air-cost, dirty-air-lap-map | traffic cost totals, modelled share | WC-06 marts | per WC labels | **WC** |
| pit-strategy | optimal lap, verdict, opportunity cost | `int_pit_strategy_value` | none → `held` until the reproduction rate is measured (PIT_CALL_REPRODUCTION_RATE, D9/W7) | T but **held** |
| stint-degradation-timeline, tyre-cliff-survival model chips, blind-test-scoreboard, model-metrics | p10/p50/p90, cliff probabilities, in-envelope, metrics | `mart_degradation_predictions`, `app/public/models/*` | pred_band_p10_p90; metric CIs | **ML** |
| degradation-simulator | none: link only | n/a | n/a | link (AI-05) |
| chance line | none | n/a | n/a | **X** |

**Page context.** Each `cards.ts` also exports `onScreen(params) → card ids`. When the drawer opens, it pre-loads those cards (6 at most, about 360 tokens) into the page-context slot. "Why did Leclerc lose time here?" asked on the Race Lost page then needs no tool call.

### 2.5 Query catalogue, the bounded query builder, and list_values

The catalogue sits in `app/src/assistant/catalogue/catalogue.ts`, emitted at build time as `assistant/catalogue.json`. Its views are **narrow exported parquet `qv_*` tables**, written by the export under `app/public/data/assistant/`. The builder therefore never joins, and every column has a contract test. Lap-grain views are partitioned by `race_year`, like their sources.

| View | Grain | Built from (published) | Dimensions (filter / group_by) | Measures (aggregate) | Required filters and limits |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `qv_laps` | driver × lap (green racing laps only, stated in the view note) | `fct_lap_residuals` (observed columns only) + `fct_cliff_prediction_features` (`lap_in_stint`, `age_in_stint`, `stint_id`) | season, race_id, driver_id, constructor_id, compound, lap_number (range), lap_in_stint (range), is_major_outlier_lap | lap_time_s (avg, median, min, max), laps (count) | `season` required, at most 2 seasons; `race_id` required to group by lap_number; outliers excluded unless asked |
| `qv_stints` | stint | `fct_stint_features` | season, race_id, driver_id, compound, stint_end_cause, pit_decision_class, is_censored_stint, reached_flag, short_stint_flag | stint_length_laps, starting_tyre_age_laps, mean_clean_pace_s (avg, median, min, max), stints (count) | `season` required; censored stints flagged in `notes`. Excluded: `tyre_management_score`, `cliff_lap_in_stint`, `cumulative_dirty_air_tax_s` |
| `qv_pit_stops` | pit stop | `int_pit_strategy_value` (`actual_pit_lap`, `pit_lane_loss_s`, `pit_loss_imputed_flag`, `pit_loss_source`) + `fct_stint_features` keys | season, race_id, driver_id, compound (before and after), pit_loss_imputed_flag | pit_lane_loss_s (avg, median, min, max, only where not imputed), stops (count), actual_pit_lap (min, max) | `season` required. Verdict and optimum are excluded (cards, held) |
| `qv_driver_race` | driver × race | `mart_race_driver_summary` (**export**; observed columns), `fct_ghost_race_finish` actuals (`is_self_scenario`) | season, race_id, circuit_id, driver_id, constructor_id, has_dnf, actual_dnf_cause | positions_gained, laps_completed, actual_finish_position, avg_lap_time_s, n_clean_laps (avg, median, min, max, sum on counts), races (count) | `rating_s`, `teammate_gap_s` and `mean_*_component_s` excluded (cards) |
| `qv_race_laps` | race × lap | `race_caution_timeline` | season, race_id, circuit_slug, caution_status, lap_number (range) | laps (count), race_laps (max) | `season` required |
| `qv_circuit_history` | circuit × season | `int_sc_hazard_history` (counts only) | circuit_slug, season | season_races_n, prior_races_n, prior_racing_laps, prior_sc_onsets, prior_vsc_onsets (sum, max) | Shrunk hazards excluded (cards) |
| `qv_teammate_corners` | teammate pair × corner × lap | `fct_telemetry_deltas` (teammates only, D7; deltas NULL when a side is missing, CO-22) | season, race_id, driver pair, corner | per-corner delta columns (avg, median), corners (count). Column names **not verified**. | `season` and `race_id` required |
| `qv_circuits`, `qv_compounds` | reference | `dim_circuits`, `dim_compounds_season` | circuit_id; season, compound | lap_length_km, corner_count; compound mapping | none |

Deliberately **not** in the catalogue: `int_corner_metrics` and `int_lap_air_state` (exposure semantics change under WC), telemetry raw (28.6M rows), raw flag tables, and every modelled column (P3).

**Request shape** (the only thing the model sends):

```jsonc
{ "view": "qv_laps",
  "filters": [{"col":"season","op":"eq","val":2024},{"col":"race_id","op":"eq","val":"2024_8"},
              {"col":"driver_id","op":"in","val":["LEC","SAI"]}],   // ops: eq ne lt lte gt gte in between; ≤6 filters; in ≤20 values
  "group_by": ["driver_id"],            // ≤2, dimension columns only
  "aggregate": {"fn":"median","col":"lap_time_s"},   // count|avg|median|min|max|sum (sum only on count-like measures)
  "order": "value_desc",                // fixed enum: value_asc|value_desc|group_asc
  "limit": 10 }                          // ≤25
```

**Compilation and safety**

- Identifiers come only from catalogue entries, matched exactly; strings from the model are never interpolated. Values are bound with `conn.prepare` (`client.ts` already does this).
- The builder appends `COUNT(*) AS n` and `LIMIT limit+1`, so `rows_dropped` can be computed without materialising the rest.
- It registers only the needed `race_year` partitions, under per-season aliases (finding 9).
- It runs on a dedicated connection with a 3 s timeout (`Promise.race` plus `cancelSent()`), separate from the Query Lab's connection.

**Result shape** (AI-09 kept): `{view, filters_applied, grain, rows:[{…, n}], row_count, rows_shown≤25, rows_dropped, label:"computed_not_card", notes:[…], result_id}`.

- Values are rounded to 3 decimals.
- A row with `n < 5` carries `thin:true` (policy THIN_SAMPLE wording).
- No data returns `{status:"no_data", reason}`.
- Validation errors list the allowed columns and operators for that view. Together with `list_values(domain:"columns")`, this replaces a separate describe tool, so AD2's seven tools stay seven.

**`list_values`** (exact-code lookup, backed by a new exported `assistant_entities` table of a few hundred rows):

- Input: `{domain, query?, season?, limit≤20}`.
- Domains: `driver`, `constructor` (with `constructor_lineage_id`, CO-29), `race` (season, round, race_id, circuit, GP name), `circuit`, `season`, `compound` (per season), `caution_status`, `stint_end_cause`, `card_kind`, `page`, `columns` (with `view`).
- Output: `[{code, display, aliases_matched, seasons}]`, at most about 400 tokens.
- Fuzzy matching runs on an alias list ("Checo" → PER; "Alfa Romeo" / "Sauber" / "Kick Sauber" → lineage `sauber`).
- Display names need a source (HD7). `data/bronze/reference/jolpica/driver_standings/` exists; I did not check whether it carries given and family names.

`compare_lap_times(a, b, race)` is a fixed `qv_laps` request with 2 series of at most 80 points, returned to the chart store (AI-11). The model gets back only `{chart_id, n_a, n_b, laps_missing}`.

### 2.6 Token budget (gpt-oss-20b, 20,480 window, AD2)

| Slot | AD2 | Proposed | How |
| :-- | ---: | ---: | :-- |
| Instructions + rule digest | 1,500 | 1,200 | Rule codes plus one-line wording. The full required wording is enforced after drafting by the checker, with one repair turn |
| Tool schemas (7) | 1,900 | 1,400 | View names and card kinds as enums; no column lists |
| Query catalogue | 1,200 | 600 | View name, grain and one line each; columns on demand via errors or `list_values(columns)` |
| Page context | 600 | 600 | Route, params, up to 6 on-screen card projections |
| History | 2,000 | 2,000 | Last two turns; cards cited by id, not re-sent |
| Tool results | 6,000 (4 × 1,500) | 4,800 (4 × 1,200) | Cards ≤10 × 55; query ≤25 rows; truncated to the slot with `rows_dropped` |
| Output (incl. low reasoning) | 4,000 | 2,500 | Measure in AX-13. The Worker's 800 is likely too low |
| **Peak context** | 17,200 | 13,100 | Under AI-07's 18,000 bar either way |

**Neurons per question**, at 18,182 neurons per M input tokens and 27,273 per M output (AI-06 step-1 record). Input is re-sent each round, and output is assumed at about 300 tokens per round.

| Tool calls | AD2 slots | Proposed slots |
| :-- | :-- | :-- |
| 1 | 15.9k tokens in, about 310 neurons | 12.9k in, about 255 neurons |
| 2 | 26.1k in, about 500 neurons | 21.3k in, about 410 neurons |
| 4 | 51k in, about 980 neurons | 42k in, about 800 neurons |

Against 10,000 neurons a day (AD4-B), that is about 12 to 40 answers a day in total. This is the binding constraint, not the window. The design therefore aims for 0 to 2 calls per typical answer:

- page cards are pre-loaded;
- `get_fact_cards` takes up to 3 scopes × 5 kinds in one call;
- `list_values` results are cached in the session and repeated codes are not looked up again.

AX-13 must record the real figures. Workers AI prefix caching would change this arithmetic; **not verified** whether it exists for this model.

### 2.7 Publishing with the app data (manifest and versioning)

**Order inside `make app-data`** (proposal):

1. `export_app_data.py` writes tables, plus the newly exported rating and isolation marts, `assistant_entities` and the `qv_*` views.
2. `node app/scripts/build-cards.ts` reads `app/public/data`, runs the registry, and writes `assistant/cards/{season}.parquet` plus `assistant/cards/_global.parquet` (career and season cards), `assistant/index.json` (counts per kind and season, held and refused lists, the ungrounded list) and `assistant/catalogue.json`.
3. `export_app_data.py --finalize` computes the ADR-010 content hash over everything, so cards change the `version`, and writes the manifest.

**Manifest addition:**

```jsonc
"assistant": { "card_schema": "1", "catalogue_version": "<sha256(catalogue.json)>",
  "registry": "<sha256>", "label_version": "v16", "model_version": null | "<ML name>",
  "cards": [{ "season": 2024, "path": "/data/assistant/cards/2024.parquet", "rows": 6210, "sha256": "…" }],
  "classes_live": ["T"], "classes_held": ["T*","WC","ML"] }
```

**Size:** about 170 races × 20 drivers × about 8 kinds, plus stint and season cards, comes to roughly 50k rows, or about 1 MB per season partition. This is an estimate, not measured, and the 5 MB gate applies.

**The Worker:** `worker/scripts/gen-tools.mjs` generates `worker/src/generated/tools.ts` (SYSTEM_PROMPT, TOOLS, CATALOGUE_VERSION) from `catalogue.json`. The browser sends `X-Catalogue-Version`. On a mismatch the Worker returns 409 `{error:"app_updated"}`, and the drawer asks for a reload.

**The freeze (AX-19)** is `{manifest.version, assistant.cards[].sha256, catalogue_version, label_version, model_version}`. `app-data-check` (the existing `--check`) fails if cards change without being regenerated.

### 2.8 Safety

**In the browser**

- No SQL from the model, and no Query Lab path (`runLabQuery` is not used by the builder).
- Prepared parameters; catalogue identifiers only; read-only views; a dedicated connection; partition-scoped registration; a 3 s cancel; 25 rows at most.
- Chart rows and full cards stay out of context.
- At render time the drawer checks grounding: every number in the answer must match a card or a `result_id` returned in this session. Unmatched numbers are struck through and the AI-02 note is shown.
- The checker runs before display.

**In the Worker** (on top of the built handler):

- **Question ticket.** The first round needs Turnstile. The Worker then issues an HMAC ticket `{visitor, q_id, rounds_left:5, exp:+120 s}`. Later rounds present the ticket instead of a new Turnstile token. The per-visitor limit counts **questions** (ticket issues), not requests.
- `DAILY_NEURON_CAP` at or under 10,000 by default while AD4-B stands (finding 5).
- Model, prompt, tools and output cap stay fixed server-side; browser-sent tools are ignored (already built).
- Message body and count limits (already built). Add a maximum `tool` message size equal to the tool-result slot, about 5,000 characters.
- No data ever passes through the Worker apart from the tool results the browser chooses to send. The Worker never runs a query (already built).
- Redaction and the bundle key scan (already built; the CI step is still owed per the AI-06 note).
- CSP: the Worker host, plus `https://challenges.cloudflare.com` in script-src, frame-src and connect-src (HD11).

**What the model could still do:** draft a wrong sentence around a correct card. This is caught by the checker and by AX-13's human read, not prevented.

---

## 3. DRAFT NEW BUILD ORDER: assistant data access (AX)

_Draft for the owner. Not in any log. If adopted, it becomes a `_roadmap/_assistant/` (or `_ai-integration` v2) `build-log.json` with the same `board.py` mechanism. This text then turns into JSON and the generated block. Do not hand-maintain it._

**Rules**

1. The pointer is the one item to run next. Run `--check` after every edit to the log.
2. A `BLOCKED` item waits on an open ruling (HD-\*) or on another track (WC, ML). Put the ruling to the owner, with the options translated, before spawning work.
3. **Class rule.** An item that produces cards may only publish classes listed in `classes_live`. A class moves to live only when its gate item lands (T: AX-07; T\*: AX-15; WC: AX-16; ML: AX-17).
4. **Published-only rule.** Cards and query views are built from `app/public/data`, never from `data/dev.duckdb` directly. Parallel dbt work uses its own folder, with the copy named `dev.duckdb` (owner's memory rule).
5. **No model-written SQL, chart code or URLs**, ever. A change that adds a free-text path to the browser engine is out of scope.
6. Nothing is committed, published to the CDN or deployed without a yes from the owner. Agents never run `git add`, `commit` or `push`.
7. PK1 still stands: no AX item starts until HD1 is ruled.
8. No DA-03 (archived) number and no chance-line number gets a card, as a fallback or otherwise.

**Items**

| # | Item | Phase | Task | Depends on | Size | Model | Acceptance test | Waiting on |
| ---: | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| 1 | AX-00 | 0 triage | Re-triage record for the old board: close CO-32 and W11 as superseded by WC; move AI-13 to the transform board; move CO-08/10/14/18/19/20 to the ML-redo plan; carry W1/W2/W7/W14 over | none | 0.25d | `sonnet-5` | Old `board.py --check` passes; every old live item has a verdict and a link; the pointer is off CO-32 | **HD9** |
| 2 | AX-01 | 1 foundations | Card schema v1 (JSON Schema, TS and Python types, two projections, label vocabulary, versions block); `checker.ts` switches to the generated type | none | 1d | `opus-5` | Schema validates 10 fixture cards and rejects 10 bad ones (no n, modelled without interval, unavailable with value, relabelled interval kind); `vitest src/assistant/honesty` passes unchanged | HD1 |
| 3 | AX-02 | 1 | `assistant_entities` export + `list_values` (domains incl. `columns`), alias list | AX-01 | 1-2d | `sonnet-5` (`opus-5` if no name source) | 100% of `driver_id`, `constructor_id`, `race_id` in the published facts resolve; 30 alias fixtures resolve; each call ≤20 rows and ≤400 tokens | HD1, **HD7** |
| 4 | AX-03 | 1 | Route param schema per shipped route (string keys pages actually read) + `navigate` v2 + card page links | AX-01 | 1d | `sonnet-5` | Every `routeToPageId` route has a schema matching its page's `searchParams.get` / `useFilters` use (static test); e2e: 5 card links land with the race and driver selected | HD1 |
| 5 | AX-04 | 1 | Card registry + headless runner: Node DuckDB adapter for `rawQuery` / `registerParquet` over local published files | AX-01 | 2-3d | `opus-5` | race-lost, era-ratings-timeline and pit-strategy queries plus transforms run headless; output equals the page's for 3 fixed parameter sets each, at display precision | HD1 |
| 6 | AX-05 | 1 | Query catalogue v1 + `qv_*` exports + `catalogue.json`; export of `mart_race_driver_summary` (and the other rating and isolation marts, for later cards) | AX-02 | 2d | `opus-5` | Contract test: every `qv` column documented; deny-list test (no `*_component_s`, `*residual*`, `rating*`, `predicted*`, `*dirty_air*`, `*hazard*_shrunk`); each partition under 5 MB; `app-data-check` stable on re-run | HD1, **HD4** |
| 7 | AX-06 | 1 | Bounded query builder (`query_data`): validation, prepared params, partition-scoped registration, `LIMIT n+1`, 3 s cancel, fixed result shape | AX-05 | 3d | `opus-5` | 0 SQL strings from model input (code-path test); 500-case fuzz all returns structured errors; a test asserts only the filtered seasons are registered; timeout test cancels; every row has `n`; label `computed_not_card` | HD1 |
| 8 | AX-07 | 1 | Class-T card kinds (§2.4 T rows), class assignment by dbt lineage, ungrounded list, held pit-verdict cards | AX-04, AX-01 | 2-3d | `opus-5` | AI-01 acceptance: every card has every field or is refused with a reason; a thin and a clean race differ in n and interval; interval kind never relabelled; parity with the page for 20 (driver, race) pairs across ≥3 seasons; lineage table saved as evidence | HD1, **HD12** (v16 re-export) |
| 9 | AX-08 | 1 | Card publish: export ordering, `--finalize`, manifest `assistant` block, checksums, `catalogue_version`; Worker tool generator | AX-05, AX-07 | 1d | `sonnet-5` | Changing one card changes `manifest.version` and fails `--check` until regenerated; generated `worker/src/generated/tools.ts` carries the same `catalogue_version` | HD1 |
| 10 | AX-09 | 1 | Honesty policy additions: `computed_not_card` wording, held-card wording, WC modelled disclaimer (DD-WC2 exact text), unavailable-not-zero, page link required | AX-01 | 1d | `opus-5` | Each new rule has fail, pass and not_fired examples; `sources.node.test.ts` passes (every rule cites a line) | HD1 |
| 11 | AX-10 | 2 assistant | Assistant core v2: dispatcher for the 7 tools, page-card pre-load, loop cap 4, budget meter and truncation per slot, checker repair turn, headless CLI | AX-02, AX-03, AX-06, AX-08, AX-09 | 2d | `sonnet-5` (`opus-5` if the budget moves) | AI-04 tests (loop limit, empty, refused, number-without-source); 10 sample questions headless; budget log per slot; AI-10's 5-page explain check recorded (closes AI-10) | HD1 |
| 12 | AX-11 | 2 | `make_chart` + `compare_lap_times` (AI-11) on `qv_laps` | AX-06 | 2d | `sonnet-5` | >6 series or >500 points rejected; 2-driver comparison renders with n; no chart rows in the model context (headless check) | HD1 |
| 13 | AX-12 | 2 | Worker v2: question ticket, per-question limit, cap ≤ free allowance, generated tools and prompt, catalogue-version 409, output cap from measurement, tool-message size cap, CSP incl. Turnstile hosts | AX-08 | 1-2d | `sonnet-5` | Existing 16 tests pass; new: a 5-round question spends 1 Turnstile token and 1 visitor slot; round 6 refused; version mismatch → 409; default cap ≤ 10,000; bundle scan in CI with a planted key failing | HD1, **HD6**, **HD11**; owner preview deploy |
| 14 | AX-13 | 2 | Eval v2 (AI-07 bar kept): questions per class; held classes must be refused or hedged with the held reason; neurons per answer → answers per day | AX-10, AX-11 | 3d | `opus-5` | Bar recorded in the log before the first run; the grader fails a planted wrong answer for every question type; baseline run saved with tokens, neurons and cost per answer | HD1 |
| 15 | AX-14 | 2 | Chat drawer (AI-08) + render-time grounding + label rendering (measured / modelled hatch + disclaimer / unavailable "—") | AX-10, AX-12 | 3d | `sonnet-5` | AI-08 acceptance (phone width, keyboard, screen reader, reduced motion, proxy-down message); an unmatched number is struck and noted; flag off by default; e2e and perf budget pass | HD1 |
| 16 | AX-15 | 3 T\* | Card kinds downstream of the dirty-air tax (§2.4 T\* rows); export the isolation marts; dirty-air components stay `held` | AX-07 | 3-4d | `opus-5` | Same as AX-07, plus: no card carries a dirty-air price while WC is unlanded; VALIDATION_GRADE and PURE_PACE_WITHIN_ERA fire on fixtures | **HD2**; if "replaces": WC-06 + relabel |
| 17 | AX-16 | 3 WC | Traffic-cost cards from WC-06 outputs (labels per stint, totals with modelled share, unavailable counted not zero) | AX-15, WC-06 | 2d | `opus-5` | Every modelled card carries the DD-WC2 disclaimer rule; totals show the modelled share; no DA-03 number (carries WC W2/W11) | **WC-05, WC-06** (wake-calibration) |
| 18 | AX-17 | 3 ML | ML card kinds: prediction bands, in-envelope, cliff probabilities, model metrics (IN_SAMPLE, CV_FOLD rules), blind test; `model_version` from `app/public/models/manifest.json` | AX-07 | 2d | `opus-5` | OUTSIDE_ENVELOPE fires on an out-of-envelope fixture; every prediction card has a p10-p90 band; 2018 cards caveated (CD2) | **ML redo landed, CD10, HD8** |
| 19 | AX-18 | 3 ML | Pit-call verdict cards with measured reproduction rate | AX-17 | 1d | `opus-5` | PIT_CALL_REPRODUCTION_RATE passes on fixtures; held cards removed only once the rate is in the card | **W7 (D9/D14 re-measure on the redo model)** |
| 20 | AX-19 | 4 launch | Freeze: snapshot of manifest version, card checksums, catalogue, label and model versions (or a "no ML" freeze under HD5-A) | AX-14, AX-13, and AX-15/16/17 per HD5 | 0.5d | `sonnet-5` | Snapshot recorded; `board --check` passes; a re-export with an unchanged warehouse reproduces the checksums | **HD5**, CD10 (if ML in scope) |
| 21 | AX-20 | 4 launch | Launch run through the real drawer and Worker on the snapshot; owner switch-on | AX-19 | 1d | `sonnet-5` | AI-07/12 bar: 100% numbers grounded, 100% refusals correct, right tool ≥95%, no run over 18,000 tokens, human read passes; cost per answer recorded | Owner yes |

**Runnable now (technically):** AX-00 through AX-14 need nothing from the other tracks. AX-07 needs a v16 re-export (HD12) for its numbers to be current, though its code and tests can be built on the stale files. All of them are held only by PK1 until HD1.

**Wait on another track:** AX-15 waits on HD2 and possibly WC-06. AX-16 waits on WC-05/06. AX-17 and AX-18 wait on the ML redo, CD10 and W7. AX-19 and AX-20 wait on HD5.

Critical path for a transform-only v1 (if HD1 = A and HD5 = A): AX-01 → AX-04 → AX-07 → AX-08 → AX-10 → AX-13 / AX-14 → AX-19 → AX-20. That is roughly 15 to 20 agent-days plus owner gates. This is an estimate.

### Which model to run it on

Same vocabulary as the old board:

- **`fable-5.1`**: none here. No item builds an estimator.
- **`opus-5`**: anything that designs a contract (schema, catalogue, class lineage, policy rules, eval bar).
- **`sonnet-5`**: wiring to a written spec (entities, navigation, publish, Worker, drawer, freeze).
- **`haiku-4-5`**: none. Every item writes into the contract or produces a claim.

### Open decisions: these are the owner's, not tasks

- **HD1 (blocks every AX item): partial lift of PK1.**
  - A (recommended): allow Phase 1-2 on `main` now, with no ML or traffic numbers. Only class T cards go live, and held classes are refused by design.
  - B: keep everything parked until the ML branch lands.
  - C: allow Phase 1 only (foundations, no cards published).
- **HD2 (blocks AX-15): does wake-calibration replace or sit beside the 0.331 × share tax** in the lap decomposition? (WC-06 already names this as an owner call. Asking it now decides whether ratings, ghost car and constructor numbers can become cards before WC finishes.)
  - A: sits beside. Only the dirty-air bars are held.
  - B: replaces. All T\* cards wait for WC-06 and a new label version.
  - C: undecided. All T\* cards are held.
- **HD3: card production.**
  - A (recommended): precompute all cards at publish time with the features' own code run headless (frozen, checksummed, the grader reads a table).
  - B: resolve feature cards live in the browser (no extra files, but harder to freeze and grade).
- **HD4: query builder scope.**
  - A (recommended): observed measures only. Modelled values come only through cards.
  - B: also expose modelled components labelled `computed_not_card` (a looser reading of AD3).
- **HD5: launch scope.**
  - A: transform-only v1 allowed; ML and traffic questions are refused with the held reason. This is a new option beside CD13, which only ruled out launching on v14.
  - B: launch only with ML cards (CD13's spirit).
- **HD6: capacity under AD4-B.** Accept about 12 to 40 answers a day in total? Set the per-visitor limit per question (recommended 3 a day) and the daily cap at 10,000 neurons or under.
- **HD7: names source** for `list_values`. A: Jolpica reference (verify that it has names). B: a hand seed of drivers and race names. Also the display convention ("Charles Leclerc (LEC)").
- **HD8: version naming on cards.** `ML-RESET-PLAN.md` uses v16 for the ML retrain, but D11 says v16 = transform label and v17 = ML model. Which string goes in `model_version`?
- **HD9: old-board housekeeping** (AX-00): approve closing CO-32 and W11, moving AI-13, and moving the chance, stint-life and retrain items to the ML plan.
- **HD10: ADR.** Add ADR-011 "Assistant data access: cards plus bounded catalogue, published-only" to `docs/platform/architecture-decisions.mdx`, and record AD1 to AD5 there?
- **HD11: CSP widening** for Turnstile (`challenges.cloudflare.com` in script-src, frame-src and connect-src). This is already an open owner question in the AI-06 note.
- **HD12: re-export and publish** app data from the v16 sealed build (`make app-data` writes tracked files under `app/public/data/`; publishing to the CDN is separate).

### Watch list: kept an eye on, not tasks and not rulings

| ID | Kind | Item | Model | What | Clears when |
| :-- | :-- | :-- | :-- | :-- | :-- |
| AXW1 | ship-blocker | AX-12 | `sonnet` | No public Worker route without the per-question limit and a cap at or under the free allowance (carries W1) | AX-20 lands with the real cap |
| AXW2 | hazard | AX-16 | `sonnet` | No DA-03 number, and no 0.331 × share price presented as traffic cost once WC lands (carries WC W2/W11) | AX-16 lands and the card deny-list test is in CI |
| AXW3 | stale-artifact | AX-07 | `haiku` | Published `_manifest.json` (2026-10-16) predates the v16 seal | Re-export on the sealed build is recorded (HD12) |
| AXW4 | hazard | AX-08, AX-12 | `sonnet` | Catalogue and tool skew between the app and the Worker | The 409 version check is tested and deployed |
| AXW5 | debt | AX-06 | `sonnet` | `runLabQuery` materialises the whole result before capping; `registerPartitionedParquet` registers every season | The builder is shown not to use either (test) |
| AXW6 | pending-ruling | AX-17 | `opus` | Chance line stays EXCLUDE (AD5). No card kind may read `flag_chance_lookup.json`; W14 is moot for the assistant | The registry guard test exists |
| AXW7 | unverified | AX-12 | `sonnet` | gpt-oss-20b tool-call support on Workers AI, not re-confirmed (AI-06 step 1); reasoning tokens against `MAX_OUTPUT_TOKENS=800` | Confirmed from the model page and measured in AX-13 |
| AXW8 | pending-ruling | AX-18 | `opus` | D9/D14 re-measures owed on the redo model (W7). Pit-verdict cards stay held | The re-measure is recorded |
| AXW9 | stale-artifact | AX-00 | `haiku` | Old board pointer on CO-32 (archived method) | AX-00 lands |
| AXW10 | debt | AX-02 | `haiku` | `useDrivers.ts` queries columns `dim_drivers` lacks (`last_name`); appears unused | Fixed or deleted in its own item, or confirmed unused |
| AXW11 | unverified | AX-15 | `opus` | T / T\* classes in §2.4 are provisional, from column names | AX-07's lineage table is saved |

---

## 4. What I did not verify

- The **CDN** contents and version: I read only the local `app/public/data/_manifest.json`.
- Column names of `fct_telemetry_deltas`, `int_track_evolution`, `int_synthetic_teammate` and `int_qualifying_decomposed` beyond what `schema.yml` lists. Some schema entries look incomplete (for example `int_track_evolution` lists 3 columns).
- Whether each feature's sources are truly T or T\*. The §2.4 classes are guesses from names; AX-07 settles them by lineage.
- Whether Jolpica bronze carries driver and race display names.
- The `_misc/_chat/f1-chat` prototype (outside the repo).
- That the `ml-fresh-start` branch exists anywhere (it is not in `git branch -a`).
- Workers AI current pricing, tool-call support and prefix caching for `@cf/openai/gpt-oss-20b`. I used the AI-06 step-1 figures of 2026-10-24.
- Card counts and file sizes (estimates), and the neuron arithmetic (computed from budget slots, not measured).
- `@duckdb/node-api` fitness for running the app's query modules headless (not tried). `cancelSent()` exists in the installed duckdb-wasm typings; I did not test it.
- I did not run any test, build or dbt command, and did not open `data/*.duckdb`.
