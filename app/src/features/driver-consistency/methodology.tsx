export const methodologyContent = (
  <>
    <p>
      Each point represents a driver's season-level lap time residual the component of
      pace unexplained by car, tyre state, fuel, dirty air, and conditions. Residuals are
      computed per clean lap and aggregated across a season.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Mean residual</strong>: average delta vs the expected lap given circumstances.
        Negative = faster than circumstances predict; positive = slower.</li>
      <li><strong>Std dev</strong>: lap-to-lap variance in that residual. Low = consistent
        delivery; high = erratic hot laps but also cold ones.</li>
      <li><strong>Clean lap filter</strong>: laps with safety cars, pit-in/out windows,
        anomaly flags, or fewer than 10 valid laps are excluded.</li>
    </ul>
    <p className="mt-3">
      The crosshairs show the season median on each axis, creating four quadrants. The
      north-star quadrant is fast-consistent (bottom-left): the driver reliably extracts
      more from the car than circumstances predict.
    </p>
    <p className="mt-3 text-muted/70">
      Residuals accumulate from <code>fct_driver_skill_features</code> via the
      seven-term additive decomposition enforced by <code>assert_additive_identity</code>.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/reference/models/fct/fct_driver_skill_features'
