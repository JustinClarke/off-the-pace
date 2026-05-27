export const methodologyContent = (
  <>
    <p>
      The synthetic teammate comparison removes the strategic divergence between
      drivers on the same car. Instead of comparing raw lap times, it weight-corrects
      each driver's pace by the teammate's adjusted lap time, isolating pure skill
      from strategy and position effects.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Skill proxy</strong>: ego pace minus the synthetic teammate's
        world-coordinate-adjusted pace, averaged over non-divergent laps. Negative
        means the driver is faster than their synthetic benchmark.</li>
      <li><strong>Quality weight</strong>: confidence in the comparison lap.
        Higher weight = the lap pair is in similar conditions (tyre age, position,
        fuel load). Low-weight laps are down-weighted in the average.</li>
      <li><strong>Strategic divergence</strong>: laps where the driver and teammate
        are on different stint strategies are excluded to avoid contaminating the
        comparison with non-pace factors.</li>
    </ul>
    <p className="mt-3">
      The result answers: <em>given the same car in the same race conditions, which
      driver would be faster?</em>
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_synthetic_teammate</code>. Season-level aggregation.
      Minimum 3 non-divergent races required.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/reference/models/int/int_synthetic_teammate'
