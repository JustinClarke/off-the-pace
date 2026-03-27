---
slug: /
sidebar_position: 1
title: Off The Pace
---

# Off The Pace

**When a car is off the pace, why?**

Off The Pace decomposes every F1 lap into seven additive, physically-grounded components so lost time can be attributed to an exact, named cause rather than a vibe.

> `lap_time = baseline + tyre_deg + fuel_load + traffic + safety_car + weather + residual`

The residual is what remains after every measurable physical factor is removed. That is the driver signal.

This identity is not claimed: it is **enforced in CI** on every lap. If the terms don't sum to zero, the build fails.

---

## Choose your path

### I want to understand the idea

Start with [Goal & Approach](./understand/goal-and-approach.md), which introduces the causal question, why it matters, and how decomposition answers it.

Then: [Seven-Term Identity](./understand/seven-term-identity.md) → [Methodology](./understand/methodology.md) → [Limitations](./understand/limitations.md)

### I want to understand the ML

The [Machine Learning](/machine-learning) section covers the five XGBoost models that predict the tyre cliff and next-lap degradation on top of the decomposition features, validation, the leakage spine and calibration.

### I want to run it

```bash
git clone https://github.com/justinclarke/off-the-pace
cd off-the-pace
make setup        # build venv + install deps
make dbt-dev      # build 46 models
make dbt-test     # run 339 tests
```

No cloud credentials required. DuckDB runs locally at `data/dev.duckdb`.

---

## Project status

| Subsystem | State |
|---|---|
| Ingestion (Bronze) | ✅ Built |
| Transform (46 models, 339 tests) | ✅ Built |
| Coefficients (KM tyre cliff) | ✅ Fitted |
| Reference docs | ✅ Generated |
| ML (5 XGBoost models) | ✅ Built |
| Frontend (React + DuckDB-Wasm) | ✅ Built |
| First attributed findings | ✅ Complete |

The engine is built and tested. The current milestone is producing the first attributed finding with real numbers.
