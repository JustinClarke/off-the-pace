import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      This is the trained tyre-degradation models running <strong>live in your browser</strong> -
      not a precomputed lookup. Five XGBoost models, exported to ONNX, score a 42-feature input
      vector through <code>onnxruntime-web</code> every time you move a slider.
    </p>
    <p className="mt-3">
      The headline is an <strong>absolute projected lap time</strong>, built entirely client-side and
      <strong> decoupled from the ONNX models</strong> &mdash; it renders the moment the history loads,
      even if inference is slow or offline:
    </p>
    <pre className="mt-2 text-xs bg-white/5 rounded p-3 overflow-x-auto">
{`projected_lap_time(k) = base + fuel(k) + tyre(k)

base     = ref_green_pace + constructor_offset + conditions_cost   [fresh-tyre, fuel-removed]
fuel(k)  = weight_penalty_factor × max(0, fuel_start − burn × (k−1))
tyre(k)  = working_deg(k) × track_scale + cliff_term(k)            [monotone by construction]
  working_deg(k) = isotonic observed deg-from-fresh (held flat past the observed range)
  cliff_term(k)  = gain × severity × max(0, k − onset_eff)^1.5     [0 before onset]`}
    </pre>
    <p className="mt-3">
      The <strong>working window</strong> (k ≤ onset) is a <em>weighted isotonic regression</em> fit
      to the raw observed deg-from-fresh (p10/p50/p90) per circuit × era × compound, n-weighted so the
      thin survivor-biased tail is held flat rather than dropping. The raw median is non-monotone (old
      tyres spuriously appear faster when only the hardiest tyres survive at late laps); the isotonic
      fit corrects this with 0 violations and MAE ≤ 0.5s vs the raw data &mdash; this part stays
      strictly faithful to what actually happened.
    </p>
    <p className="mt-3">
      Past the onset the curve adds a <strong>cliff term</strong>: a convex acceleration scaled by the
      circuit × compound&apos;s <em>fitted</em> cliff severity. This is a deliberate, signposted
      extrapolation <em>beyond</em> the survivor sample &mdash; the observed median goes flat there only
      because cliff-hitting tyres get pitted and leave the data, so the headline reconstructs the cliff
      from the fitted params rather than pretending it does not exist. The term and its slope are both
      zero at the onset, so the join is smooth (no kink), and a running-max guard keeps the whole curve
      monotone at every slider position.
    </p>
    <p className="mt-3">
      Every control moves the curve: <strong>Fuel</strong> tilts it (and now also feeds the ONNX
      panels); <strong>Dirty-air</strong> and <strong>temperature</strong> add a per-lap pace cost
      <em> and</em> bring the cliff onset forward (overheating wears faster); <strong>abrasiveness</strong>
      scales cliff severity; <strong>track energy</strong> scales the working-window deg rate;
      <strong> constructor</strong> shifts the fresh-tyre anchor (post-2022 structural pace);
      <strong> circuit</strong>, <strong>era</strong> and <strong>compound</strong> swap the whole
      envelope and cliff parameters.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Fresh-tyre anchor</strong> (<code>ref_green_pace_s</code>) is the per
        circuit × era × compound median fuel-removed lap time over fresh-tyre clean laps, from the{' '}
        <code>mart_degradation_history_envelope</code> mart.</li>
      <li><strong>Observed range</strong> (dashed band) is the fitted p10/p90 what actually happened
        across comparable 2018–2024 stints, monotonised; past the onset it carries the same cliff term
        so the band rises with the projection.</li>
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
      42-feature vector including its real telemetry (gear changes, RPM, full-throttle and DRS
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

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/degradation-simulator`
