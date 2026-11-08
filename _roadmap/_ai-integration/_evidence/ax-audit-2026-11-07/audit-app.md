# App audit: can an AI assistant use each shipped feature as an inference source?

Scope: `app/` (43 shipped routes in `app/src/nav/routes.ts`), `docs/app/*.mdx` (read through the generated summaries in `app/src/nav/pageSummaries.generated.json`), `app/src/data/**`, `app/src/nav/assistantTools.ts`, `app/src/assistant/honesty/*`, `worker/src/*`, plus the `_roadmap/_ai-integration` and `_roadmap/_wake-calibration` boards for what is blocked. Read-only: no app run, no tests run, no files changed apart from this report.

---

## 1. Verdict

**Today an assistant has no working path to the numbers.** The parts exist, but nothing joins them:

- The Worker has no tools and only a placeholder prompt (`worker/src/config.ts:10-12`, `TOOLS: unknown[] = []`). It passes tool calls through and never runs a query (`worker/src/handler.ts:169`). Nothing in `app/src` calls `/v1/chat`. `assistantTools.ts` and the honesty checker are imported only by tests.
- The only tools that exist are `navigate` and `explainPage` (`app/src/nav/assistantTools.ts:67,92`). Neither returns a number. `navigate` cannot reach a specific race or driver view (see 4.2).
- The only data path is free SQL through Query Lab (`app/src/data/duckdb/queryLab.ts`). v1 ruled that path out (`_roadmap/_ai-integration/README.md`, "Cut from v1 ... free SQL"). It also returns no `n`, no interval and no labels, and it is not bounded (see 4.1).
- Fact cards (AI-01), the query builder (AI-09), the chart and compare tools (AI-11) and the core loop (AI-04) are all **BLOCKED on PK1**. PK1 is the owner's 2026-10-24 ruling: "transform layer only; all ML and assistant items parked until the ML layer is redone on a separate branch" (`_roadmap/_ai-integration/status/build-log.json`, decision PK1).

**The feature code is a good base.** Every one of the 33 feature modules splits into `queries.ts` (named `registerQuery` functions that return plain rows), `transform.ts` (pure, tested) and `page.tsx` (render only). Only two pages hold logic the assistant would need (blind-test and model-metrics fetch the model card inside the component). So most features need **wrapping, not rewriting**.

**Four systemic gaps stop any feature from being citable as it stands:**

1. **No feature carries its own provenance.** Every page hard-codes `dataWindow: '2018–2025'` (e.g. `features/race-lost/page.tsx:67`). None reports its source mart, the data-manifest version or `model_version`. No query selects `model_version` from `mart_degradation_predictions`. The simulator hard-codes `modelVersion: '3'` and `datasetFingerprint: 'b8a37b7c'` (`features/degradation-simulator/page.tsx:273-274`), but the shipped models manifest says `v14`, fingerprint `5dbd8e51…`.
2. **Missing values are written as zero.** The lap waterfall and race-lost wrap every component in `COALESCE(AVG|SUM(x), 0)` (`features/lap-waterfall/queries.ts:48-56,74-82`; `features/race-lost/queries.ts:48`). A lap with no dirty-air measurement (NULL under FD6) adds 0 s. That breaks the "unavailable, never 0" rule (WC-06) and the spirit of `MISSING_RATING_IS_NOT_ZERO`.
3. **No feature has a measured / modelled / unavailable label.** That scheme exists only as the WC-06 plan, for dirty air (`_roadmap/_wake-calibration/wi/WC-06*.md`).
4. **The data being served predates the landed fixes.** The live CDN manifest is version `b9fbd7092b43b6dc`, generated 2026-10-03 (fetched during this audit). The local `app/public/data/_manifest.json` is `30f91247d7cb651e`, generated 2026-10-16. Both are older than CO-16 (sector tax), CO-30/31 (thin-cell and restart-lap fixes) and the v16 label seal (CO-33). So anything the assistant read through the app today could contradict cards built later from the trusted rebuild (AI-03 freeze).

**Count across the 43 routes:** 5 ready (as `computed_not_card`), 17 need extraction or fixes, 13 visual-only or navigation, 8 blocked.

---

## 2. Feature table (all 43 shipped routes)

Key:

