export const methodologyContent = (
  <>
    <p>
      This is a driver's <strong>track record in equal machinery</strong>. For one circuit and
      one regulation era, every driver who raced there is ranked by their car-removed pace so the
      board reads as driver skill at that track not whose car was quickest.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li>
        <strong>Equal car</strong>: each lap's time is decomposed into fuel, tyre compound, rubber,
        ambient, <em>constructor</em>, and driver-skill components (the seven-term additive
        identity). The leaderboard uses only the driver-skill residual the part left once the car
        and conditions are removed so a slow car no longer hides a fast driver, and vice versa.
        Negative = faster than the field.
      </li>
      <li>
        <strong>Split by era, not blended</strong>: records are computed separately for
        <span className="font-mono"> 2018–2021</span> (last-gen aero) and
        <span className="font-mono"> 2022–2024</span> (ground-effect), split on the 2022 regulation
        change. A driver's pace is only ever compared within one car era, never averaged across
        the boundary.
      </li>
      <li>
        <strong>No single year</strong>: every race a driver ran at the circuit within the era is
        pooled, so this is a multi-season record rather than one race's result.
      </li>
      <li>
        <strong>Shrunk toward the driver's own average</strong>: a one-race sample is regularised
        toward the driver's era-wide mean (Bayesian, prior = 5 virtual races), so a single hot lap
        can't top the board on noise. The <span className="font-mono">Conf.</span> column is the
        data fraction of the estimate <span className="font-mono">n / (n + 5)</span>; values
        below <span className="font-mono">{0.3}</span> (amber) are prior-dominated and should be
        read as "not enough races yet".
      </li>
      <li>
        <strong>95% CI</strong>: the credible interval on the shrunk estimate. Overlapping
        intervals mean two drivers are statistically tied at that track.
      </li>
      <li>
        <strong>Min. races</strong>: filters out thin samples; the gap-to-leader is measured
        against the fastest driver among those shown.
      </li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>int_driver_circuit_era_affinity</code>, built on the driver-skill residual of{' '}
      <code>fct_lap_residuals</code>. This is a statistical reconstruction of equal-car pace, not a
      physics simulation treat the ranking as expected-value estimates with the confidence and CI
      columns as the uncertainty.
    </p>
  </>
)

export const methodologyHref =
  'https://offthepace.mintlify.app/reference/models/int/int_driver_circuit_era_affinity'
