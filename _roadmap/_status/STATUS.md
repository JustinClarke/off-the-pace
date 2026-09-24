# Off The Pace — Status & Statistics

> **Solo-built F1 analytics platform.** Ingestion → physics-first lap decomposition →
> survival analysis → gradient-boosted ML → zero-server browser app with in-browser SQL
> and in-browser ML inference. 149 races. 137 k decomposed laps. 876 automated tests.
> One enforced mathematical invariant.

Every figure below is swept from the live repository (compiled dbt manifest, ML manifest,
source tree). Where the README or docs lag behind, this document reflects ground truth.

---

## 1. Data & Coverage

| Dimension | Scale |
|---|---|
| Seasons | 2018–2024 (7 full F1 seasons) |
| Races ingested | 149 Grand Prix events, 147 fully lap-decomposed |
| Decomposed laps | **137,447** (each with all seven additive physics terms) |
| Raw telemetry | **90 M+ rows per season** at ~10 Hz interpolated resolution |
| Grain | Lap × driver × stint — every term in seconds relative to the field |
| Public data bundle | 1,674 Hive-partitioned Parquet files shipped as a browsable open dataset |
| Out-of-sample holdout | 2025 season reserved; reproducible OpenF1 validation (re-run it and get the same numbers) |

---

## 2. Ingestion Layer (Bronze)

Raw F1 telemetry goes from two independent APIs to Hive-partitioned Parquet without any
transformation — the Bronze layer is a faithful, append-only, auditable copy of the source.
All business logic lives downstream in dbt where it is version-controlled, tested, and
re-runnable without re-pulling from the API.

| Capability | Detail |
|---|---|
| **Data sources** | **FastF1** (session telemetry, timing, lap data) + **Jolpica** (Ergast successor: championship standings, pit-stop history) |
| **Output format** | Hive-partitioned Parquet (`dataset/season=YYYY/race=<slug>/`) — DuckDB partition-prunes at read |
| **Idempotent writes** | Completed races are skipped in milliseconds on re-run; only gaps are pulled |
| **Exponential-backoff retry** | 1 s → 2 s → 4 s → 8 s — transient FastF1/network blips self-heal |
| **Tiered DQ severity** | Race-lap schema failures block the write; qualifying checks warn-only (short/red-flagged sessions are common) |
| **Run manifest** | Every attempt — ok, skip, error — recorded with row count, DQ flag, and a SHA-1 schema fingerprint. The run is queryable after the fact and doubles as a CI gate |
| **Schema drift detection** | FastF1's schema drifts between seasons. The fingerprint makes drift *detectable*, not silently absorbed |
| **Replay simulator** | Deterministic re-ingestion from on-disk cache for integration testing |

**Design philosophy:** Bronze is dumb; logic lives in dbt. A transform bug never costs a
re-ingestion.

---

## 3. Transform Layer (dbt + DuckDB)

The transform layer is a 60-model dbt project running on DuckDB — the entire analytical
warehouse builds locally in seconds with zero cloud credentials.

| Component | Count | Detail |
|---|---|---|
| **Staging models** | 12 | Clean and type Bronze → `stg_laps`, `stg_weather`, `stg_telemetry`, `stg_race_control` |
| **Intermediate models** | 34 | The physics & fixed-effects engine room: fuel state, stint geometry, field pace curve, compound cliff prediction, track evolution, dirty-air tax, air density, synthetic teammate, constructor structural pace, circuit×constructor interaction, lap residual decomposition |
| **Gold marts** | 10 | Feature-serving tables consumed by ML and the app: `fct_lap_residuals`, `fct_cliff_prediction_features`, `fct_ghost_race_finish`, `fct_driver_skill_features`, and degradation history/envelope marts |
| **Reference dims** | 4 | Drivers, constructors, circuits, compounds-by-season |
| **Tests** | **443** | CI-enforced: unique, not-null, relationships, accepted-values, plus **29 bespoke singular tests** including the additive-identity invariant |
| **Macros** | 7 | Including `assert_additive_identity` (the CI contract) and `normal_cdf` (hand-rolled erf for DuckDB which lacks it natively) |
| **Seeds** | 7 | Physics/reference seeds: compound cliff params (401 groups), corner geometry, circuit reference, tyre allocations, manual lap exceptions, race-to-track mapping, raw event dims |
| **Coefficient fitters** | 4 Python modules | `fit_compound_cliff`, `fit_weight_penalty`, `fit_constructor_car_fe`, `fit_degradation_isotonic` — each reads the warehouse read-only and writes fitted parameters for human review before promotion |
| **Output** | Local `dev.duckdb` **or** production DuckDB-Wasm Parquet bundles |

