import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Each point is a driver's season-averaged skill residual in qualifying and in race,
      estimated independently from the same seven-term additive decomposition after
      removing car, tyre, fuel, dirty air, and conditions.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Qualifying skill</strong>: average residual from personal-best Q laps
        with traffic and DNQ sessions excluded.</li>
      <li><strong>Race skill</strong>: average <code>driver_skill_proxy_mean_s</code>
        across race stints from <code>fct_driver_skill_features</code>.</li>
      <li><strong>Q−R delta</strong>: qualifying residual minus race residual. Negative
        means the driver is relatively faster in qualifying (qualifying specialist);
        positive means they gain more in race trim (race specialist).</li>
    </ul>
    <p className="mt-3">
      Residuals are on the same scale as absolute lap times (seconds, negative = faster
      than the model predicts). The diagonal reference marks equal qualifying and race
      skill; deviation shows the direction of specialisation.
    </p>
    <p className="mt-3 text-muted/70">
      Sources: <code>int_qualifying_decomposed</code> and <code>fct_driver_skill_features</code>.
      Minimum 3 valid qualifying sessions per season required.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/quali-vs-race-skill`
