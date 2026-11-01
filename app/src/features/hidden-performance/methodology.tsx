import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/hidden-performance`

export const methodologyContent = (
  <>
    <p>
      Ghost-projected positions come from <strong>fct_ghost_race_finish</strong>: for each driver,
      their lap times are recombined with a chosen host constructor's car pace, then re-ranked by
      predicted mean fuel-adjusted lap pace (not cumulative race time). Only scenarios where{' '}
      <code>avg_recombination_confidence &ge; 0.3</code> are included.
    </p>
    <p className="mt-2">
      A negative <em>delta</em> means the model projected a better finish than actually occurred
      the driver was "under-rewarded" by the result. It is pace versus result, not an injustice
      ledger: strategy, safety cars, and incidents legitimately move finishing positions in ways a
      pace projection cannot see. The confidence score encodes how well the
      host constructor's pace is estimated from panel data (more races with that team = higher
      confidence).
    </p>
    <p className="mt-2">
      Short runs (too few laps for a reliable estimate) are excluded. The self-scenario check: when
      the host constructor equals the driver's own team (<code>is_self_scenario</code>), every
      host-versus-own-car swap is zero, so the predicted mean lap time (
      <code>predicted_mean_lap_s</code>) equals the actual mean lap time (
      <code>actual_mean_lap_s</code>) up to rounding error; on the 2018–2025 warehouse build of
      2026-10-31 the largest gap is below 1e-13 s. A gap between those two lap times in a
      self-scenario row is a data issue. Finish position is different: the projected finish ranks
      every driver in the scenario by mean fuel-adjusted lap pace in the same car, while the actual
      finish also reflects strategy, safety cars, incidents and retirements, so it will usually
      differ. A non-zero finish delta in the self-scenario is expected, not a data issue: on that
      build <code>delta_vs_actual_position</code> is non-zero in about 94% of self-scenario rows
      (2,617 of 2,786 self-scenario rows that have an actual finish position).
    </p>
    <p className="mt-2">
      The <em>Rating</em> column is the driver's season rating from{' '}
      <code>int_era_normalized_driver_rating</code>: his median lap-by-lap gap to his teammate,
      averaged over the season, in seconds. Negative = faster than his teammate. It is a
      teammate comparison, not a gap to the field, and carries no era offset.
    </p>
  </>
)