- **ready**: the query and transform can be called outside React and already carry `n` plus an interval, or the claim is a plain count. A card wrapper and provenance are still needed.
- **needs extraction**: the numbers are reachable, but the interval, `n` or label is missing, dropped or computed wrongly.
- **visual-only**: navigation or a picture, with nothing to infer from.
- **blocked**: unfinished upstream work or an owner ruling stops honest use.

All loaders go through `loadManifest` → `getTablePath` → `registerParquet` → `rawQuery` (`app/src/data/manifest.ts`, `duckdb/register.ts`, `hooks/useQuery.ts`). "Q" means the feature's `queries.ts` and "T" its `transform.ts`.

### Home and pillar indexes

| Route | Readiness | Data | Answerable questions | Blockers and caveats |
|---|---|---|---|---|
| `/` Home | ready (counts only) | `_manifest.json` stats (`routes/home/index.tsx:54-55`) | "How many laps, drivers, circuits and seasons are covered?" | The "N/5 ml models beat baseline" tile (`home/index.tsx:201`) comes from `ml_model_count or 5` (`scripts/export_app_data.py:574`), so zero significant models would still show 5. `total_events = 6` comes from `dim_events`, not the 173 races. |
| `/ghost-car` | visual-only | none (PillarIndex) | none | Navigation only. |
| `/lap-decomposition` | visual-only | none | none | |
| `/tyre-strategy` | visual-only | none | none | |
| `/aero` | visual-only | none | none | |
| `/drivers` | visual-only | none | none | |
| `/constructors` | visual-only | none | none | |
| `/ml` | visual-only | none | none | |
| `/race-craft` | visual-only (stub) | none (`App.tsx:83` `<Stub>`) | none | Left out of `shippedPaths` by `STUB_ROUTES` (`assistantTools.ts:14`). |
| `/roadmap` | visual-only | none | none | Unshipped showcase. |

### Ghost car

| Route | Readiness | Data | Answerable questions | Blockers and caveats |
|---|---|---|---|---|
| `/ghost-car/standings` | **ready** | `int_driver_circuit_era_affinity`, `int_driver_race_skill_loro`; Q `queryGhostStandings` | "Who is quickest at circuit C in era E with the car removed?" | Carries CI, SE, `affinity_confidence` and `n_obs` (T:57-60). `CONFIDENCE_FLOOR = 0.3`. Amber rows can be extreme. A statistical reconstruction, not a simulation. Shares the race-grain rating with affinity and era ratings, so they are not independent evidence. |
| `/ghost-car/championship` | needs extraction | `fct_ghost_race_finish`; Q `queryChampionship*` | "What if driver D had been in car K for season S?" | Points sums carry no interval, only `avg_confidence`. Badged when fewer than 15 races pass `avg_recombination_confidence ≥ 0.3`. The host car is fixed in the URL `constructor` param as a string id. A counterfactual, not a prediction. |
| `/ghost-car/hidden` | needs extraction | `fct_ghost_race_finish`, `int_era_normalized_driver_rating`, `int_driver_circuit_era_affinity`, `dim_circuits`, `race_to_track` | "Which drives were masked by car or strategy?" | `finish_pos_se` exists. Same source as Championship, aggregated differently. A self-scenario check (predicted lap equals actual) catches data faults; keep it as an integrity guard. |

### Lap decomposition

| Route | Readiness | Data | Answerable questions | Blockers and caveats |
|---|---|---|---|---|
| `/lap-decomposition/waterfall` | needs extraction (partly blocked) | `fct_lap_residuals` (season partition) | "Why was D slow at race R: fuel, compound, car, dirty air or skill?" | No interval on any bar. `COALESCE(..., 0)` turns missing into zero (Q:48-56). The dirty-air bar is the pooled 0.331 × share rule that wake calibration is replacing. The driver is held in local state (`page.tsx:15`), so the view cannot be linked. The race key is the integer round (`page.tsx:23`). |
| `/lap-decomposition/race-lost` | needs extraction (partly blocked) | `fct_lap_residuals`; Q `queryRaceLost` | Same question as total seconds per cause, with `n_laps` | `COALESCE(SUM, 0)` (Q:48). Track noise is non-additive. The driver is held in local state (`page.tsx:17`). The race comes from a string `race` param. `CALIBRATION_FLAGGED_CIRCUIT` cannot fire because the flag is in no exported table (driver-consistency docs). |
| `/lap-decomposition/sectors` | **blocked** | `int_sector_residual_decomposed` | "Which sector lost the time?" | CO-16 landed in transform, but the served data is older, so sector sums can miss the lap by exactly 0.331 s on about 10.7k laps (CO-16 WI). Noisier than full-lap figures. AI-09 explicitly waits on CO-16 being exported. |