**Intermediate model highlights** (the 34-model physics engine):

- **`int_lap_fuel_state`** — fuel mass estimated per lap from burn rate and circuit length
- **`int_stint_geometry`** — stint boundaries, tyre age, compound assignment per lap
- **`int_field_pace_curve`** — trimmed-mean field baseline (fastest/slowest 10% excluded) with 5-lap centred smoothing
- **`int_compound_cliff_predicted`** — KM-estimated cliff onset applied to every stint
- **`int_track_evolution`** — rubber accumulation (monotone-increasing) and ambient temperature signals separated by structural asymmetry
- **`int_dirty_air_tax`** — aerodynamic wake penalty per lap, calibrated from partial residuals
- **`int_constructor_structural_pace`** — team car pace relative to field median
- **`int_circuit_x_constructor_interaction`** — circuit-specific constructor affinity
- **`int_synthetic_teammate`** — within-team comparison controlling for tyre state, strategy divergence, and lap quality
- **`int_lap_residual_decomposed`** — the full seven-term decomposition: fuel + compound + rubber + ambient + constructor + dirty_air + driver_skill, summing to pace_delta within 0.0001 s

---

## 4. The Mathematical & Statistical Engine

Every lap is decomposed into seven additive, physically-grounded components:

```
pace_delta = fuel + compound + rubber + ambient + constructor + dirty_air + driver_skill
```

### CI-Enforced Physical Invariant

The seven terms reconstruct `pace_delta` to within **0.0001 s** (0.1 ms). The
[`assert_additive_identity`](../transform/macros/assert_additive_identity.sql) macro
runs on every lap in CI. If any lap violates the identity, the dbt build fails and the
merge is blocked. Observed reconstruction error: **1.4 × 10⁻¹⁴ s** (machine precision).

A stated invariant is documentation. An enforced invariant is a contract.

### Sequential Residualisation

All six physics terms are active on every lap simultaneously. Estimating any one requires
holding the others constant. The project breaks this circularity by estimating terms in
order of **decreasing identifiability**, subtracting each before estimating the next:

1. **Fuel** — most constrained: fuel mass is computable from lap number, circuit length, and
   known burn rate. Weight penalty calibrated per circuit:
   $w \approx 0.02 + 0.0002 \times \text{corner\_count} \times \text{avg\_lateral\_g}$
   (giving ~0.018 s/kg at Monza, ~0.035 s/kg at Suzuka).
   Empirically calibrated via first-stint regression in
   [`fit_weight_penalty.py`](../transform/tasks/coefficients/fit_weight_penalty.py).
2. **Compound + Rubber + Ambient (jointly)** — separated by structural signatures:
   - Tyre wear → identified by within-driver stint-level variation
   - Track rubber → monotonically increasing (grip always improves as rubber builds)
   - Ambient temperature → non-monotonic (can rise or fall), distinguishing it from rubber
3. **Constructor** — panel fixed-effects on race-year-constructor combinations
4. **Dirty air** — regression of partial residuals against `dirty_air_share`
5. **Driver skill** — the closure: whatever remains after all six physics terms are subtracted.
   Defined as a residual, never estimated independently — guaranteeing the identity closes
   exactly

### HDFE Two-Way Fixed Effects (Car vs Driver De-biasing)

The hardest problem in F1 analytics: separating car quality from driver quality. A naive
team-average lap time absorbs the driver's skill, creating the "Albon/Sargeant Zandvoort
bug" — a weak driver on a slow car floats to the top because the car pace is contaminated
by who drove it.

Solved with a two-way High-Dimensional Fixed Effects panel regression:

$$\text{pace\_delta\_s} \sim 1 \mid \text{driver\_id} + \text{constructor\_race}$$

The constructor×race fixed effect absorbs the car net of driver skill. The driver FE is
identified globally because every constructor races every event. Implemented in
[`fit_constructor_car_fe.py`](../transform/tasks/coefficients/fit_constructor_car_fe.py)
using `pyfixest`.

### Right-Censored Kaplan-Meier Survival Analysis

