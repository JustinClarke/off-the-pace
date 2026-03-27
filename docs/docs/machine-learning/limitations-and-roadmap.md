---
sidebar_position: 8
title: Limitations & roadmap
---

# Limitations & roadmap

The machine layer is built, tested and reproducible and it is **v1**. This page is the honest accounting of what it cannot do yet, in the same spirit as the project-wide [limitations](/understand/limitations).

---

## Known limitations

- **The cliff classifier is the weakest model.** Macro-F1 ≈ 0.37 on 4-class cliff timing decisively beats the majority prior (0.18) but is modest in absolute terms; skill on the rare imminent-cliff windows is limited. The 100 most-confident misses are exported (`holdout_biggest_misses.parquet`) for study.
- **No live 2025 holdout yet.** Headline numbers are the final time-series CV fold (2024). They become a true out-of-sample reveal automatically when 2025 ingests-but until then, they are cross-validation, not a held-out season.
- **v1 hyperparameters come from a reduced tuning budget.** A canonical `make ml-tune` (50 trials / 5 folds / full data) should precede a production blessing. It only improves params, no code change.
- **~47% of laps have a NULL cliff-onset prior** (2018 legacy compounds, un-fit circuits). XGBoost carries the missingness natively-documented rather than imputed-but those laps lean less on the strongest prior.
- **The stint-life baseline is near-oracle** by design (it uses true stint length). Treat the model's *overall* win as the meaningful signal and read the per-cohort losses as honest disclosure.
- **CI has not run on a live PR.** The `ml-ci.yml` workflow is written and locally consistent; its season-grouped smoke job needs bronze fixtures covering ≥6 seasons.

## Inherited data ceilings

The machine layer cannot exceed the [data ceilings](/understand/limitations) of the layers beneath it: no tyre temperature or pressure telemetry, no actual fuel load (inferred), no setup data, ~10 Hz interpolated telemetry, and pre-2018 coverage absent. Degradation is always *inferred* from lap-time behaviour and physics proxies, never measured directly.

## Roadmap

- **Canonical re-tune + production blessing**-run the full Optuna budget and a twice-through `make ml-all` timing check; the determinism machinery is already [proven](/machine-learning/reproducibility-and-deployment).
- **2025 ingestion → true holdout**-the moment OpenF1 2025 lands in the bronze layer, evaluation flips to a real out-of-sample season with no code change.
- **The web app**-React + DuckDB-Wasm scoring the [ONNX models](/machine-learning/reproducibility-and-deployment) client-side, surfacing the cliff prediction and degradation band on a race page.
- **v2 modelling**-improving the cliff classifier's minority-window skill is the clearest target, informed by the biggest-misses set and the ablation findings.

---

*For the exhaustive, auto-generated numbers behind everything in this section every hyperparameter, cohort and calibration figure see the [Tyre Degradation Predictors (v1)](/reference/ml/degradation-model-v1) model card, generated from `ml/model_card.yml`.*
