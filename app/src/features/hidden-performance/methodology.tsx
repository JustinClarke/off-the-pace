import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/hidden-performance`

export const methodologyContent = (
  <>
    <p>
      Ghost-projected positions come from <strong>fct_ghost_race_finish</strong>: for each driver,
      their lap times are recombined with a chosen host constructor's car pace, then re-ranked by
      predicted cumulative race time. Only scenarios where{' '}
      <code>avg_recombination_confidence &ge; 0.3</code> are included.
    </p>
    <p className="mt-2">
      A negative <em>delta</em> means the model projected a better finish than actually occurred
      the driver was "under-rewarded" by the result. The confidence score encodes how well the
      host constructor's pace is estimated from panel data (more races with that team = higher
      confidence).
    </p>
    <p className="mt-2">
      Short runs (too few laps for a reliable estimate) are excluded. The identity check: when the
      host constructor equals the driver's own team, predicted finish equals actual finish any
      deviation from zero in that case signals a data issue.
    </p>
  </>
)