### Tyre and strategy

| Route | Readiness | Data | Answerable questions | Blockers and caveats |
|---|---|---|---|---|
| `/tyre-strategy/survival` | needs extraction | `fct_cliff_prediction_features`, `dim_compounds_season`, `race_to_track`, `dim_circuits`; Kaplan-Meier computed client-side (`computeKM` in Q) | "How long does compound X last before the cliff?" | No Greenwood or other CI on the KM curve. A censoring-dominated curve is a lower bound on tyre life. Envelope rules apply to the model chips. Race selected through the `race_id` param (`page.tsx:54`). |
| `/tyre-strategy/degradation` | needs extraction | `fct_cliff_prediction_features` | "How fast did compound X degrade in race R?" | The band is a driver-spread standard deviation (`std_pace_loss_s`), not an interval. Single-stint compounds are indicative only. |
| `/tyre-strategy/pit-gantt` | **blocked** | `int_pit_strategy_value`, `fct_stint_features`, `fct_lap_residuals` | "Was the pit call right?" | The query selects `optimal_pit_lap_confidence` (Q:126) but T drops it (T:26-39), so it never reaches the UI or CSV. `PIT_CALL_REPRODUCTION_RATE` requires quoting 33.9% (±2 laps), measured on v11 and marked stale; the re-measure belongs to CO-18, parked under PK1. "Overran" or "early" is not proof of a mistake. 266 stints are "unknown". |
| `/tyre-strategy/recovery` | needs extraction | `int_tyre_surface_vs_bulk_decoupling` | "Is the wear thermal (recoverable) or structural?" | No interval. The 0.35 boundary is soft. Covers post-cliff laps only. |
| `/tyre-strategy/party-mode` | needs extraction | `int_constructor_structural_pace(_qualifying)` | "Which team is a qualifying specialist?" | `delta_s` is a plain difference with no SE, although both inputs carry SEs (Q:40,58). Different lap populations. Derived from Structural Pace, so not independent of it. |

### Aero and conditions

| Route | Readiness | Data | Answerable questions | Blockers and caveats |
|---|---|---|---|---|
| `/aero/dirty-air` | **blocked** | `int_dirty_air_tax_component`, `fct_cliff_prediction_features` | "How much did traffic cost D?" | One pooled coefficient (0.331 s) for every circuit and season, with no interval. Wake calibration WC-05/WC-06 will add measured / modelled / unavailable labels and decide at its gate whether to replace or keep this rule. WC-10e is BUILDING. Read it as "laps spent following × constant". |
| `/aero/lap-map` | visual-only and blocked | `int_lap_air_state`, `fct_cliff_prediction_features` | "When was D in dirty air?" (qualitative) | Grey means clean air **or** missing telemetry, so an assistant must never infer "free air" from it. Same WC-06 dependency as Dirty Air Cost. |
| `/aero/track-evolution` | needs extraction | `int_track_evolution` | "How much did the track rubber in?" | No interval. The ambient term absorbs rubber signal on short races. |
| `/aero/field-pace` | needs extraction | `int_field_pace_curve` | "What was the field baseline on lap L?" | An upstream model input, not a conclusion. `low_sample_flag` marks thin regions. The served data predates the CO-31 restart-lap fix. |

### Race craft

| Route | Readiness | Data | Answerable questions | Blockers and caveats |
|---|---|---|---|---|
| `/race-craft/race-control` | **ready** | `race_caution_timeline`, `int_sc_hazard_history`, `race_to_track` | "When were the SC, VSC and red flags in R? How often do cautions happen?" | Wilson intervals (T:67) and an EB prior of 600 laps (T:119). No per-circuit SC probability by design. The best example of honest uncertainty in the app. Race selected through the `race_id` param (`page.tsx:44`). |

### Drivers