F1 teams pit *before* the cliff. Every voluntary pit is a right-censored observation —
"I stopped the experiment early." Naive regression treats these as complete stints,
systematically underestimating tyre life.

The project models cliff onset as a **time-to-event survival problem** using the
Kaplan-Meier estimator in [`survival.py`](../transform/tasks/coefficients/survival.py):

$$S(t) = P(\text{cliff has not occurred by lap } t)$$

- **Event definition:** lap time exceeds 5-lap trailing median by ≥ 0.5 s for ≥ 2 consecutive laps (filters lockups/track-limits anomalies)
- **Censoring:** voluntary pits are censored at the lap before exit
- **Forced stops** (DNF, crash, SC pit): treated as uncensored — the team did not choose to stop
- **Output:** median survival time = cliff onset estimate τ, stored per (circuit, compound, season) in `dim_compounds_season` across **401 groups**
- **Why KM over Cox PH:** groups are already stratified by (circuit, compound, season); Cox PH requires shared baseline hazard that doesn't hold across compounds. KM is robust to small N and the median has a direct physical interpretation

### Non-Linear Wear Polynomials (Hockey-Stick Model)

Tyre degradation is captured by a piecewise polynomial that steepens sharply after the cliff:

$$\text{compound}(\text{age}) = \beta_0 + \beta_1 \cdot \text{age} + \beta_2 \cdot \text{age}^2 + \beta_3 \cdot \max(0,\, \text{age} - \tau) + \delta_T \cdot \text{temp\_delta}$$

$\tau$ is the KM-estimated cliff onset; $\beta_3$ is the post-cliff degradation acceleration.
All coefficients are fitted per (circuit, compound, season) in
[`fit_compound_cliff.py`](../transform/tasks/coefficients/fit_compound_cliff.py).

### Isotonic Regression Degradation Envelopes

The browser-based tyre simulator requires physically monotone degradation curves. Weighted
isotonic regression ($\text{IsotonicRegression}(\text{increasing}=\text{True})$) enforces
monotonicity across the 10th, 50th, and 90th percentiles simultaneously, with n-weighted
fits and sklearn clip (flat-hold beyond the observed range). Calibrated across all
(circuit, era, compound) cells in
[`fit_degradation_isotonic.py`](../transform/tasks/coefficients/fit_degradation_isotonic.py)
— including dirty-air multipliers and compound-specific temperature headroom/penalty
coefficients.

---

## 5. Feature Engineering & Physics

The ML feature spine carries **42 engineered inputs** (v4), grouped by physical mechanism:

| Family | Features |
|---|---|
| **Tyre & compound physics** | grip peak, wear gradient, optimal-temp window (low/high), cliff-onset laps, cliff severity, expected compound pace & degradation rate |
| **Cliff dynamics** | cliff-onset-passed flag, laps-past-cliff, cliff-candidate flag |
| **Push-load thermal model** | push residual, cumulative push load (surface + bulk), surface-bulk ratio |
| **Dirty-air model** | dirty-air share per lap, thermal load (surface + bulk), dominant air state |
| **Telemetry micro-features** | gear changes, mean/max RPM, % full throttle, % DRS active, short-shift index, mid-corner speed loss, traction/wheelspin proxy, throttle-trace decay, braking-point drift, lift-coast share |
| **Environment & circuit** | ambient-temp delta, rain-lap flag, track energy index, circuit abrasiveness index |
| **Context & anomaly** | lap number, lap-in-stint, age-in-stint, fuel mass, compound, constructor, event flag, anomaly class |

Every feature is computed in the dbt transform layer. The ML layer reads; it never
computes features.

---

## 6. Machine Learning Layer

Five gradient-boosted models score every lap from `fct_cliff_prediction_features`
(137 k laps, 42 features). Every model beats a strong per-cohort baseline on its
headline metric.

### Headline Results

| Model | Metric | Eval (2024 holdout fold) | Per-Cohort Baseline | Beats Baseline? |
|---|---|---|---|---|
| `degradation_regressor_p10` | pinball loss ↓ | **0.0941** | 0.1792 | ✅ |
| `degradation_regressor_p50` | pinball loss ↓ | **0.1997** | 0.3037 | ✅ |
| `degradation_regressor_p90` | pinball loss ↓ | **0.1231** | 0.1554 | ✅ |
| `cliff_classifier` | macro-F1 ↑ | **0.3278** | 0.2318 | ✅ (1.4× prior) |
| `stint_life_regressor` | RMSE ↓ | **8.090** | 9.498 | ✅ |

