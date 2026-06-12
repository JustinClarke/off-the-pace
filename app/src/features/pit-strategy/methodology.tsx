export const methodologyHref =
  'https://offthepace.mintlify.app/reference/models/int/int_pit_strategy_value'

export const methodologyContent = (
  <div className="space-y-3 text-sm text-muted">
    <p>
      Each stint is placed on the Gantt as a horizontal bar spanning its actual race
      laps. Bar fill reflects the tyre compound; the border colour shows the strategy
      verdict (<span className="text-emerald-400 font-mono">optimal</span> /
      {' '}<span className="text-red-400 font-mono">overran</span> /
      {' '}<span className="font-mono">unknown</span>).
    </p>
    <p>
      <strong className="text-[rgb(var(--color-text))]">Cliff onset</strong> (dashed
      line inside bar) comes from{' '}
      <code className="text-xs">fct_stint_features.cliff_lap_in_stint</code>-the
      lap within the stint where the compound crossed the degradation threshold.
    </p>
    <p>
      <strong className="text-[rgb(var(--color-text))]">Optimal pit window</strong>{' '}
      (triangle below bar) comes from{' '}
      <code className="text-xs">int_pit_strategy_value.optimal_pit_lap_in_stint</code>{' '}
     -the lap at which stopping would have minimised total race time given the
      degradation model and undercut threat window.
    </p>
    <p>
      <strong className="text-[rgb(var(--color-text))]">Opportunity cost</strong> is
      the estimated time lost by pitting later than optimal, in seconds.
      Verdicts require a minimum confidence threshold; stints below it show as
      &ldquo;unknown&rdquo; rather than silent null.
    </p>
    <p className="text-xs">
      Source:{' '}
      <code>fct_stint_features</code> &times; <code>fct_lap_residuals</code> (for
      lap windows) &times; <code>int_pit_strategy_value</code>.
    </p>
  </div>
)