| Route | Readiness | Data | Answerable questions | Blockers and caveats |
|---|---|---|---|---|
| `/drivers/ratings-timeline` | **ready** | `int_era_normalized_driver_rating` | "How did D's margin over his teammate evolve?" | Carries CI, `rating_confidence` and `n_races`. A change of teammate moves the line. The bridge offset was dropped (F45). The same table feeds Era Translator. |
| `/drivers/era-translator` | **ready** | `int_era_normalized_driver_rating` | "Rank drivers on one scale in season S" | At least 5 races. Duplicates Ratings Timeline, so cite only one as a source. |
| `/drivers/consistency` | needs extraction | `fct_driver_skill_features` | "Who is consistent and who runs hot and cold?" | Mean and SD with no interval. `clean_lap_count ≥ 10`. The `REVIEW_REQUIRED` calibration flag is not exported, so `CALIBRATION_FLAGGED_CIRCUIT` cannot fire. |
| `/drivers/quali-vs-race` | needs extraction | `int_qualifying_decomposed` | "One-lap merchant or race driver?" | No interval. Qualifying residuals are noisy. At least 3 sessions. |
| `/drivers/circuit-affinity` | needs extraction | `int_driver_circuit_affinity` | "Where does D over-perform his teammate?" | Carries `affinity_confidence` and `n_obs`, but no CI is selected. Requires `n_obs ≥ 2`. Not independent of era ratings (docs WARNING). |
| `/drivers/wet-race` | needs extraction | `fct_driver_skill_features` | "Is D a wet-weather specialist?" | No interval. Wet races are rare and differ a lot. Lower confidence than the dry ratings. |
| `/drivers/workload` | needs extraction | `fct_cliff_prediction_features` | "Who is hardest on the tyres?" | Proxy measures. The dirty-air share depends on WC. Compare within a season only. |
| `/drivers/synthetic-teammate` | needs extraction | `int_synthetic_teammate` | "D's pace against a weight-corrected teammate" | Carries `avg_quality_weight` and `n_races ≥ 3`, but no interval. |
| `/drivers/corner-skill` | needs extraction | `mart_corner_skill_driver` (partitioned) | "Braking, mid-corner or exit strength" | z-scores only, no interval (Q:26-37). Requires at least 100 corners. The baseline is a per-constructor mean. |

### Constructors

| Route | Readiness | Data | Answerable questions | Blockers and caveats |
|---|---|---|---|---|
| `/constructors/structural` | **ready at race grain**; the season view needs a fix | `int_constructor_structural_pace(_qualifying)` | "Which team has structural (car) pace?" | The season mode averages the per-race SE and CI bounds (`constructor-structural-pace/queries.ts:62-65`). That gives an average of interval widths, not a season interval. |
| `/constructors/circuits` | needs extraction | `int_circuit_x_constructor_interaction`, `dim_circuits` | "Where does team K over- or under-perform?" | `n_races` and shrinkage (prior of 3) only, no CI. Thin cells are directional. A blank cell means fewer than 2 visits, not zero. |
| `/constructors/team-averages` | needs extraction | `fct_lap_residuals` | Car term, dirty-air tax and skill average per team | No interval. This is a second "car pace" number (`constructor_component_s`) next to the panel FE on Structural Pace, and the two can disagree. Includes the WC-dependent dirty-air tax. |

### The Machine, Query Lab, Data Quality

| Route | Readiness | Data | Answerable questions | Blockers and caveats |
|---|---|---|---|---|
| `/ml/blind-test` | **blocked** | `mart_degradation_predictions`, `fct_cliff_prediction_features`, `fct_stint_features`, plus `model_card.json` fetched inside the component (`page.tsx:44`) | "How well do the tyre models predict?" | Every season is in-sample until 2026 (`IN_SAMPLE_FIT`). The page never reads `model_version`. The models are v14 while the labels are v16 (CO-18 and CO-19 parked, PK1). |
| `/ml/simulator` | **blocked** (and visual what-if) | ONNX v14 (`app/src/ml/*`, `public/models/`), `fct_cliff_prediction_features`, `mart_degradation_history_envelope`, `dim_compounds_season` | "What if" tyre scenarios | AI-04 says "what if" questions get a link, not a computed answer. AI-05 is closed for v1. The chance line must not be quoted (`CHANCE_LINE_QUOTABLE`). Provenance is hard-coded and stale (`page.tsx:273-274`). |
| `/ml/metrics` | **blocked** | `model_card.json` (fetched in the component, `model-metrics/page.tsx:19`) | "Does model X beat its baseline?" | The headline is the 2025 CV fold, not a clean holdout (`CV_FOLD_NOT_CLEAN_HOLDOUT`). `WIN_CARRIES_INTERVAL` applies. PK1 applies. |
| `/query` | tool, not a source (v1: excluded) | every manifest table (`queryLab.ts`) | Anything, unbounded | See 4.1. |
| `/data-quality` | **ready** | `int_lap_anomaly_flags` | "How much of race R is usable, and why were laps dropped?" | The buckets cover every exclusion, so they are plain counts. This is the provenance companion for every per-race answer. |

