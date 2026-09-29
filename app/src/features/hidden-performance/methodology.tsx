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
      Short runs (too few laps for a reliable estimate) are excluded. The self-scenario check: when
      the host constructor equals the driver's own team, the predicted per-lap pace should match
      the actual per-lap pace. Finish position depends on how other drivers rank within the scenario
      when transplanted to the same car, so it will differ from actual finish.
    </p>
    <p className="mt-2">
      The <em>Rating</em> column is the driver's season rating from{' '}
      <code>int_era_normalized_driver_rating</code>: his median lap-by-lap gap to his teammate,
      averaged over the season, in seconds. Negative = faster than his teammate. It is a
      teammate comparison, not a gap to the field, and carries no era offset.
    </p>
  </>
)
