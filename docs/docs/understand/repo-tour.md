---
sidebar_position: 5
title: Repository Tour
---

# Repository Tour

> One path through the whole repository. Start here if you want to understand how every
> piece connects not just what it does, but why it exists and where it fits.

The tour follows the **data lifecycle**: raw telemetry arrives, is structured, transformed
into physics-grounded components, scored by ML models, surfaced in the browser, and documented.
Each stop answers the question a reader naturally asks next.

The file-system-anchored version of this tour lives at
[`TOUR.md`](https://github.com/justinclarke/off-the-pace/blob/main/TOUR.md) in the repo root
with clickable links to every file mentioned.

---

## Stop 1 Ingestion: where does the data come from?

Raw F1 telemetry enters the system through the **ingestion layer**. There are no databases to
set up, no credentials required FastF1 handles the F1 timing feed and OpenF1 provides a
public REST API.

`ingestion/src/ingest.py` is the CLI entry point. You call it with `--season`, `--round`, and
`--session` flags; it fetches the relevant session, validates it against a JSON Schema contract
in `ingestion/schemas/`, and writes Hive-partitioned Parquet to `data/bronze/`.

**Why Hive partitioning?** It makes every downstream tool dbt, DuckDB, pandas able to
predicate-push on `season=`, `race=`, or `session=` without scanning the whole dataset. A
query for a single race reads ~200 MB, not ~180 GB.

For the full architecture and coverage table, see
[ingestion docs](/reference/schemas) and the
[ingestion README](https://github.com/justinclarke/off-the-pace/blob/main/ingestion/README.md).

---

## Stop 2 Data Lake: where does it land?

The output of ingestion lives in `data/bronze/` following a strict **partition grammar**:

```
data/bronze/<dataset>/season=<YYYY>/race=<event-slug>/[session=<Q|R>]/<file>.parquet
```

- `<dataset>` is one of `laps`, `weather`, `race_control`, `telemetry`
- `<event-slug>` is the FastF1 event name, lowercased, spaces replaced by hyphens
- `session=` only appears in the telemetry dataset, which distinguishes Qualifying from Race
- 2018 Rd1/Rd2 telemetry is missing-FastF1's livetiming feed started mid-season

Bronze is **append-only**. Nothing in the transform layer ever writes back to it. This
separation means the raw data can be audited independently of any business logic.

---

## Stop 3 Transform: how is raw data turned into meaning?

The transform layer is a **dbt project running on DuckDB**. It converts raw Parquet into the
seven additive components that are the project's core claim.

The four dbt layers, in order:

| Layer | What it does |
|---|---|
| **Staging** | Casts, renames, and cleans Bronze → typed, named columns |
| **Reference** | Slowly-changing lookups: circuits, constructor history, driver mapping |
| **Intermediate** | Physics: fuel-load correction, compound-cliff KM curve, dirty-air tax, ambient state, residual decomposition |
| **Marts** | Gold feature tables: `fct_lap_residuals`, `fct_cliff_prediction_features`, `fct_ghost_car_pace` |

The invariant that ties all of it together tested on every lap in CI:

```sql
pace_delta_s = fuel_component_s + compound_component_s + rubber_component_s
             + ambient_component_s + constructor_component_s + dirty_air_tax_s
             + driver_skill_residual_s
```

If any lap violates this by more than 0.0001 s, the build fails. This is the CI-enforced
mathematical identity described in the [seven-term identity](seven-term-identity.md) page.

The dbt project runs 339 tests schema tests (not null, accepted values, relationships)
plus singular `assert_*` tests that encode domain-specific invariants. For the full model map
and layer contracts, see [transform/README.md](https://github.com/justinclarke/off-the-pace/blob/main/transform/README.md).

---

## Stop 4 Machine Learning: what predicts the future?

Five XGBoost models are trained on `fct_cliff_prediction_features`, the gold lap-grain mart.

| Model | Predicts |
|---|---|
| `degradation_regressor_p10/p50/p90_v1` | Next-lap fuel-corrected pace loss with calibrated interval |
| `cliff_classifier_v1` | Laps-until-cliff bucket: 0–2, 3–5, 6+, or none |
| `stint_life_regressor_v1` | Remaining laps of usable tyre life |

**Why five models instead of one?** The quantile trio gives a calibrated interval, not just a
point estimate. Empirical coverage at the 0.80 nominal level sits at 0.80 the interval
means what it says. The cliff classifier and stint-life regressor answer a different question:
*when*, not *how much*.

Every model round-trips to ONNX within `atol=1e-5`. This is the export format that the app
will use for **in-browser scoring** no server required.

The leakage spine is CI-enforced: no forward-looking features, no `driver_id` or `race_year`
in the feature matrix. An adversarial probe that recovers `race_year` at 0.9999 precision
proves these columns would have leaked, which is why they're excluded.

Full narrative: [machine-learning section](/machine-learning). Full build record: `ml/BUILD_LOG.md`.

---

## Stop 5 App: how does a human see it?

The React + DuckDB-Wasm frontend is complete and live at [off-the-pace.web.app](https://off-the-pace.web.app).

The architecture is unusual: there is no compute server. The browser fetches gold Parquet
files from Firebase Storage, loads them into DuckDB-Wasm (WebAssembly), and runs SQL queries
in-browser. Sub-10ms queries on the gold mart, zero server cost. Deployed to Firebase Hosting
via GitHub Actions CI on every push to main.

Nine content pillars are planned: Ghost Car, Lap Decomposition, Tyre Strategy, Aerodynamics,
Drivers, Constructors, Deep Dives, Query Lab, and ML live prediction with the ONNX models.

---

## Stop 6 Docs: how is all of this explained and proven?

The Docusaurus site (`docs/`) organises explanation into four sections:

| Section | Purpose |
|---|---|
| `understand/` | Goal, approach, the seven-term identity, methodology, limitations |
| `learn-dbt/` | 13-chapter tutorial: from staging through marts, hands-on |
| `machine-learning/` | 8-page narrative: features, models, validation, ONNX export |
| `reference/` | **Auto-generated** from source models, macros, schemas, CLI, model card |

The reference section is generated by `scripts/build_reference.py`. The CI drift check ensures
it never lags its sources: if `git diff --exit-code` is non-empty after generation, the build
fails. Edit the dbt YAML or Python docstrings, not the MDX.

---

## Stop 7 Build & Governance

Three CI pipelines gate every merge:

| Pipeline | What it checks |
|---|---|
| `dbt-ci` | Build all 46 models + run 339 tests + assert additive identity |
| `docs-ci` | Build Docusaurus + reference drift check |
| `ml-ci` | 27-test spine: leakage, ONNX parity, output schema, beats-baseline |

The `Makefile` mirrors CI locally every `make` target matches what CI runs. If it passes
locally, it passes in CI. Architecture decisions are recorded in `.github/adr/DECISIONS.md`.

---

## The complete chain

```
ingestion/   (FastF1 → Bronze Parquet)
  ↓
data/        (Medallion lake, Hive partitions)
  ↓
transform/   (dbt: staging → intermediate physics → marts)
  ↓
ml/          (XGBoost quantile trio + cliff + stint-life → ONNX)
  ↓
app/         (React + DuckDB-Wasm-local / not published)
landing/     (Portfolio storefront-separate repo: justinclarke.github.io)
  ↓
docs/        (this site: understand + learn-dbt + ML narrative + auto-reference)
scripts/     (generators + drift check)
  ↓
Makefile + .github/   (build, test, govern)
```

Every directory in the repo has a `README.md`. Every authored file has a header. Every
generated, data-partition, or vendored file is covered by a class banner never described
per-file.
