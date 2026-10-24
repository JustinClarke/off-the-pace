import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/constructors`

export const methodologyContent = (
  <>
    <p>
      Team averages compare constructors on the same laps, using <strong>fct_lap_residuals</strong>.
      Each team's value is the average of its per-race values, so a driver's share of races counts
      equally across the team's races.
    </p>
    <p className="mt-2">
      Teammates and cross-team pairs are <strong>not paired</strong>. A corner or lap gap between two
      cars mostly measures the car, so this page reports each team's own average instead of comparing
      drivers across teams.
    </p>
    <p className="mt-2">
      Only training-eligible laps are included. Missing readings are blank, not zero: a team with no
      measured dirty-air laps shows an empty cell.
    </p>
  </>
)