### Calibration

The quantile trio claims an 80% prediction interval `[p10, p90]`. On the 2024 evaluation
set (n = 19,067 laps):

| Measure | Value |
|---|---|
| Nominal target | 0.800 |
| Empirical coverage | **0.814** |
| Split-conformal (CQR) coverage | **0.805** |
| Conformal correction q | −0.014 |
| Mean interval width | 1.238 s |

The raw quantiles already land close — empirical coverage slightly over-covers at 0.814.
The split-conformal step (q = −0.014) *tightens* the interval to 0.805, within half a
point of nominal — a confirmation pass, not a rescue.

### Leakage Spine (CI-Enforced, 5 Guards)

| Guard | What it proves |
|---|---|
| **No leaked columns** | Targets, driver-skill signals, and season identifiers never enter the feature matrix |
| **No forward-looking features** | A `sqlglot` audit walks the compiled dbt mart and all ancestors, rejecting any `LEAD` or `FOLLOWING` window function |
| **Holdout purity** | No holdout-season row appears in any training fold |
| **No hard-coded holdout** | The split is `MAX(race_year)+1`-derived, never a literal year — the test suite enforces this |
| **Bounded / non-null targets** | Degradation ∈ [−10, 10]; no NULL-target rows enter training |

### The Adversarial Leakage Probe

The two most consequential feature exclusions — `driver_id` and `race_year` — are justified
by **demonstration, not assertion**. A throwaway XGBoost model trained to recover `race_year`
from the remaining features achieves **0.987 accuracy** (majority-class baseline: 0.168).
That is precisely why it must be excluded: constructor identities and compound generations
carry such a strong residual temporal signal that `race_year` is near-perfectly recoverable
as a backdoor to outcomes.

### ONNX Export & Browser Parity

Every booster round-trips to ONNX within `atol=1e-5`. The parity sample is deliberately
NaN-bearing (47% of laps have a null cliff-onset prior) to confirm that XGBoost's native
default-direction splits round-trip correctly. Numbers in the browser match numbers from
training — proven, not claimed.

### Model Governance

- **Current version:** v4 (42 features); full v1→v4 lineage retained for model diffing
- **25 ONNX artifacts** on disk across versions + smoke builds
- **Hyperparameter tuning:** Optuna (`TPESampler` + `MedianPruner`, seeded), 9-dimensional search with per-fold pruning
- **Auto-generated model card:** metrics, baselines, calibration, dual feature importance, limitations, cohort losses — built from `model_card.yml`, never hand-edited
- **Cohort transparency:** 15 underperforming cells are surfaced in the model card rather than hidden (the contract: record losses, never drop them)
- **28 ML tests** in CI: leakage spine, ONNX parity, output schema, beats-baseline

---

## 7. Analytics & Research Tooling

**26 standalone scripts** powering research, validation, reference generation, and CI:

| Script | What it does |
|---|---|
| **`mc_finish_order.py`** | Pure-function Monte Carlo finish-order simulator: draws pace from Normal(μ, SE), ranks into full position distributions with `p_win`, `p_podium`, `p_beats_next`, and SE-propagated confidence. Deterministic (RNG passed in), side-effect-free — the same core intended for the live engine |
| **`driver_network_rating.py`** | Massey teammate-network rating system: chains all pairwise teammate head-to-heads into a global Massey rating via weighted least-squares on the graph Laplacian ($\Sigma r = 0$ anchor). Three era scopes (all-time, pre-2022, post-2022). Sufficient-sample flag for consumers |
| **`validate_gate.py`** | **614-line GO/NO-GO validation harness** (5 steps): teammate-swap degradation test, team-change counterfactual transfer test (bootstrap CI), leave-one-race-out finish-order backtest (Spearman/Kendall vs host-invariant baseline), pairwise probability calibration (Brier score + variance-inflation k* fitting), and MC-vs-analytic consistency check. Outputs gate_metrics.json + gate_metrics.md |
| **`ablation_telemetry.py`** | Feature-contribution ablation study |
| **`export_app_data.py`** | Warehouse → app Parquet export pipeline with manifest versioning |
| **Reference generators (5)** | dbt models, macros, schema, ML model card, CLI — all generated from source manifests; CI fails on drift |
| **Docs-facts family (5)** | `docs_facts` + per-tab `overview_/ingestion_/transform_/ml_docs_facts` cross-reference headline counts in docs vs compiled manifests; flag stale numbers |
| **`docs_audit.py` + `app_docs_audit.py`** | Strict CI gates asserting every model/feature/route is documented and every methodology link resolves |
| **`gen_project_graph.py` + `watch_project_graph.py`** | Emit and live-watch the `project-graph.html` dependency deliverable |
| **`analyze_race_case_study.py`** | Decompose a single race lap-by-lap for the attributed-findings case studies |
| **`smoke_test_season.py`** | Season-level smoke tests for quick validation |

