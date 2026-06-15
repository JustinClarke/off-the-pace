export const methodologyHref =
  'https://docs.offthepace.dev/reference/models/fct/fct_ghost_race_finish'

export const methodologyContent = (
  <>
    <p>
      For each race, every driver's lap times are recombined with the host constructor's car pace
      (<code>fct_ghost_race_finish</code>) to give the pace they would have shown in that car. Each
      driver is then transplanted <em>one at a time</em> into the host car and slotted into the real
      grid: their projected finishing position is one plus the number of cars whose <em>actual</em>
      race pace was quicker than the ghost's host-car pace. F1 points (25-18-15-12-10-8-6-4-2-1) are
      assigned to both the projected and actual positions and summed across the season.
    </p>
    <p className="mt-2">
      Why rank against the real grid rather than against the other ghosts? If all drivers share the
      host car and are ranked only against each other, the car's pace level is common to everyone and
      cancels out the order collapses to a pure driver-skill ranking that barely changes whichever
      car you pick. Racing each ghost against the field in their real machinery keeps the car level in
      play: a slow host scores almost nothing, a dominant host sweeps the points.
    </p>
    <p className="mt-2">
      Only races where <code>avg_recombination_confidence &ge; 0.3</code> contribute scenarios
      with insufficient panel data are excluded rather than imputed. A coverage badge appears when
      fewer than 15 races qualify (unreliable season-level aggregation).
    </p>
    <p className="mt-2">
      The "delta" column shows how many championship points each driver gained or lost versus their
      real-world result. Note the host team's own drivers still appear in the real grid, so each
      transplant is measured against the actual field including the car's incumbents.
    </p>
  </>
)
