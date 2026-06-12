**Reading time:** 5 min · **Audience:** Architect · **Status:** ✅ Current

---

# Architectural Decision Log (ADRs)

---

## ADR-001: DuckDB as the primary database engine
**Decision:** Use DuckDB (via dbt-duckdb) as the core transform and analytical engine for local development, CI/CD, and production parquet compilation.
**Rationale:** Low-overhead columnar engine, zero-setup, optimized execution, and direct integration with Parquet files without requiring active SQL database resources.
**Tradeoff:** Single-connection write limit, but fully sufficient for our batch transformation DAG.

## ADR-002: React + DuckDB-Wasm for Zero-Compute Client-Side Analytics
**Decision:** Run SQL queries directly in the user's browser using DuckDB-Wasm, querying Gold-layer Parquet files served from a CDN.
**Rationale:** Eliminates server runtime hosting costs, scales infinitely with client bandwidth, and executes complex analytics queries in <10ms.
**Tradeoff:** Initial payload load time includes downloading the WASM engine and the base data parquets (mitigated via background pre-warming).

## ADR-003: CDN Parquet Storage over Active Cloud Warehouses
**Decision:** Serve Gold-layer analytics outputs as compressed Parquet files directly from a CDN (Firebase Storage) rather than running an active cloud database server (such as Snowflake or Fabric).
**Rationale:** Dramatically reduces costs, simplifies infrastructure maintenance, and enables the zero-compute DuckDB-Wasm architecture to load and query files on-demand.
**Tradeoff:** Real-time write/update capabilities are not natively supported (handled by compiling the static database files via offline/CI batch builds).

## ADR-004: Local ML Pipeline with ONNX Client-Side Runtime
**Decision:** Train XGBoost models locally/in CI via standard Python pipelines and compile the trained models to `.onnx` files for direct browser-side evaluation.
**Rationale:** Avoids server-side ML hosting costs, secures data privacy, and enables instantaneous local stint-life and tyre cliff classification.
**Tradeoff:** Target model complexity is limited by browser memory constraints (XGBoost fits this constraint perfectly).

## ADR-005: Python replay simulator for Eventstream testing
**Decision:** Build `replay_simulator.py` to stream historical data to EventHub/Eventstream endpoints.
**Rationale:** Allows 24/7 integration testing and simulation of live race streams outside actual race weekends.
**Tradeoff:** Simulated lap interval (e.g., 90s) is a flat approximation of real-world timing flow.

## ADR-006: OLS regression for causal isolation
**Decision:** Use OLS with event dummy variables from `dim_events.csv`.
**Rationale:** Interpretable and sufficient for 22-race sample.
**Tradeoff:** Assumes linear degradation.

## ADR-007: XGBoost with TimeSeriesSplit
**Decision:** Use `TimeSeriesSplit` for model validation.
**Rationale:** Guarantees temporal integrity in seasonal data.
**Tradeoff:** Fewer validation folds than random CV.

## ADR-008: React + Tailwind CSS for the user dashboard
**Decision:** Implement the public-facing dashboard as a React application styled with Tailwind CSS instead of Streamlit.
**Rationale:** Provides professional visual design, deep layout customization, and enables smooth integration of DuckDB-Wasm and ONNX runtimes.
**Tradeoff:** Requires more complex development setup and boilerplate code than a simple Python-based Streamlit dashboard.

## ADR-009: Accept 2018 Rd1/Rd2 telemetry gap
**Decision:** Include all 20 races from 2018, but accept missing telemetry for Rd1/Rd2 (F1 didn't publish livetiming feed until later that season).
**Rationale:** Preserves full 168-race dataset for trend analysis; lap-time degradation signals are available as fallback; clean to document and test.
**Tradeoff:** Feature inconsistency for 2018 Rd1/Rd2 (laps-only vs. full telemetry in later races). ML layer handles this via conditional feature selection.
**Implementation:** `fct_lap_degradation` includes both `lap_time_delta` and `speed_delta` where available; models can learn which signal is stronger per race.

## ADR-010: CDN publish pipeline with version-stamped cache-busting
**Decision:** Promote the exported Gold-layer parquet + ONNX artefacts to the live CDN bucket (`gs://off-the-pace-cdn`) via a dedicated, idempotent script (`scripts/publish_cdn.sh`, `make app-publish`/`app-deploy`), and cache-bust every parquet URL with the manifest `version` hash (`?v=<version>`).
**Rationale:** The app reads all data from the CDN even in local dev (ADR-002/003), so `make app-data` alone never reaches the running app a publish step is mandatory. CDN parquet paths are not content-hashed, so a schema/data change reuses the same URL; the GCS public edge cache (`Cache-Control: public, max-age=3600`) then served stale generations to *all* clients regardless of browser, masking the new data for up to an hour. Stamping URLs with the no-cache manifest `version` gives each data revision a unique key that always misses the stale cache. The publish script uploads with no deletes (preserves bucket-only objects like `data/ml/`) and writes the manifest last so the version pointer never references unfinished uploads.
**Tradeoff:** A redundant `?v=` query param on every data request, and a manual publish step (not yet wired into CI). Models are exempt their filenames already carry a `_v1` version.
**Trigger:** The `is_self_scenario` binder error (2026-06-11): a rebuilt `fct_ghost_race_finish` mart was correct on disk and in the bucket object, but the public HTTP endpoint served a months-old cached generation with the pre-expansion schema.

---
