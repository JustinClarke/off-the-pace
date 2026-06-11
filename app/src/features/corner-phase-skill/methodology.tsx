import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Corner-phase skill uses ghost-car-style recombination to isolate driver technique from
      car performance. Rather than comparing each driver directly against the field median
      (which mixes car + driver), the model first estimates what each corner looks like
      for a driver's specific car, then measures how much the driver deviates from that
      car baseline.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li>
        <strong>Car effect estimation:</strong> For each <code>(season, constructor, corner)</code>,
        the model averages the braking point, apex speed, and throttle point across all valid
        laps by that constructor at that corner. This is the car's characteristic geometry  
        what the machinery "wants" to do at that turn.
      </li>
      <li>
        <strong>Driver deviation:</strong> Each driver's per-corner geometry is subtracted from
        their car's average. Negative deviation = driver is more aggressive (earlier brake,
        higher apex, earlier throttle) than their machinery baseline the "skill residual".
      </li>
      <li>
        <strong>Phase z-scores:</strong> Braking, mid-corner, and exit residuals are each
        standardised across the driver pool within the season (zero mean, unit variance). This
        ensures all three phases contribute equally to the final index, eliminating the exit
        dominance present in raw deltas (exit has 4–6× the spread of the other phases).
      </li>
      <li>
        <strong>Skill Index:</strong> Sum of the three z-scores. Lower = faster corner driver.
        A driver in a slow car will rank on the basis of skill, not car speed; a driver in a
        fast car who under-delivers relative to their machinery will rank lower.
      </li>
    </ul>
    <p className="mt-3">
      Lap filtering: SC / VSC / pit / inaccurate / deleted laps are excluded before car
      averages are formed to prevent safety-car geometry from contaminating the car baseline.
      Car-corner cells with fewer than 5 observations are also excluded. Only drivers with
      ≥ 100 mapped corner observations are shown.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>mart_corner_skill_driver</code>. Season aggregate.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/corner-phase-skill`
