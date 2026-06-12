---
title: "Repository Tour"
description: "A guided walkthrough of the Off The Pace codebase."
---

# Off The Pace Repository Tour

> **One path through the whole repo.** Every section answers the question a reader naturally
> asks next. Each directory has its own README for depth; this file is the thread connecting
> them.

Start at [README.md](https://github.com/JustinClarke/off-the-pace/blob/main/README.md), then follow the lifecycle here.

---

## Stop 0 Entry: what is this project?

**Question answered:** *What does Off The Pace do, and how is the repo structured?*

| File | What it does |
|---|---|
| [README.md](https://github.com/JustinClarke/off-the-pace/blob/main/README.md) | Thesis, status table, quickstart, stack, repo layout |
| [.github/CONTRIBUTING.md](https://github.com/JustinClarke/off-the-pace/blob/main/.github/CONTRIBUTING.md) | How to contribute, how the pipeline hangs together |
| [Makefile](https://github.com/JustinClarke/off-the-pace/blob/main/Makefile) | One-command entry point for every subsystem (`make help`) |

After reading the README, continue down the data lifecycle. The project ingests raw F1
telemetry, transforms it into seven additive lap-time components, trains ML models on
those components, and exposes everything via a React browser application.

---

## Stop 1 Ingestion: where does the data come from?

**Question answered:** *How does raw F1 telemetry become structured Parquet files?*

| File | What it does |
|---|---|
| [`ingestion/src/ingest.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ingestion/src/ingest.py) | CLI entrypoint calls FastF1/OpenF1, writes Bronze Parquet |
| [`ingestion/src/api_client.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ingestion/src/api_client.py) | FastF1 and OpenF1 session wrappers |
| [`ingestion/src/data_quality.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ingestion/src/data_quality.py) | Row-count checks, null guards, coverage assertions |
| [`ingestion/schemas/`](https://github.com/JustinClarke/off-the-pace/tree/main/ingestion/schemas/) | JSON Schema contracts one per dataset (laps, weather, race_control, telemetry) |
| [`ingestion/tests/test_ingestion.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ingestion/tests/test_ingestion.py) | Offline tests against fixture Parquet (no network, less than 5 s) |

Coverage: 168 races × 4 datasets (2018–2024). Output lands in `data/bronze/`.

For depth → [ingestion/README.md](https://github.com/JustinClarke/off-the-pace/blob/main/ingestion/README.md)

---

## Stop 2 Data Lake: where does it land?

**Question answered:** *How is the raw data organised on disk, and what are the naming rules?*

| File | What it does |
|---|---|
| [`data/README.md`](https://github.com/JustinClarke/off-the-pace/blob/main/data/README.md) | Medallion layout, partition grammar, contracts, known issues |
| `data/bronze/[dataset]/season=YYYY/race=[slug]/` | Hive-partitioned Parquet append-only Bronze |
| `data/dev.duckdb` | Local DuckDB warehouse built by `make dbt-dev` (gitignored) |

**Partition grammar** (decode any path):
```
data/bronze/<dataset>/season=<YYYY>/race=<event-slug>/[session=<Q|R>]/<file>.parquet
```
- `<dataset>` ∈ `laps | weather | race_control | telemetry`
- `<event-slug>` is FastF1's `EventName` lowercased, spaces → hyphens (e.g. `bahrain-grand-prix`)
- `session` key only present for telemetry (which distinguishes Qualifying vs Race)
- 2018 Rd1/Rd2 telemetry missing FastF1 livetiming feed started mid-season

Bronze is never modified after write. All business logic lives in the dbt transform layer.

For depth → [data/README.md](https://github.com/JustinClarke/off-the-pace/blob/main/data/README.md)

---

## Stop 3 Transform: how is raw data turned into meaning?

**Question answered:** *How does a raw lap become a seven-component decomposition?*

| File | What it does |
|---|---|
| [`transform/models/staging/`](https://github.com/JustinClarke/off-the-pace/tree/main/transform/models/staging/) | Clean and type Bronze → `stg_laps`, `stg_weather`, `stg_telemetry`, `stg_race_control` |
| [`transform/models/reference/`](https://github.com/JustinClarke/off-the-pace/tree/main/transform/models/reference/) | Slowly-changing reference data: circuits, constructors, driver mapping |
| [`transform/models/intermediate/`](https://github.com/JustinClarke/off-the-pace/tree/main/transform/models/intermediate/) | Physics: fuel load, tyre compound cliff, dirty-air tax, air density, residual decomposition |
| [`transform/models/marts/`](https://github.com/JustinClarke/off-the-pace/tree/main/transform/models/marts/) | Feature marts consumed by ML and app: `fct_lap_residuals`, `fct_cliff_prediction_features`, `fct_ghost_car_pace` |
| [`transform/macros/assert_additive_identity.sql`](https://github.com/JustinClarke/off-the-pace/blob/main/transform/macros/assert_additive_identity.sql) | The CI-enforced invariant: all seven components must sum to zero |
| [`transform/seeds/`](https://github.com/JustinClarke/off-the-pace/tree/main/transform/seeds/) | Hand-fitted parameters: `circuit_reference.csv`, `compound_cliff_params.csv` |
| [`transform/tasks/coefficients/`](https://github.com/JustinClarke/off-the-pace/tree/main/transform/tasks/coefficients/) | Python fitters that produce the seed CSVs |
| [`transform/tests/`](https://github.com/JustinClarke/off-the-pace/tree/main/transform/tests/) | 339 tests schema, singular, `assert_*` invariants |

The mathematical identity that the whole project rests on:
```
lap_time = baseline + tyre_deg + fuel_load + traffic + safety_car + weather + residual
→  pace_delta_s = fuel_component_s + compound_component_s + rubber_component_s
                + ambient_component_s + constructor_component_s + dirty_air_tax_s
                + driver_skill_residual_s
```
If any lap violates this by more than 0.0001 s, `make dbt-test` fails.

For depth → [transform/README.md](https://github.com/JustinClarke/off-the-pace/blob/main/transform/README.md)

---

## Stop 4 ML: what predicts the future from those features?

**Question answered:** *How does Off The Pace turn historical lap data into forward-looking predictions?*

| File | What it does |
|---|---|
| [`ml/src/features.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ml/src/features.py) | Feature extraction from `fct_cliff_prediction_features`; leakage audit |
| [`ml/src/train.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ml/src/train.py) | XGBoost training with season-grouped `TimeSeriesSplit` |
| [`ml/src/tune.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ml/src/tune.py) | Optuna hyperparameter search |
| [`ml/src/evaluate.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ml/src/evaluate.py) | Baseline comparisons, calibration, feature importance |
| [`ml/src/export_onnx.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ml/src/export_onnx.py) | `.bst` → `.onnx` with `atol=1e-5` parity gate |
| [`ml/src/card.py`](https://github.com/JustinClarke/off-the-pace/blob/main/ml/src/card.py) | Assembles `model_card.yml` / `model_card.json` |
| [`ml/model_card.yml`](https://github.com/JustinClarke/off-the-pace/blob/main/ml/model_card.yml) | Source of truth for the auto-generated model card MDX |

Five production models (each as `.bst` + `.onnx`):
- **Degradation quantile trio** (`p10`/`p50`/`p90`) calibrated next-lap pace-loss interval
- **Cliff classifier** laps-until-cliff bucket
- **Stint-life regressor** remaining usable laps

All five beat a strong per-cohort baseline; all five pass ONNX parity. The leakage spine (no
forward-looking features, no `driver_id`/`race_year`) is enforced by `ml/tests/`.

For depth → [ml/README.md](https://github.com/JustinClarke/off-the-pace/blob/main/ml/README.md)

---

## Stop 5 App: how does a human see it?

**Question answered:** *How is the data warehouse surfaced in the browser zero backend?*

The React + DuckDB-Wasm frontend is complete and deployed. The platform includes a data export pipeline, ONNX inference layer for live ML scoring, reusable chart components, season/race/driver filters, and navigation across 13 pillars. Live visualizations include driver consistency analysis and tyre degradation simulation. The architecture: Firebase Storage (parquet CDN) → DuckDB-Wasm (browser WebAssembly) → hooks → route components → UI. Zero compute server. Sub-10ms queries on the gold mart. Deployed to Firebase Hosting at off-the-pace.web.app; CI deploys on push to main.

For depth → [app/README.md](https://github.com/JustinClarke/off-the-pace/blob/main/app/README.md)

---

## Stop 5b Landing: the portfolio storefront

**Question answered:** *How is the project presented to hiring managers and non-engineers?*

The portfolio landing page lives in a **separate repository**:
[`justinclarke.github.io`](https://github.com/JustinClarke/justinclarke.github.io) at `src/pages/off-the-pace/`.
It deploys at the root URL; this `off-the-pace` repo is the data and analysis engine it describes.

---

## Stop 6 Docs: how is all of this explained and proven?

**Question answered:** *How does the Mintlify site relate to the source files?*

| File | What it does |
|---|---|
| [docs/decomposition/](decomposition/seven-term-identity.mdx) | Goal & approach, lap decomposition physics, limitations |
| [docs/ml/](ml/overview.mdx) | 8-page ML narrative (features, models, validation, ONNX) |
| [docs/findings/](findings/overview.mdx) | Real race decompositions proving the methodology on actual data |
| [docs/reference/](reference/fct-lap-residuals.mdx) | **Auto-generated** models, macros, schemas, CLI, model card MDX. Edit the source, not these. |

**Attributed Findings** sit at the intersection of methodology and evidence. The [São Paulo 2021 case study](findings/sao-paulo-2021.mdx) applies the 7-term decomposition to Hamilton vs Verstappen's final stint and finds a precise answer to a question commentary could not: how much of the win was strategy (2.91 s structural tyre advantage) versus driving skill (1.59 s on the overtake lap). It is the primary demonstration that the physics layer produces meaningful, verifiable outputs on real race data. The React application will expose this interactively across all 168 races.

The reference section is generated by `scripts/build_reference.py`. CI fails if generated files
drift from their sources (`git diff --exit-code`).

For depth → [docs/README.md](README.md)

---

## Stop 6b Scripts: how are the reference docs kept true?

**Question answered:** *What generates the auto-reference docs, and how does CI catch drift?*

| File | What it does |
|---|---|
| [`scripts/build_reference.py`](https://github.com/JustinClarke/off-the-pace/blob/main/scripts/build_reference.py) | Orchestrates all five generators; used by `make docs-reference` and CI |
| [`scripts/gen_dbt_reference.py`](https://github.com/JustinClarke/off-the-pace/blob/main/scripts/gen_dbt_reference.py) | Reads dbt `manifest.json` → model/macro MDX pages |
| [`scripts/gen_schema_reference.py`](https://github.com/JustinClarke/off-the-pace/blob/main/scripts/gen_schema_reference.py) | Reads `ingestion/schemas/*.json` → schema MDX |
| [`scripts/gen_ml_reference.py`](https://github.com/JustinClarke/off-the-pace/blob/main/scripts/gen_ml_reference.py) | Reads `ml/model_card.yml` → model card MDX |
| [`scripts/gen_cli_reference.py`](https://github.com/JustinClarke/off-the-pace/blob/main/scripts/gen_cli_reference.py) | Reads Python docstrings → CLI reference MDX |
| [`scripts/mdx_utils.py`](https://github.com/JustinClarke/off-the-pace/blob/main/scripts/mdx_utils.py) | Shared MDX formatting helpers |

The drift check: `python scripts/build_reference.py && git diff --exit-code` in `docs-ci.yml`.
If the generated MDX differs from what's committed, CI fails you can't have stale reference docs.

For depth → [scripts/README.md](https://github.com/JustinClarke/off-the-pace/blob/main/scripts/README.md)

---

## Stop 7 Build & Governance: how is it all wired together?

**Question answered:** *How do you run, test, and govern the whole system from one place?*

| File | What it does |
|---|---|
| [`Makefile`](https://github.com/JustinClarke/off-the-pace/blob/main/Makefile) | One-command entry for every subsystem (`make setup`, `make dbt-*`, `make ml-*`, `make docs-*`) |
| [`.github/workflows/dbt-ci.yml`](https://github.com/JustinClarke/off-the-pace/blob/main/.github/workflows/dbt-ci.yml) | Build all 46 models + run 339 tests + assert additive identity |
| [`.github/workflows/docs-ci.yml`](https://github.com/JustinClarke/off-the-pace/blob/main/.github/workflows/docs-ci.yml) | Build Mintlify + reference drift check |
| [`.github/workflows/ml-ci.yml`](https://github.com/JustinClarke/off-the-pace/blob/main/.github/workflows/ml-ci.yml) | 27-test spine: leakage, ONNX parity, output schema, beats-baseline |
| [`.github/adr/DECISIONS.md`](https://github.com/JustinClarke/off-the-pace/blob/main/.github/adr/DECISIONS.md) | Architecture decision records |
| [`.github/CONTRIBUTING.md`](https://github.com/JustinClarke/off-the-pace/blob/main/.github/CONTRIBUTING.md) | Canonical contributor guide |

For depth → see `.github/CONTRIBUTING.md` and the workflow files themselves.

---

## Stop 7b Agents: operational helpers

**Question answered:** *What are the automated helpers that operate on the repo?*

A lineage agent (natural-language → dbt model lineage) and a status agent (pipeline health
reporting) are architected and documented but deferred to future integration. They are kept
in a local working tree, not published in this repo.

---

## Stop 8 Internal: where is the thinking recorded?

**Question answered:** *What are the planning documents, and which are read-me-first vs internal?*

Internal planning feature lists, route specs, documentation plans, roadmap snapshots, and
ADR-style notes is kept in a local working tree, not published in this repo. The code and
the docs site are the authoritative sources of current state.

---

## The complete chain

```
README.md → docs/repo-tour.md (here)
  → ingestion/   (FastF1 → Bronze Parquet)
  → data/        (Medallion lake, partition grammar)
  → transform/   (dbt: staging → intermediate physics → marts)
  → ml/          (XGBoost trio + cliff + stint-life → ONNX)
  → app/         (React + DuckDB-Wasm local / not published)
  → landing/     (Portfolio storefront separate repo: justinclarke.github.io)
  → docs/        (Mintlify: decomposition + ML + findings + auto-reference)
  → scripts/     (generators + drift check)
  → Makefile + .github/  (build, test, govern)
  → agents/      (lineage + status, deferred local / not published)
  → _roadmap/    (internal planning local / not published)
```

Every directory has a `README.md`. Every authored file has a header. Every generated,
data-partition, and vendored file is explained by a class banner never described per-file.
