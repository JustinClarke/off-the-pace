import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Each line tracks a driver's season rating: how far ahead of (or behind) his teammate
      he was, in seconds per lap, in the same car. Negative = faster than his teammate(s).
      The car cancels in the teammate comparison, and so does the 2022 regulation change,
      which moved both teammates alike, so no era offset is applied.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li>
        <strong>Per race:</strong> the median of the driver's lap-by-lap gap to his
        teammate on laps both ran clean.
      </li>
      <li>
        <strong>Bayesian shrinkage:</strong> per-season means are shrunk toward the
        season mean with a 5-race prior. Drivers with fewer races have wider CIs and
        estimates pulled closer to zero; the uncertainty is honest, not hidden.
      </li>
      <li>
        <strong>Relative to the teammate:</strong> a line moves when the driver's margin
        over his teammate moves, and a change of teammate can move it as much as a change
        in the driver. Drivers with at least 8 races on each side of 2022 ("bridge") are
        shown as solid lines, others as dashed; this is context only and changes no
        rating.
      </li>
      <li>
        <strong>95% CI ribbon:</strong> the per-season posterior uncertainty.
      </li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>int_era_normalized_driver_rating</code> via{' '}
      <code>int_driver_season_ratings</code> (column <code>era_adjusted_rating</code>,
      which carries no era offset). Clean-lap filter applied upstream.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/era-ratings-timeline`
