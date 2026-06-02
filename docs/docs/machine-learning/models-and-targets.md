---
sidebar_position: 4
title: Models & targets
---

# Models & targets

Five XGBoost models, three target families, one shared feature matrix. Every model is tuned with Optuna and refit on all training data, and every one **beats a strong per-cohort baseline** on its headline metric. The exhaustive numbers hyperparameters, per-cohort breakdowns live in the auto-generated [model card](/reference/ml/degradation-model-v1); this page is the narrative.

---

## Headline results (evaluation season 2024)

| Model | Objective | Metric | CV | Eval | Baseline | Beats |
|---|---|---|---|---|---|---|
| `degradation_regressor_p10` | `reg:quantileerror` α=0.1 | pinball ↓ | 0.0799 | **0.0781** | 0.1276 | ✅ |
| `degradation_regressor_p50` | `reg:quantileerror` α=0.5 | pinball ↓ | 0.1919 | **0.1896** | 0.2247 | ✅ |
| `degradation_regressor_p90` | `reg:quantileerror` α=0.9 | pinball ↓ | 0.1316 | **0.1283** | 0.1438 | ✅ |
| `cliff_classifier` | `multi:softprob` | macro-F1 ↑ | 0.3655 | **0.3679** | 0.1835 | ✅ |
| `stint_life_regressor` | `reg:squarederror` | RMSE ↓ | 7.198 | **7.728** | 8.085 | ✅ |

*CV is the season-grouped `TimeSeriesSplit` mean; Eval is the final fold (2024) standing in as a holdout until 2025 ingests. See [Validation](/machine-learning/validation-and-leakage).*

## The degradation quantile trio

The three regressors share the pinball (quantile) loss but target different quantiles of `next_lap_degradation_jump_s`:

$$
\mathcal{L}_\alpha(y, \hat{y}) = \max\big(\alpha (y \hat{y}),\ (\alpha 1)(y \hat{y})\big)
$$

- **p50** is the median forecast-the best single guess at next-lap pace loss.
- **p10 / p90** bound it. Together they form an 80% prediction interval that is [calibrated to actually cover 80%](/machine-learning/calibration-and-importance).

`predict.py` row-sorts the trio so the quantiles never cross (observed crossing: **0.00%** of laps on the tuned v1 models).

Each regressor's baseline is the honest naive answer in the same `(compound, circuit, age-bucket)` cells: the cell **group-mean** for p50, the empirical **10th/90th percentile** for p10/p90. Beating a per-cell empirical percentile is a real bar it means the model adds signal beyond "what usually happens here."

## The cliff classifier

A 4-class model over `laps_until_cliff_class` (`0_to_2` / `3_to_5` / `6_plus` / `none_in_stint`), trained with balanced class weights. Its **macro-F1 of 0.368 nearly doubles** the only honest naive baseline the majority-class prior at 0.184.

This is, deliberately, the section where the project is most candid: macro-F1 ≈ 0.37 on 4-class cliff timing is **modest in absolute terms**. It decisively beats chance, the balanced weighting earns its keep on the minority imminent-cliff windows, and the 100 most-confident misses are exported to `holdout_biggest_misses.parquet` for inspection but absolute skill on the rare cliff windows is the headline weakness, surfaced rather than hidden. See [Limitations](/machine-learning/limitations-and-roadmap).

## The stint-life regressor

Predicts `remaining_stint_life_laps` (clipped ≥ 0) with squared-error loss. Its baseline is **knowingly near-oracle**: `(stint_length_laps − lap_in_stint) / 2`, which uses the true stint length the model is forbidden to see. The model still wins **overall** (RMSE 7.73 vs 8.08) and where it loses per-cohort (mostly specific circuits like Australia and Japan), those losses are recorded, never dropped.

## Tuning & refit

Each model is tuned by `tune.py` with Optuna (`TPESampler` + `MedianPruner`, seeded), a 9-dimensional search space, and per-fold pruning. The study is persisted to `ml/models/optuna_studies/<target>_v1.db`; the best params are written to `<target>_best_params.json`; then the model is **refit on the full training data** and saved as `<target>_v1.bst`.

> **Honest caveat:** the shipped v1 params come from a *reduced* session tuning budget (15 trials / 3 folds / 30k-row search subsample the final refit always uses all rows). The canonical `make ml-tune` (50 trials / 5 folds / full data) only improves params, with **no code change**, and should precede any production blessing. The beats-baseline gate holds regardless.
