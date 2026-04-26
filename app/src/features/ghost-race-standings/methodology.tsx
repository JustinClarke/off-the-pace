export const methodologyContent = (
  <>
    <p>
      For each race, every driver is placed into every constructor's car and their lap times
      are predicted using pace recombination. Drivers are then re-ranked by predicted
      <strong> mean lap pace</strong> to produce a ghost finishing order.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li>
        <strong>Pace recombination</strong>: lap times are rebuilt from the driver's
        skill residual plus the host constructor's structural pace, tyre degradation, and
        environmental components from the seven-term additive decomposition.
      </li>
      <li>
        <strong>Ranked by pace, not total time</strong>: ranking on cumulative race time
        unfairly rewards drivers who ran fewer laps (a DNF accumulates a smaller total).
        Ranking by mean lap pace is invariant to lap count, so partial races compare fairly.
      </li>
      <li>
        <strong>Partial races (DNF)</strong>: drivers covering less than half the race
        distance are flagged <span className="text-amber-400/80 font-mono">dnf</span> their
        estimate is small-sample, and &Delta; pos is blank because they have no real finishing
        position.
      </li>
      <li>
        <strong>Confidence</strong>: a continuous score combining how well the host car's
        pace is estimated (panel-observation shrinkage) with how much of the race the driver
        actually contributed. It now varies per driver rather than sitting at a flat value.
      </li>
      <li>
        <strong>Identity invariant</strong>: when a driver is placed in their own
        constructor's car (the self-scenario, shown as <em>self</em>), predicted pace equals
        actual. A degenerate but verifiable case the model must satisfy.
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
  'https://offthepace.mintlify.app/reference/models/fct/fct_ghost_race_finish'
