export const methodologyContent = (
  <>
    <p>
      For each race, every driver is placed into every constructor's car and their cumulative
      race time is predicted using pace recombination. Drivers are then re-ranked by that
      predicted time to produce a ghost finishing order.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li>
        <strong>Pace recombination</strong>: lap times are rebuilt from the driver's
        skill residual plus the host constructor's structural pace, tyre degradation, and
        environmental components from the seven-term additive decomposition.
      </li>
      <li>
        <strong>Confidence gate</strong>: only laps with recombination confidence
        &ge; 0.3 enter the race total. Scenarios where any driver falls below 0.3 are
        highlighted with a low-confidence badge.
      </li>
      <li>
        <strong>Identity invariant</strong>: when a driver is placed in their own
        constructor's car (the self-scenario), predicted time equals actual time and
        &Delta; pos = 0. This is a degenerate but verifiable case the model must satisfy.
      </li>
      <li>
        <strong>&Delta; pos</strong>: predicted minus actual finish position. Negative
        values (green) mean the driver would have finished <em>higher</em> in the ghost
        scenario; positive (red) means lower.
      </li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>fct_ghost_race_finish</code> via <code>fct_ghost_car_pace</code>.
      Recombination is a probabilistic reconstruction, not a physics simulation; treat
      positions as expected-value estimates with the confidence column as the uncertainty
      proxy.
    </p>
  </>
)

export const methodologyHref =
  'https://off-the-pace.onrender.com/reference/models/fct/fct_ghost_race_finish'
