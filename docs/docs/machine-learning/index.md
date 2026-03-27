---
slug: /machine-learning
sidebar_position: 1
title: Machine Learning
---

# The Machine Layer

The [seven-term decomposition](/understand/seven-term-identity) explains *where* a lap's time went. The machine layer asks the next question: *what happens next?* It learns five XGBoost models on top of the decomposed lap data to predict tyre behaviour a lap and a stint ahead.

> Built across 7 milestones: foundation + transform fixes → schema + leakage audit → ONNX parity spike → predictions → tuning + refits → evaluation + baselines → model cards/docs/CI → determinism proof. Five models, every one beating a strong per-cohort baseline. Full numbers live in the auto-generated [Tyre Degradation Predictors (v1)](/reference/ml/degradation-model-v1) model card.

---

## Why a machine layer at all

The statistical layer already estimates a tyre cliff per `(circuit, compound, season)` with [Kaplan-Meier survival analysis](/understand/methodology). That is a *population* answer: when does the average Soft at Bahrain fall off? It cannot say whether *this* stint, in *these* conditions, with *this* thermal history, is about to drop because the cliff is not a fixed lap number. It moves with track temperature, dirty-air exposure, push history, fuel load and compound generation.

The machine layer turns the population prior into a per-lap prediction. It consumes the same physics features the decomposition produces and outputs:

- **how much pace** the next lap will lose to degradation (with a calibrated uncertainty band),
- **how many laps until the cliff**, and
- **how much usable life** the stint has left.

## The five models at a glance

| Model | Predicts | Kind | Headline metric (eval 2024) |
|---|---|---|---|
| `degradation_regressor_p10` | next-lap pace loss optimistic bound | quantile (α=0.1) | pinball **0.078** vs 0.128 baseline |
| `degradation_regressor_p50` | next-lap pace loss median | quantile (α=0.5) | pinball **0.190** vs 0.225 baseline |
| `degradation_regressor_p90` | next-lap pace loss pessimistic bound | quantile (α=0.9) | pinball **0.128** vs 0.144 baseline |
| `cliff_classifier` | laps-until-cliff bucket | 4-class | macro-F1 **0.368** vs 0.184 baseline |
| `stint_life_regressor` | remaining stint life (laps) | regression | RMSE **7.73** vs 8.08 baseline |

The three quantile regressors form a **calibrated interval**: `[p10, p90]` covers the true next-lap degradation 80% of the time, at a nominal 80% (see [Calibration & importance](/machine-learning/calibration-and-importance)). All five beat their baseline globally proven by a test, not a claim ([Validation & the leakage spine](/machine-learning/validation-and-leakage)).

## How to read this section

1. **[The cliff problem](/machine-learning/the-cliff-problem)** why per-stint prediction needs ML, and what the targets mean.
2. **[The feature pipeline](/machine-learning/feature-pipeline)** the 38 features in 9 physics groups, sourced from [`fct_cliff_prediction_features`](/reference/models/fct/fct_cliff_prediction_features).
3. **[Models & targets](/machine-learning/models-and-targets)** each model's objective, tuning and headline result.
4. **[Validation & the leakage spine](/machine-learning/validation-and-leakage)** season-grouped `TimeSeriesSplit`, the 2025 holdout policy, and the adversarial leakage probe.
5. **[Calibration & importance](/machine-learning/calibration-and-importance)** conformal coverage and SHAP-vs-permutation feature importance.
6. **[Reproducibility & deployment](/machine-learning/reproducibility-and-deployment)** determinism proof and ONNX export for in-browser scoring.
7. **[Limitations & roadmap](/machine-learning/limitations-and-roadmap)** what the models cannot do yet, honestly.

## Reproduce it

```bash
make ml-setup        # install ml/requirements.txt into ./.venv
make ml-all          # features → tune → train → evaluate → predict → onnx → card → docs
make ml-test         # 27 tests: leakage spine, ONNX parity, output schema, beats-baseline
```

The machine layer reads the warehouse **read-only** and never writes to `app/`. See [`ml/README.md`](https://github.com/justinclarke/off-the-pace/tree/main/ml) and `ml/BUILD_LOG.md` for the full build record.
