export const methodologyHref =
  'https://off-the-pace.onrender.com/machine-learning'

export const methodologyContent = (
  <div className="flex flex-col gap-3 text-sm text-muted leading-relaxed">
    <p>
      Five XGBoost 3.2.0 models predict next-lap tyre degradation (p10/p50/p90 quantile trio),
      laps-until-cliff class (4-class), and remaining stint life. All are trained on 38 per-lap
      features from <code>fct_cliff_prediction_features</code> covering 2018-2024.
    </p>
    <p>
      Evaluation uses a season-grouped <strong>TimeSeriesSplit</strong> (5 folds, expanding window)
      so the final fold always validates on 2024-a strict temporal holdout. Every number on this
      page is read directly from <code>model_card.json</code>; none are hand-typed.
    </p>
    <p>
      <strong>Baselines</strong> are strong per-cohort anchors: group-mean over compound x circuit x
      age-bucket cells for the degradation models; majority-class prior for the cliff classifier;
      a knowingly leakage-shaped anchor for stint life. Beating these baselines is the headline claim.
    </p>
    <p>
      <strong>Calibration</strong>: the p10-p90 interval targets 80% empirical coverage. Conformal
      calibration applies a small correction (q = conformal_q from the card) to exactly hit the
      nominal level on the held-out fold.
    </p>
    <p>
      <strong>Feature importance</strong> cross-validates SHAP (tree-path attribution) against
      permutation importance (model-agnostic). Agreement in the top-5 indicates genuine signal;
      disagreements flag potentially correlated or collinear features.
    </p>
    <p>
      2025 is the designated true holdout and will ingest post-launch, at which point the
      <code>is_holdout</code> flag in <code>mart_degradation_predictions</code> flips automatically
      with no code change.
    </p>
  </div>
)
