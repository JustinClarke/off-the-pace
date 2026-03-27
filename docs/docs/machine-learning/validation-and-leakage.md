---
sidebar_position: 5
title: Validation & the leakage spine
---

# Validation & the leakage spine

Forward-looking targets make leakage the defining risk of the machine layer. The defence is a **leakage spine** a set of guards, baked into tests and CI, that prove the model never sees the future or the answer. This page covers how the models are validated and how that spine is enforced.

---

## Season-grouped time-series validation

Tyre data is a time series, so a random train/test split would let the model train on 2024 to predict 2022 a leak. Instead, validation uses a **season-grouped `TimeSeriesSplit`** (expanding window, 5 splits): whole seasons move together, and each fold validates on the season(s) *after* the ones it trained on. The final fold trains on 2018–2023 and validates on **2024**.

This connects directly to the project's [out-of-sample philosophy](/understand/out-of-sample-validation): you never score yourself on data you could have peeked at.

## The 2025 holdout policy

The holdout season is **data-derived**, not hard-coded: `HOLDOUT_SEASON = MAX(race_year) + 1`. Today that resolves to **2025, which has no rows yet**. So the models train on all ingested seasons (2018–2024) and selection rests on the cross-validation above.

The evaluation **headline is reported on the final CV fold (2024)** the most recent, holdout-shaped unseen season. The moment 2025 data ingests, `_evaluation_split` detects a populated holdout and switches to a true out-of-sample reveal **with zero code change**. There is no literal `2025` anywhere in `ml/src` a test (`test_no_hardcoded_holdout`) enforces it.

## The leakage spine five guards

| Guard | What it proves | Where |
|---|---|---|
| **No leaked columns** | targets, driver-skill signals and season-identifiers never enter `X` | `schema.EXCLUDED_LEAKAGE_COLUMNS` + `assert_no_leakage_columns.sql` |
| **No forward-looking features** | a `sqlglot` audit walks the compiled mart + ancestors and rejects any `LEAD` / `FOLLOWING` window | `features.py` audit + `test_no_forward_looking_features` |
| **Holdout purity** | no holdout-season row appears in any training fold | `test_holdout_purity` |
| **No hard-coded holdout** | the split is `MAX+1`-derived, not a literal year | `test_no_hardcoded_holdout` |
| **Bounded / non-null targets** | degradation ∈ [−10, 10]; no NULL-target rows train | `test_target_bounded`, `test_no_null_targets_in_training` |

These are part of the **27-test** `ml/tests` suite (12 spine + 5 ONNX parity + 3 predict + 7 evaluate) and run in the `ml-ci.yml` workflow.

## The adversarial leakage probe

The two most consequential exclusions `driver_id` and `race_year` are justified by **demonstration, not assertion**. A throwaway XGBoost model is trained to recover `race_year` from the *remaining* features:

- it succeeds at **0.9999 accuracy** versus a 0.169 majority-class baseline (a lift of 0.83).

That is the point: constructor identities and compound generations carry such a strong residual temporal signal that `race_year` is almost perfectly recoverable so including it would be a backdoor to the season, and through it to outcomes the model should not know. The same logic applies to `driver_id`, which would let the trees relearn per-driver skill the very signal the decomposition strips into `driver_skill_residual_s`. Both are correctly excluded.

## Cohorts surfaced, never dropped

Beyond the global headline, every model is scored across cohorts (compound, circuit, constructor, rain-lap, season). **21 underperforming cells** are recorded to the model card rather than hidden. The majority are the near-oracle stint-life baseline winning on specific circuits; the degradation regressors lose narrowly only on the Canadian GP, the classifier only on São Paulo. The contract is explicit: *surface losses, don't hide them.* Read the full cohort table in the [model card](/reference/ml/degradation-model-v1).