### The Validation Gate in Detail

The `validate_gate.py` harness is a 5-step statistical validation suite:

1. **§4.1 Teammate-swap harness** — measures within-team degradation gap slope vs age-in-stint.
   Confirms constructor-shared degradation is unbiased (mean slope ≈ 0) and quantifies the
   signal-to-noise ratio of constructor reordering signals
2. **§4.2 Team-change counterfactuals** — tests whether driver skill residuals transfer across
   constructor changes (bootstrap CI on switcher-vs-stayer MAE gap)
3. **§4.3 Leave-one-race-out backtest** — structural finish-order prediction
   (LOO skill + constructor pace + circuit×constructor) vs host-invariant baseline, scored
   with Spearman ρ, Kendall τ, and top-3 hit rate, paired-bootstrap on per-race gap
4. **§4.4 Pairwise probability calibration** — reliability curve, Brier score, and
   variance-inflation k* that would recalibrate the live confidence band
5. **§4.5 Offline Monte Carlo core** — validates the simulation against analytic
   Poisson-binomial quantities: p_beats_next, position-matrix row/column sums (valid
   permutation check), expected-position monotonicity in pace

---

## 8. App & Frontend (React + DuckDB-Wasm + ONNX Runtime Web)

A zero-server, browser-native analytics platform. Your browser IS the compute server.

### Architecture

```
Firebase Storage CDN ─── versioned Gold Parquet + ONNX model bundles
                              ↓
            DuckDB-Wasm (WebAssembly) ─── sub-10 ms analytical SQL
                              ↓
            ONNX Runtime Web (WebAssembly) ─── client-side ML inference
                              ↓
            React UI ─── charts, simulators, SQL editor, filters
```

No backend server at any point. Zero compute cost. Infinite horizontal scalability.

### Performance & Scale

