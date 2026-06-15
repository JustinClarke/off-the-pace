export const methodologyContent = (
  <>
    <p>
      This is the trained tyre-degradation models running <strong>live in your browser</strong> -
      not a precomputed lookup. Five XGBoost models, exported to ONNX, score a 41-feature input
      vector through <code>onnxruntime-web</code> every time you move a slider.
    </p>
    <p className="mt-3">
      The headline is an <strong>absolute projected lap time</strong>, built from three additive pieces:
    </p>
    <pre className="mt-2 text-xs bg-white/5 rounded p-3 overflow-x-auto">
{`projected_lap_time(k) = ref_green_pace                         [fresh-tyre anchor, fuel-removed]
                      + weight_penalty_factor × fuel(k)         [Fuel]
                      + isotonic(observed deg)(k) × M           [Tyre monotone by construction]

M = clamp(1 + air_bump·𝟙[dirty_air] + temp_penalty·max(0, ΔT − headroom), 1.0, 1.5)`}
    </pre>
    <p className="mt-3">
      The <strong>Tyre</strong> term is a <em>weighted isotonic regression</em> fit to the raw
      observed deg-from-fresh (p10/p50/p90) per circuit × era × compound, n-weighted so the thin
      survivor-biased tail is held flat rather than dropping. The raw median is non-monotone (old
      tyres spuriously appear faster when only the hardiest tyres remain at late laps); the isotonic
      fit corrects this with 0 violations and MAE ≤ 0.5s vs the raw data. Multiplied by <strong>M</strong>
      a modulation factor computed from your dirty-air and ambient-temp sliders the curve stays
      monotone at all inputs (M is constant across the stint).
    </p>
    <p className="mt-3">
      The model is fed a <strong>neutral fuel trajectory</strong> (the circuit&apos;s consumption
      rate) so the Fuel slider cleanly shifts the curve without distorting the ONNX tyre prediction.
      The dirty-air and temp sliders move the headline <em>modestly by design</em> (~0.1–0.3s):
      dirty air is a sign-gated within-race contrast; the temp penalty is a compound-window
      overheating term (not a raw linear slope the raw data is non-monotone in temperature).
      Fuel, compound, circuit, and era are the dominant movers.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Fresh-tyre anchor</strong> (<code>ref_green_pace_s</code>) is the per
        circuit × era × compound median fuel-removed lap time over fresh-tyre clean laps, from the{' '}
        <code>mart_degradation_history_envelope</code> mart.</li>
      <li><strong>Observed range</strong> (dashed band) is the fitted p10/p90 × M what actually
        happened across comparable 2018–2024 stints, monotonised and scaled to your conditions.</li>
      <li><strong>The fan</strong> is the degradation-jump quantile trio (p10/p50/p90) the
        predicted next-lap pace loss swept across every lap (ONNX models unchanged).</li>
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
      <strong>Load a real stint</strong> to score that tyre&apos;s actual per-lap rows - the full
      41-feature vector including its real telemetry (gear changes, RPM, full-throttle and DRS
      share, corner-speed loss, …) - and overlay its observed next-lap jump (dashed) against the
      predicted fan. The moment you drag a slider you enter what-if space: those laps never
      happened, so the 11 telemetry features (which have no sliders) pass through as XGBoost
      native-missing (NaN), never imputed.
    </p>
    <p className="mt-3 text-muted/70">
      Browser inference is proven to match the trained boosters to 7.6e-6 (max abs) by the
      ONNX-parity test. The categorical encoders, feature order, and output post-processing are
      read at runtime from <code>manifest.json</code>; nothing is hard-coded.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/ml/overview'
