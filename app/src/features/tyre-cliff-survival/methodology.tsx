export const methodologyContent = (
  <>
    <p>
      The survival curve shows the probability that a tyre stint reaches a given lap
      without a cliff onset event-estimated using the Kaplan-Meier estimator from
      historical stint data.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li>
        <strong>Cliff onset</strong>: detected when compound degradation rate
        accelerates beyond a threshold derived from <code>fct_cliff_prediction_features</code>.
        A stint where the driver pitted before hitting the cliff is <em>censored</em> -
        it tells us the cliff had not happened by lap N, not that it never would.
      </li>
      <li>
        <strong>Kaplan-Meier</strong>: a non-parametric survival estimator. At each
        lap where at least one cliff is observed, S(t) updates as
        S(t) = S(t-1) x (1-events / at-risk). Censored stints reduce the at-risk
        pool without contributing an event.
      </li>
      <li>
        <strong>Model onset line</strong>: the median cliff lap from the fitted
        Cox/KM model stored in <code>dim_compounds_season</code>. The scatter of actual
        stint end-points is the live validation: if the KM curve crosses 0.5
        near the model line, the fit is well-calibrated.
      </li>
      <li>
        <strong>Degradation overlay (right axis)</strong>: cumulative expected
        degradation in seconds at the point each stint ended (sum of
        <code>expected_degradation_rate_s_per_lap</code> per lap in stint).
        Red dots = cliff observed before pit; grey squares = pit before cliff.
      </li>
    </ul>
    <p className="mt-3 text-muted/70">
      Rain laps and anomaly-flagged laps are excluded from both the KM curve and
      the scatter. The provenance footer shows the original fit date and the
      number of cross-season stints used.
    </p>
  </>
)

export const methodologyHref =
  'https://off-the-pace.onrender.com/reference/models/int/int_compound_cliff_predicted'