**Totals:**

- 5 ready: standings, race-control, ratings-timeline, era-translator, data-quality.
- 17 needs extraction or fixes: home counts, plus the per-race grain of structural pace.
- 13 visual-only or navigation: 8 pillar indexes, the stub, the roadmap, lap-map, and Query Lab as a tool.
- 8 blocked: sectors, pit-gantt, dirty-air, lap-map (also counted above), blind-test, simulator, metrics, and the dirty-air terms inside waterfall and race-lost.

The boundaries overlap, so treat the per-row label as authoritative.

---

## 3. Chaining features into conclusions

### Chains the assistant can make, with conditions

1. **"Why was D slow at race R?"**
   - Start with Data Quality: usable %, so thin races get flagged early.
   - Then Race-lost: fuel, compound, car and skill seconds with `n_laps`.
   - Then Race Control: which laps were neutralised and therefore excluded upstream.
   - Then Pit Gantt for stint layout only (not the verdict), and Degradation Timeline for compound behaviour.
   - Rules: skill is "unexplained by the four physics terms", not "driver error". Name the dirty-air term as a pooled-rule estimate. Never add track noise. Today, refuse when a component is NULL; this needs the COALESCE fix first.
2. **"Which team has structural pace?"**
   - Use Structural Pace at race grain (CI) and quote per-race CIs or a properly pooled one.
   - Add Circuit Interaction for venue deviations, read as directional on thin cells.
   - Team Averages can corroborate but is not independent: same laps, different estimator.
3. **"Is D quicker than his teammate, and where?"**
   - Era Translator or Ratings Timeline (cite one), then Ghost Standings for circuit grain, then Corner Skill for phase.
   - Say they share the race-grain rating (affinity docs WARNING) and are not three confirmations.
4. **"Was the pit call right?"**
   - Describe the stint against the cliff lap and the model-optimal lap, with the Race Control SC timing for context.
   - Always carry the 33.9% reproduction-rate wording and "not proof of an error" (`PIT_CALL_REPRODUCTION_RATE`).
   - Do not give a verdict until CO-18 re-measures.
5. **"How often do safety cars happen?"**
   - Pooled Wilson rates from Race Control only.

### Chains the assistant must not make

- **Per-circuit SC probability** from any page. The Race Control finding is that the between-circuit share is 0.000.
- **Ranking drivers across different "skill" measures.** At least six definitions ship:
  - `driver_skill_residual_s` (waterfall)
  - `driver_residual_mean_s` (consistency)
  - `driver_skill_proxy_mean_s` (wet race)
  - the LORO race skill (ghost standings)
  - the era-normalised rating (timeline and translator)
  - `corner_skill_index`, the synthetic-teammate proxy and qualifying-decomposed skill

  Their ranks can disagree. An assistant must name which one it quotes.
- **Stacking affinity with era ratings** as independent evidence, or Party Mode with Structural Pace.
- **Two "car pace" numbers as one:** Team Averages `constructor_component_s` against the Structural Pace panel FE.
- **Championship or Hidden Performance as "would have won".** They are counterfactual reconstructions, and badged seasons are indicative only.
- **Blind-test or Model Metrics as out-of-sample performance** (`IN_SAMPLE_FIT`, `CV_FOLD_NOT_CLEAN_HOLDOUT`).
- **A grey lap-map cell as "free air"**, or Dirty Air Cost as a per-circuit aero measurement.
- **Sector attributions on the current data** (pre-CO-16).
- **Pure-pace comparisons across fit eras** (`PURE_PACE_WITHIN_ERA`), or anything about 2026 (`NO_2026_DATA`).
- **Mixing app-read numbers with post-freeze cards.** The served data (2026-10-03 on the CDN) predates the v16 seal.

