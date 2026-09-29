import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Every driver-season is rated by the same yardstick: how far ahead of (or behind) his
      teammate the driver was, in the same car. Because both drivers share the car, the
      car cancels, and so does the 2022 ground-effect regulation change, which moved both
      teammates alike. That is what puts 2018 and 2025 on one scale. No era offset is
      applied.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Rating</strong>: per race, the median of the driver's lap-by-lap gap to
        his teammate on laps both ran clean; averaged over the season and shrunk toward the
        season mean with a 5-race prior. Negative = faster than his teammate(s), positive =
        slower. Most seasons sit within ±0.4s.</li>
      <li><strong>Relative to the teammate</strong>: a rating says as much about the teammate
        as the driver. A −0.3s season next to a weak teammate and a −0.3s season next to a
        strong one are not the same achievement.</li>
      <li><strong>95% CI</strong>: the season rating's posterior uncertainty. Wider = fewer
        races.</li>
      <li><strong>★</strong>: drivers with at least 8 races on each side of the 2022
        regulation boundary. Shown for context; the rating does not depend on them.</li>
    </ul>
    <p className="mt-3">
      This is the same underlying data as the Era Ratings Timeline (career arcs view),
      presented as a season leaderboard.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_era_normalized_driver_rating</code> (column{' '}
      <code>era_adjusted_rating</code>, which carries no era offset). Minimum 5 races required.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/era-translator`
