**Reading time:** 5 min · **Audience:** Architect · **Status:** ✅ Current

---

# Architectural Decision Log (ADRs)

---

## ADR-001: DuckDB as local dev environment only
**Date:** Day 1 / Week 1
**Decision:** DuckDB retained for local unit testing and fast iteration.
**Rationale:** Zero-setup columnar engine, M1 ARM-optimised.
**Tradeoff:** Local and production environments differ. Mitigated by dual dbt profiles.

## ADR-002: dbt dual-profile strategy
**Date:** Day 2 / Week 1
**Decision:** Use `dbt-fabric` for production and `dbt-duckdb` for local development.
**Rationale:** Environment-agnostic business logic.
**Tradeoff:** Developer must be explicit about target (`--target fabric`).

## ADR-003: Microsoft Fabric Lakehouse over Snowflake
**Date:** Day 2 / Week 1
**Decision:** Fabric Lakehouse (OneLake) as primary storage.
**Rationale:** Dominant UAE enterprise stack. DP-700 exam alignment. Single platform for ML/Streaming.
**Tradeoff:** Free trial limits and cold start latency.

## ADR-004: Fabric Notebooks for ML training
**Date:** Day 2 / Week 1
**Decision:** XGBoost trained in Fabric Notebooks.
**Rationale:** Eliminates data movement. Model artifact stored in OneLake `/models/`.
**Tradeoff:** Spark overhead for small datasets.

## ADR-005: Python replay simulator as Eventstream source
**Date:** Day 2 / Week 1
**Decision:** Build `replay_simulator.py` to stream historical data.
**Rationale:** Allows 24/7 testing outside race weekends.
**Tradeoff:** Simulated lap interval (90s) is a flat approximation.

## ADR-006: OLS regression for causal isolation
**Date:** Day 2 / Week 1
**Decision:** Use OLS with event dummy variables from `dim_events.csv`.
**Rationale:** Interpretable and sufficient for 22-race sample.
**Tradeoff:** Assumes linear degradation.

## ADR-007: XGBoost with TimeSeriesSplit
**Date:** Day 2 / Week 1
**Decision:** Use `TimeSeriesSplit` for model validation.
**Rationale:** Guarantees temporal integrity in seasonal data.
**Tradeoff:** Fewer validation folds than random CV.

## ADR-008: Streamlit for public surface
**Date:** Day 2 / Week 1
**Decision:** Use Streamlit for the dashboard.
**Rationale:** Python-native analytics engineering signal.
**Tradeoff:** Less customisable than a full React frontend.

## ADR-009: Accept 2018 Rd1/Rd2 telemetry gap
**Date:** 2026-05-21
**Decision:** Include all 20 races from 2018, but accept missing telemetry for Rd1/Rd2 (F1 didn't publish livetiming feed until later that season).
**Rationale:** Preserves full 168-race dataset for trend analysis; lap-time degradation signals are available as fallback; clean to document and test.
**Tradeoff:** Feature inconsistency for 2018 Rd1/Rd2 (laps-only vs. full telemetry in later races). ML layer handles this via conditional feature selection.
**Implementation:** `fct_lap_degradation` includes both `lap_time_delta` and `speed_delta` where available; models can learn which signal is stronger per race.

---