### Contradictions already recorded

`policy.json` lists 7 contradictions, X1 to X8. X2 and X3 are grade disagreements that decide whether pure pace is suppressed. X4 is 1 against 30 circuits flagged `REVIEW_REQUIRED`. The checker follows whatever the card carries, so the cards must carry the stricter value.

---

## 4. Gaps in the current assistant tool surface

### 4.1 Query Lab (`app/src/data/duckdb/queryLab.ts`, `client.ts`)

- **Validation is regex only.**
  - `ALLOWED_LEADING` and `FORBIDDEN` are at `queryLab.ts:30-31`.
  - Table functions such as `read_parquet('https://…')` and `parquet_scan` are not blocked, so a query can fetch any URL. The CSP `connect-src` in `firebase.json` is report-only per AI-06, so nothing stops it yet. Not tested.
- **The row cap does not bound memory.** `result.toArray()` loads every row before slicing to `MAX_ROWS = 5000` (`queryLab.ts:17,123-127`).
- **No timeout.** `client.query` has none either (`client.ts:94-100`).
- **Partitioned tables are registered as a UNION ALL of all 8 seasons** (`register.ts:66-95`), including `fct_telemetry_deltas`. AI-09 says the 28.6M-row telemetry table must not be exposed.
- **Results carry nothing to cite:** no `n`, no grain, no source label, no `computed_not_card`.
- Matching tables by token works (`resolveTablesInSql`), but there is no `describe(view)` that costs about 300 tokens.

### 4.2 `navigate` / `explainPage` (`app/src/nav/assistantTools.ts`)

- **The filter contract does not match the pages.** `ALLOWED_FILTERS` is "All are integers" (`:7-8`) and `navigate` rejects non-integers (`:76`). But:
  - 11 pages read `race` as a string race id like `2024_1` (`useRaceOptions`), e.g. `race-lost/page.tsx:16` and `dirty-air-cost/page.tsx:43`.
  - The waterfall reads `race` as an integer round (`lap-waterfall/page.tsx:23`).
  - Three pages read `race_id`, which is not in the allowed list (`pit-strategy/page.tsx:50`, `tyre-cliff-survival/page.tsx:54`, `race-control/page.tsx:44`).
  - `constructor` is a string id on Championship and Hidden.
  - The driver is local state on race-lost and the waterfall, so it cannot be put in a URL at all.

  Result: `navigate` can open a page and a season, but no race, driver or host car.
- **`explainPage` works.** There are 44 summaries of 800 tokens or less, carrying the WARNING and NOTE caveats. But it returns prose only, no numbers.

### 4.3 Honesty policy and checker (`app/src/assistant/honesty/`)

- **The checker is sound and data-driven.** `checkAnswer` (`checker.ts:206`) runs regex wording and forbidden checks on the answer, plus predicates on the cards.
- **It depends on fact cards that do not exist.** Its `FactCard` is "loose on purpose until AI-01 lands" (`checker.ts:13-29`).
- **The rules miss several pages.** The 16 rules cover in-sample fit, 2026, thin samples, calibration, envelope, grades, pure pace, pit call and the chance line. Nothing covers:
  - the dirty-air pooled coefficient and its WC replacement
  - lap-map grey cells
  - Kaplan-Meier as a lower bound
  - counterfactual (ghost) claims
  - sector data before CO-16
  - the "skill definition" ambiguity
- **`CALIBRATION_FLAGGED_CIRCUIT` can never fire** from app data, because the flag is not exported (driver-consistency docs).
- **`applies_to.pages` uses docs paths** (`/app/<slug>`), while `assistantTools` uses routes and slugs. That is fine for triggers, which use `source_page` regexes, but there is no shared id.

### 4.4 Worker (`worker/src/`)

- **The safety scaffold is done and tested:** model and prompt fixed, `parseMessages` takes messages only and refuses a client "system" role (`handler.ts:63-77`), Turnstile, a per-visitor limit, a neuron ledger, pause, redaction.
- **The rest is missing:**
  - The tool definitions and system prompt, which AI-04 owns (`config.ts:9-12`).
  - Any app-side client, tool dispatcher or loop limit.
  - The Worker host in CSP `connect-src`.
  - `MAX_OUTPUT_TOKENS = 800`, while AI-04 budgets 4,000 tokens of output.

