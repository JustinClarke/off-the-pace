export const methodologyContent = (
  <>
    <p>
      This is the trained tyre-degradation models running <strong>live in your browser</strong> -
      not a precomputed lookup. Five XGBoost models, exported to ONNX, score a 38-feature input
      vector through <code>onnxruntime-web</code> every time you move a slider.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>The fan</strong> is the degradation-jump quantile trio (p10/p50/p90)-the
        predicted next-lap pace loss in seconds-swept across every lap of the stint.</li>
      <li><strong>Cliff probability</strong> is the multiclass cliff classifier&apos;s softprob over
        four classes (cliff in 0-2 / 3-5 / 6+ laps, or none this stint) at the current lap.</li>
      <li><strong>Remaining life</strong> is the stint-life regressor, clipped at zero.</li>
    </ul>
    <p className="mt-3">
      Sliders are bounded by the p5-p95 range of the real training data
      (<code>fct_cliff_prediction_features</code>, 2018-2024). The cliff-state features
      (<code>cliff_onset_passed</code>, <code>laps_past_cliff</code>, <code>cliff_candidate_flag</code>)
      are derived per lap from the compound&apos;s cliff-onset constant, exactly as the warehouse
      computes them, so the swept rows are faithful model inputs.
    </p>
    <p className="mt-3">
      <strong>Load a real stint</strong> to score an actual lapped tyre-all 38 features filled
      from the warehouse-and overlay the observed next-lap jump (dashed) against the predicted
      fan. Eight telemetry / air-density features are absent from the export and were NULL in
      training too; they pass through as XGBoost native-missing (NaN), never imputed.
    </p>
    <p className="mt-3 text-muted/70">
      Browser inference is proven to match the trained boosters to 1.05e-5 (max abs) by the
      ONNX-parity test. The categorical encoders, feature order, and output post-processing are
      read at runtime from <code>manifest.json</code>; nothing is hard-coded.
    </p>
  </>
)

export const methodologyHref = 'https://off-the-pace.onrender.com/machine-learning'
