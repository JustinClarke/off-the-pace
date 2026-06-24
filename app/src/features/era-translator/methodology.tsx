import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      The era-adjusted rating puts every driver season on a single comparable scale,
      correcting for the 2022 ground-effect regulation shift. Ratings from 2018 are
      directly comparable to ratings from 2024.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Era-adjusted rating</strong>: Bayesian-shrunk seasonal residual,
        offset by the era shift estimated from 20 bridge drivers who raced on both
        sides of the 2022 regulation boundary. Negative = faster than the
        era-normalised field average.</li>
      <li><strong>95% CI</strong>: propagates both the within-season sampling
        uncertainty and the era-offset uncertainty. Wider ribbon = fewer qualifying
        seasons for the bridge anchor or fewer clean laps for the driver.</li>
      <li><strong>Bridge anchor</strong> (★): drivers with ≥8 clean-race seasons
        spanning pre- and post-2022, used to anchor the era shift. Their ratings
        are the most directly comparable across eras.</li>
    </ul>
    <p className="mt-3">
      This is the same underlying data as the Era-Adjusted Rating Timeline
      (career arcs view), presented as a season leaderboard for direct
      within-season cross-era comparison.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_era_normalized_driver_rating</code>. Minimum 5 races required.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/era-translator`