### 4.5 Tools that are missing altogether

| Tool (AI-04 list) | State | Note |
|---|---|---|
| `get_fact_cards` | absent; AI-01 BLOCKED (PK1) | No card table in the manifest (39 tables, none of them cards or rating marts). |
| `query_data` (builder) | absent; AI-09 BLOCKED | `runLabQuery` could be its runner once 4.1 is hardened. |
| `list_values` | absent | `dim_drivers`, `dim_constructors`, `dim_events` and `race_to_track` exist. `dim_constructors` and `dim_events` are unused by the app. Needed to resolve "Hamilton" to the right id and "Interlagos 2021" to `2021_19`. |
| `compare_lap_times` / `make_chart` | absent; AI-11 BLOCKED | The prototype lives outside the repo (`_misc/_chat/f1-chat`). `ui/charts/*` are React-only. |
| `explain_page` / `navigate` | present, not wired | Fix 4.2. |

---

## 5. Concrete work items in app code

Sizes: S is about half a day or less, M is 1-3 days, L is more than 3 days. Items marked PK1 cannot land as assistant features until PK1 is lifted. The data-correctness fixes (1-6) are worth doing regardless.

| # | Item | Size | Files |
|---|---|---|---|
| 1 | Stop writing missing values as 0: drop `COALESCE(...,0)`, add per-component `n_null`, and show and return "unavailable" | S | `features/lap-waterfall/queries.ts:48-82`, `features/race-lost/queries.ts:48+`, both `transform.ts` |
| 2 | Carry `optimal_pit_lap_confidence` through the transform and CSV | S | `features/pit-strategy/transform.ts:26-39,81` |
| 3 | Season Structural Pace: replace `AVG(ci_low/high, se)` with a pooled SE (precision-weighted mean, `1/sqrt(Σ1/se²)`) and derive the CI from it. Add the delta SE `sqrt(se_q²+se_r²)` to Party Mode | S-M | `features/constructor-structural-pace/queries.ts:58-72`, `features/party-mode/queries.ts:40,58` |
| 4 | Provenance from manifests, not literals: data `manifest.version` and `generatedAt`, the source table list per query, and `model_version` from `public/models/manifest.json`. Remove the simulator's `'3'` / `'b8a37b7c'` | S-M | `ui/methodology/Provenance.tsx`, `ui/layout/FeaturePage.tsx`, all `features/*/page.tsx` provenance props, `features/degradation-simulator/page.tsx:272-276` |
| 5 | Move the model-card fetch out of the components into a shared loader | S | `features/blind-test-scoreboard/page.tsx:40-50`, `features/model-metrics/page.tsx:9-25`, new `src/ml/modelCard.ts` |
| 6 | Home tile: stop the `or 5` fallback and show "unknown" (pipeline-side) | S | `scripts/export_app_data.py:574`, `routes/home/index.tsx:201` |
| 7 | One filter contract: string `race` (`YYYY_R`) everywhere, `race_id` renamed to `race`, and URL-addressable `driver` and `constructor` (string ids). Update `ALLOWED_FILTERS` and validation to match | M | `state/FilterContext.tsx`, `nav/assistantTools.ts:7-8,67-85`, `features/{pit-strategy,tyre-cliff-survival,race-control}/page.tsx`, `features/{lap-waterfall,race-lost}/page.tsx` (driver state) |
| 8 | A headless feature catalogue: route → named query fn, param schema, grain, source tables, value / `n` / interval column mapping, interval kind, caveat codes, label (measured or modelled). This is the bridge from the existing `queries.ts`/`transform.ts` to cards and tools | M | new `src/assistant/featureCatalog.ts`; reuses each `features/*/queries.ts` export. Note `register.ts:23,77` needs `window.location`, so it runs in the browser only; the headless AI-07 loop needs a base-URL injection |
| 9 | Harden `runLabQuery` for builder use: block table functions and URL literals, enforce a `LIMIT` in the SQL rather than slicing after `toArray`, add a timeout (interrupt the connection), keep a view whitelist that leaves out `fct_telemetry_deltas` | S-M | `data/duckdb/queryLab.ts:30-31,110-133`, `data/duckdb/client.ts:89-101`, `queryLab.test.ts` |
| 10 | Query builder (AI-09): request schema, whitelist validation, SQL generation, fixed result shape (`n`, `grain`, `rows_shown ≤ 25`, `computed_not_card`), a `describe` call, a 200-call fuzz test | L (3d) | new `src/assistant/queryBuilder.ts` on `runLabQuery` (PK1) |
| 11 | `list_values(kind, query)`: drivers, constructors, races and circuits from the dim tables, returning exact codes | S | new `src/assistant/listValues.ts`; `features/shared/useRaceOptions.ts` already has the race SQL |
| 12 | App-side fact-card lookup and JSON Schema check, once AI-01 publishes the card table | M | new `src/assistant/factCards.ts`; aligns `checker.ts:15-29` `FactCard` (PK1, plus pipeline `scripts/export_app_data.py`) |
| 13 | Policy additions: the dirty-air pooled-rule and WC-pending rule, lap-map grey, Kaplan-Meier lower bound, counterfactual ghost, sectors before CO-16, and a "name the skill measure" rule. Plus a shared page id (route ↔ docs slug) | S-M | `assistant/honesty/policy.json`, `nav/assistantTools.ts:21-64` |
| 14 | Export the `calibration_flag` into `dim_circuits` so `CALIBRATION_FLAGGED_CIRCUIT` can fire (pipeline) | S | transform `dim_circuits`, `scripts/export_app_data.py` |
| 15 | Kaplan-Meier with a Greenwood CI. Degradation timeline: label the band "driver spread (SD)", not an interval | S | `features/tyre-cliff-survival/queries.ts` (`computeKM`), `features/stint-degradation-timeline/transform.ts` |
| 16 | Chart and compare tools (AI-11): fixed spec at most 6 × 500, rows kept out of the model's context, `n` on every chart | M | new `src/assistant/chartTool.ts`, `ui/charts/*` (PK1) |
| 17 | Dispatcher, loop limit (4 calls), Worker client with Turnstile, tool schemas and system prompt in the Worker, CSP host | M | new `src/assistant/{dispatch,client}.ts`, `worker/src/config.ts:9-12`, `firebase.json` (PK1) |
| 18 | Dirty air: replace or label the two pages and the dirty-air terms in waterfall, race-lost and team averages with the WC-06 measured / modelled / unavailable output and the approved disclaimer | M-L | `features/dirty-air-cost/`, `features/dirty-air-lap-map/`, plus the components above. Gated on WC-05 and the WC-06 owner gate |
| 19 | Republish the app data from the trusted, v16-sealed build (AI-03 freeze) before any card or builder answer goes live | owner and pipeline | CDN `data/_manifest.json` (now 2026-10-03), `app/public/data/_manifest.json` (2026-10-16) |

