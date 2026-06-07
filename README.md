# Off The Pace

**When a car is off the pace, why?**

Off The Pace decomposes every F1 lap into seven additive, physically-grounded components so lost time can be attributed to an exact, named cause rather than a vibe.

**[Docs at off-the-pace.onrender.com](https://off-the-pace.onrender.com)** · **[Repository Tour →](TOUR.md)**

---

## Three things to notice

### 1. The question, as the thesis

Most F1 analytics tells you *who* is slow. This project asks *why*. Each lap is decomposed into:

> `lap_time = baseline + tyre_deg + fuel_load + traffic + safety_car + weather + residual`

The residual is what remains after every measurable physical factor is removed. That is the driver signal, representing the part that actually belongs to the human.

### 2. A CI-enforced mathematical invariant

The seven terms sum to zero by construction. This isn't a stated property: it's tested on every lap in CI:

```sql
-- transform/macros/assert_additive_identity.sql
select count(*) from {{ model }}
where abs(pace_delta_s-(
  fuel_component_s + compound_component_s + rubber_component_s +
  ambient_component_s + constructor_component_s + dirty_air_tax_s +
  driver_skill_residual_s
)) > 0.0001
```

If it fails, the build fails. An enforced invariant is worth more than a claimed one.

### 3. Honest out-of-sample validation + honest limitations

Trained on 2018–2024. The 2025 season is held out as a reproducible out-of-sample validation against now-public OpenF1 data; you can run it yourself to get the same numbers. Paired with an explicit limitations section: no 2025 ingestion yet (so the ML holdout is time-series CV for now), no frontend yet.

---

## Choose your path

**I want to understand the idea →** [off-the-pace.onrender.com/understand/goal-and-approach](https://off-the-pace.onrender.com/understand/goal-and-approach)

**I want to run it →** `make setup && make dbt-dev` (see Quickstart below)

---

## Quickstart

Requires Python 3.11.

```bash
git clone https://github.com/justinclarke/off-the-pace
cd off-the-pace
make setup           # build venv + install deps
make dbt-dev         # build the transform layer (46 models)
make dbt-test        # run 339 tests including assert_additive_identity
```

No cloud credentials required. DuckDB runs locally at `data/dev.duckdb`.

---

## Project status

| Subsystem | State | Evidence |
|---|---|---|
| Ingestion (Bronze) | ✅ Built | `ingestion/src/`: FastF1 to Hive-partitioned Parquet |
| Transform (46 models, 339 tests) | ✅ Built | `transform/models/`: schema.yml and singular tests |
| Coefficients (KM tyre cliff) | ✅ Fitted | `transform/tasks/coefficients/`: seeds |
| Reference docs | ✅ Generated | `docs/docs/reference/` generated from dbt manifest |
| ML (5 XGBoost models, 27 tests) | ✅ Built | [`ml/`](ml/): degradation quantile trio + cliff classifier + stint-life; ONNX parity; auto-generated [model card](docs/docs/reference/ml/degradation-model-v1.mdx) |
| Frontend (React + DuckDB-Wasm) | ✅ Built | [`app/`](app/): platform complete; 35 tests passing; deployed to Firebase Hosting |
| Visualizations | ✅ Complete | Driver consistency, tyre degradation simulator, and more |
| Streaming (Microsoft Fabric) | ❌ Planned | Streaming Integration |

The engine is built and tested. The current focus is producing the first attributed finding: a concrete lap decomposition with numbers, not just the framework that produces them.

---

## Machine Learning

Five XGBoost models score every lap from the feature mart [`fct_cliff_prediction_features`](transform/models/marts/fct_cliff_prediction_features.sql):

- **Degradation quantile trio** (`p10` / `p50` / `p90`) next-lap pace loss with a calibrated interval (empirical coverage 0.80 at nominal 0.80).
- **Cliff classifier** laps-until-cliff bucket (`0_to_2` / `3_to_5` / `6_plus` / `none_in_stint`).
- **Stint-life regressor** remaining laps of usable life.

Every model **beats a strong per-cohort baseline** on the headline metric (season-grouped `TimeSeriesSplit`; the 2024 fold stands in as a holdout until 2025 ingests). Each booster round-trips to **ONNX within `atol=1e-5`** for in-browser scoring (browser application). The leakage spine no forward-looking features (a `sqlglot` audit of the compiled SQL), `driver_id`/`race_year` excluded (an adversarial probe recovers `race_year` at 0.9999, proving they would leak) is enforced by tests and CI.

Reproduce end-to-end (one venv, warehouse read-only, nothing written to `app/`):

```bash
make ml-setup        # install ml/requirements.txt
make ml-all          # features → tune → train → evaluate → predict → onnx → card → docs
make ml-test         # 27 tests: leakage spine, ONNX parity, output schema, beats-baseline
```

Full auto-generated **[model card](docs/docs/reference/ml/degradation-model-v1.mdx)** (metrics, baselines, calibration, dual feature importance, limitations) is built from `ml/model_card.yml`.

---

## Stack

| Layer | Tech |
|---|---|
| Ingestion | FastF1 + OpenF1 → Hive-partitioned Parquet |
| Transform | dbt-core (DuckDB local, 46 models, 339 tests) |
| ML | XGBoost (degradation quantile trio, cliff classifier, remaining life) → ONNX |
| Frontend | React + DuckDB-Wasm (sub-10ms queries, zero compute cost) |
| Hosting | Firebase Hosting (frontend) + Firebase Storage (data CDN) + Render (docs) |

## Repo layout

| Folder | Contents |
|---|---|
| [`ingestion/`](ingestion/) | FastF1 + OpenF1 pulls → Bronze Parquet |
| [`transform/`](transform/) | dbt project, from staging through feature marts |
| [`ml/`](ml/) | Machine learning layer: XGBoost models, ONNX export, model card |
| [`docs/`](docs/) | Docusaurus docs site |
| [`scripts/`](scripts/) | Reference doc generators, CI tooling |

---

---

## Documentation map

| Document | Purpose |
|---|---|
| **[README.md](README.md)** | *Start here* thesis, status, quickstart, stack |
| **[TOUR.md](TOUR.md)** | *Read next* guided walkthrough of every directory in lifecycle order |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | How to contribute; pipeline overview for new contributors |

---

Built by [Justin Clarke](https://justinclarke.github.io) · Licensed under AGPL-3.0