| Metric | Value |
|---|---|
| Query latency | **< 10 ms** (local in-browser SQL on Parquet) |
| Server compute cost | **$0** (all computation runs in the user's browser) |
| ML inference | 5 XGBoost models scored client-side via WebAssembly |
| ONNX parity | $\text{atol} = 10^{-5}$ (proven, not claimed) |
| Source scale | **328 TypeScript files** (161 `.tsx` + 167 `.ts`) |
| Chart primitives | 8 reusable components: Gantt, Heatmap, Line-with-CI-Ribbon, Quantile Fan Chart, Ranked Table, Scatter, Survival Curve, Waterfall |
| Content routes | 12 total (9 shipped, 3 coming soon) |
| Tests | **310 passing** (rendering, routing, data-layer, WebAssembly ONNX inference) |

### Signature Interactive Features

**Ghost Car Standings** — The headline feature. Every driver is placed in every other
team's car using the HDFE-debiased skill residuals + constructor pace + circuit×constructor
interaction. Full standard-error propagation via Monte Carlo simulation produces
`p_beats_next`, `p_win`, `p_podium`, and position SE. Per-circuit/era driver affinity
in equal cars — answering "who is actually the fastest driver?" with honest uncertainty
bands.

**Tyre Degradation Simulator** — Dial compound, fuel load, dirty-air share, and ambient
temperature delta via live sliders. The XGBoost quantile trio scores every simulated lap
in-browser via ONNX Runtime Web, producing a fuel-corrected absolute lap time curve with
a calibrated p10/p90 uncertainty fan overlaid on the historical degradation envelope.

**Lap Decomposition Waterfall** — Select any driver, any lap, any race. See the seven-term
breakdown as a waterfall chart: fuel, compound, rubber, ambient, constructor, dirty air,
driver skill. Verify the identity closes to 0.0001 s yourself.

**Query Lab** — A full SQL editor running against the gold-mart Parquet files. Write any
analytical query. No credentials, no server, no API — DuckDB-Wasm and your browser.

### CDN & Deployment Pipeline

Firebase Hosting serves the app. Gold Parquet files and ONNX model bundles are synced to
Google Cloud Storage. A `manifest.json` with a `version` field cache-busts every data
change — so a warehouse rebuild is never masked by stale browser/CDN caching.
Zero-downtime data deployments.

---

## 9. Documentation (Mintlify)

A full Mintlify site organised into **6 top-level tabs**, **196 pages** (190 `.mdx` +
6 `.md`) — built out from a flat narrative set into a layered, per-layer documentation
platform with auto-generated reference and CI drift gates on every tab.

| Tab | Pages | What it covers |
|---|---|---|
| **Overview** | 5 | What-you-can-do, glossary, and attributed case studies — São Paulo 2021 (Hamilton vs Verstappen: strategy 2.91 s, driving skill 1.60 s on the overtake lap) |
| **Data** | 19 | Ingestion concepts, FastF1/Jolpica sources, Bronze schemas, quality & coverage, ingest how-tos, ops runbooks |
| **Transform** | 87 | Decomposition concepts, how-the-layer-works, the CI contract, 8 macro pages, and the **60-model auto-generated reference** |
| **Machine Learning** | 15 | Concepts, the pipeline, validation & leakage spine, the CI contract, and the auto-generated model card |
| **App** | 41 | Architecture + per-family feature docs: Ghost Car, lap decomposition, tyre & strategy, aero & conditions, drivers, constructors, the machine, data & validation |
| **Platform** | 8 | Getting started, architecture, operations, reliability/observability |

- **Auto-generated reference:** dbt models, macros, schemas, ML model card, and CLI — every reference page is **generated from compiled manifests, drift-gated in CI**.
- **Drift-gated facts:** per-tab `*_docs_facts.py` plus `docs_audit.py` / `app_docs_audit.py` reconcile every headline count and methodology link against source.

**Drift gate:** `python scripts/build_reference.py && git diff --exit-code` in
`docs-ci.yml`. If generated MDX diverges from source, CI fails. Reference docs
cannot go stale.

---

## 10. Quality & Testing (Defence in Depth)

| Layer | Tests | What they guard |
|---|---|---|
| **Transform (dbt)** | **443** | Additive identity (0.1 ms), uniqueness, referential integrity, accepted values, 29 singular physics tests |
| **Coefficient fitters (pytest)** | **42** | Kaplan-Meier survival, weight-penalty, constructor-car HDFE, and isotonic-degradation fits |
| **Machine Learning** | **28** | Leakage spine (5 guards), ONNX parity (`atol=1e-5`), output schema, beats-baseline, no hard-coded holdout |
| **Frontend (app)** | **310** | Rendering, routing, data-layer, WebAssembly ONNX inference |
| **Ingestion** | **53** | FastF1 integration, Jolpica client, data quality gates, schema fingerprint verification |
| **Total** | **876** | |

**Additional governance:**
- Coefficient freshness check — seeds older than 365 days trigger warnings
- Docs drift gate — generated reference must match compiled manifests
- `docs_facts.py` + `docs_audit.py` — reconcile headline counts across docs and flag staleness

---

## 11. Repository Scale

| Dimension | Count |
|---|---|
| Tracked files | **945** |
| Python | 79 `.py` (ingestion, coefficients, ML, scripts) |
| SQL | 98 `.sql` (dbt models, tests, macros) |
| TypeScript | **337** `.ts`/`.tsx` (161 `.tsx` + 176 `.ts`) |
| MDX | 190 (Mintlify docs) |
| ONNX artifacts | 25 (across the v1→v4 model lineage) |
| Public Parquet assets | 1,674 partition files |
| Knowledge graph | 9,405 nodes · 14,340 edges · 758 communities (graphify) |

---

## 12. Architecture & Stack

| Layer | Technology | Key Property |
|---|---|---|
| Ingestion | FastF1 + Jolpica → Hive-partitioned Parquet | Append-only Bronze, idempotent, schema-fingerprinted |
| Transform | dbt-core on DuckDB (60 models, 443 tests) | Seven-term physics decomposition with CI-enforced invariant |
| Coefficients | Kaplan-Meier, HDFE, isotonic regression, OLS | Survival analysis, econometric de-biasing, monotone fits |
| Machine Learning | XGBoost (quantile trio + classifier + regressor) → ONNX | Every model beats baseline; leakage-audited by `sqlglot` |
| Frontend | React + Vite + DuckDB-Wasm + ONNX Runtime Web | Sub-10 ms SQL, zero-server, browser-native ML inference |
| Hosting | Firebase Hosting + GCS Parquet CDN | Manifest-versioned, cache-busted, zero-downtime deploys |
| Docs | Mintlify (196 pages, 6 tabs, auto-generated reference) | Drift-gated in CI; cannot go stale |
| Validation | 614-line GO/NO-GO harness + Monte Carlo simulator | Bootstrap CIs, Spearman/Kendall, Brier calibration |

---

## 13. What Makes This Project Different

Most F1 dashboards tell you **who** is slow. This project tells you **why** — in seconds,
per lap, with honest uncertainty.

| # | Claim | How it's proven |
|---|---|---|
| 1 | **Attribution, not aggregation** | Every lap deconvolved into seven named, physical causes — not just raw averages |
| 2 | **Hard CI-enforced math invariant** | A physical conservation law tested to 0.1 ms on every lap in CI; violation = build failure |
| 3 | **Econometric car-driver de-biasing** | Two-way HDFE panel regression separates car quality from driver quality — solves the fundamental confound |
| 4 | **Survival analysis for censored data** | Kaplan-Meier handles the selection bias of teams pitting before the cliff — the same estimator used in clinical drug trials |
| 5 | **True client-side OLAP database** | DuckDB-Wasm executes real analytical SQL on static Parquet files locally in the browser — zero server |
| 6 | **Edge ML inference** | Five XGBoost models scored in WebAssembly client-side, with `atol=1e-5` parity proven against Python training |
| 7 | **Zero-server, infinite scalability** | The serverless architecture handles infinite traffic at $0 compute cost |
| 8 | **Counterfactuals with honest uncertainty** | Ghost Car propagates standard errors via Monte Carlo simulation to finish-order probabilities |
| 9 | **Leakage auditing in CI** | `sqlglot` parses compiled dbt SQL to check for forward-looking features before training |
| 10 | **5-step statistical validation gate** | Teammate-swap, team-change counterfactual, LORO backtest, pairwise calibration, MC consistency — all with bootstrap CIs |
| 11 | **Deterministic versioned data CDN** | Manifest-versioned Parquet loads cache-bust seamlessly on GCS |
| 12 | **Attributed findings with real numbers** | São Paulo 2021: strategy delivered 2.91 s of tyre advantage; Hamilton's driving delivered 1.60 s on the overtake lap |
| 13 | **876 automated tests** | Transform + coefficient fitters + ML + app + ingestion, with drift-gated docs on top |
| 14 | **Solo-built, end to end** | Ingestion → physics → survival analysis → ML → ONNX → React app → CDN → docs — one person |

---

## 14. Where These Numbers Come From (re-sweep cheatsheet)

Every figure above is swept from the live repo, not hand-maintained. To refresh, re-run
the commands below — the **authoritative source is always the compiled artifact**, not the
README or docs.

### Authoritative sources

| Stat | Source of truth | How to read it |
|---|---|---|
| dbt model / test / seed counts | `transform/target/manifest.json` | count nodes by `model.` / `test.` / `seed.` prefix |
| ML version, feature count, feature order | `ml/models/manifest.json` | `.input.n_features`, `.input.feature_order`, `.model_version` |
| ML headline metrics (eval/baseline per model) | `ml/models/model_card.json` | `['model_card']['models'][n]['eval_headline']` / `baseline_headline` |
| ML calibration & leakage probe | `ml/models/model_card.json` | `['model_card']['validation']['calibration']` / `leakage_probe` |
| Data coverage (seasons/races/laps) | `data/dev.duckdb` marts | the residuals + ghost marts |
| App routes & charts | `app/src/routes/` and `app/src/ui/charts/` | one dir per route; one file per chart primitive |

### Exact commands (copy-paste)

```bash
# dbt: models by layer + canonical test/seed counts from the COMPILED manifest
python3 -c "import json;m=json.load(open('transform/target/manifest.json'));n=m['nodes'];\
print('models',sum(k.startswith('model.') for k in n),\
'tests',sum(k.startswith('test.') for k in n),\
'seeds',sum(k.startswith('seed.') for k in n))"
find transform/models/staging      -name '*.sql' | wc -l   # 12
find transform/models/intermediate -name '*.sql' | wc -l   # 34
find transform/models/marts        -name '*.sql' | wc -l   # 10
find transform/models/reference    -name '*.sql' | wc -l   # 4
find transform/macros -name '*.sql' | wc -l                # 7 macros
find transform/tests  -name '*.sql' | wc -l                # 29 singular tests

# ML: feature count + version straight from the manifest the app & ONNX share
python3 -c "import json;m=json.load(open('ml/models/manifest.json'));\
print(m['model_version'], m['input']['n_features'], 'features')"
ls ml/models/*_v4.onnx                                      # 5 current ONNX models

# ML: headline metrics for all 5 models (eval / baseline / beats)
python3 -c "
import json; c=json.load(open('ml/models/model_card.json'))['model_card']
print(f\"{'model':40} {'metric':10} {'eval':>9} {'baseline':>9}\")
for m in c['models']:
    print(f\"{m['name']:40} {m['headline_metric']:10} {m['eval_headline']:9.4f} {m['baseline_headline']:9.4f}\")
"
# ML: calibration + leakage probe
python3 -c "
import json; v=json.load(open('ml/models/model_card.json'))['model_card']['validation']
c=v['calibration']; p=v['leakage_probe']
print('n',c['n'],'raw',round(c['raw_empirical_coverage'],3),'conformal',round(c['conformal_empirical_coverage'],3),'width',round(c['mean_interval_width'],3))
print('probe accuracy',round(p['accuracy'],3),'vs baseline',round(p['majority_class_accuracy'],3))
"

# App: routes (9 shipped have index.tsx, 3 coming-soon do not) + chart primitives
ls -d app/src/routes/*/                                     # 12 route dirs
find app/src/routes -maxdepth 2 -name index.tsx            # 9 shipped
ls app/src/ui/charts/*.tsx                                  # 8 chart primitives
find app/src -name '*.tsx' | wc -l && find app/src -name '*.ts' | wc -l  # 161 + 167 = 328

# Tests by layer (876 total)
python3 -c "import json;m=json.load(open('transform/target/manifest.json'));n=m['nodes'];\
print('dbt tests',sum(k.startswith('test.') for k in n))"
                                                           # dbt: 443
PYTHONPATH=transform ./.venv/bin/pytest transform/tasks/coefficients/tests/ --collect-only -q
                                                           # coeff fitters: 42
./.venv/bin/python -m pytest ml/tests --collect-only -q    # ML: 28
cd app && ./node_modules/.bin/vitest list | wc -l          # app vitest: 310
PYTHONPATH=. ./.venv/bin/pytest ingestion/tests/test_ingestion.py \
  ingestion/tests/test_jolpica.py --collect-only -q        # ingestion: 53

# Ingestion sources, scripts, docs
ls ingestion/src/*_client.py                               # FastF1 (api_client) + Jolpica
ls scripts/*.py | wc -l                                     # 26 analytics scripts
find docs -name '*.mdx' | wc -l && find docs -name '*.md' | wc -l   # 190 + 6

# Repo scale
git ls-files | wc -l                                       # 945 tracked files
git ls-files | sed 's/.*\.//' | sort | uniq -c | sort -rn  # by extension
find data -name '*.parquet' | wc -l                        # 1,674 public assets
```

### The graphify knowledge graph

A full structural graph of the codebase lives at `graphify-out/` (9,405 nodes · 14,340 edges ·
758 communities over 830 files). Use it for capability sweeps and "what connects to what" questions:

```bash
graphify query "what are the core analytical capabilities and models"   # BFS sweep
graphify update .                                                       # refresh (code-only = no LLM cost)
cat graphify-out/GRAPH_REPORT.md                                       # god nodes, communities, freshness
```

> **Freshness note:** the graph records the commit it was built from. If it's behind
> `git rev-parse HEAD`, run `graphify update .` — the figures in this doc always come from
> the live tree commands above, so they're current regardless.

### Reconciliation tip

If the README or a doc page disagrees with a number here, **trust the compiled manifest /
source tree**, then fix the doc. `scripts/docs_facts.py` reconciles headline counts across
docs and flags drift.
