import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Driver Workload aggregates four tyre and traffic stress signals per driver across a
      season, revealing who races deepest into stints, pushes hardest on tyres, and spends
      the most time in aerodynamically compromised air.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Push residual</strong>: thermal and mechanical load proxy from within-stint
        driver-skill residual drift. Higher values indicate a more aggressive pushing style
        that accelerates tyre degradation.</li>
      <li><strong>Avg stint age</strong>: mean lap-in-stint across all eligible laps. Drivers
        with longer averages are kept out longer by their teams a proxy for tyre management
        capability or strategic circumstance.</li>
      <li><strong>Dirty air share</strong>: fraction of eligible laps classified as dirty-air
        (gap &lt; 1.5s in sector 2). Higher share means more time in thermally loaded air
        behind competitors.</li>
      <li><strong>Cliff risk</strong>: fraction of eligible laps flagged as cliff candidates
        by the degradation model. Indicates how often the driver approaches the tyre
        performance cliff.</li>
    </ul>
    <p className="mt-3">
      Only training-eligible laps (age in stint &gt; 3, no SC or mistake laps) are included.
      Drivers with fewer than 50 eligible laps in the season are excluded.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>fct_cliff_prediction_features</code>.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/driver-workload`