---

## 6. What I did not verify

- **Nothing was run.** I did not start the app or run tests. Every claim about runtime behaviour comes from reading code: the cost of `toArray`, that `read_parquet` with a URL gets through, CSP blocking.
- **Docs were read through their generated summaries.** I used the ≤800-token summaries (the WARNING and NOTE blocks) and did not read each `docs/app/*.mdx` in full. Summaries are built from the docs, and AI-10 tests are meant to catch drift, but I did not re-check that.
- **Not every file was read in full.** I did not read every `page.tsx` or `methodology.tsx`. Readiness rests on `queries.ts`/`transform.ts` exports and a grep for computation inside pages. PillarIndex content was not inspected.
- **Live data was checked only at the manifest level.** I fetched only the CDN `_manifest.json` header. I did not inspect partition contents or check that the CO-16 error is present in the served sector parquet; that comes from timing, not measurement.
- **Model files on Firebase Hosting were not checked.** I did not confirm that the deployed `public/models/*` match the local v14 files.
- **Two filter details were not confirmed:** how the `driver` filter is used on every page (I checked race-lost and the waterfall), and the exact encoding of the `constructor` param.
- **Worker tests were not run.**
- **Wake-calibration status is from `board.py` output on 2026-11-07** (WC-10e BUILDING, WC-05/06 SPEC). Its README still says "plan only" and is out of date against the board.
- **"Ready" means as `computed_not_card`.** Under AI-04, rated and modelled numbers may be quoted only from fact cards, which do not exist yet. The five "ready" features are citable only under that label.
