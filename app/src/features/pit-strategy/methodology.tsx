import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/pit-strategy`

export const methodologyContent = (
  <div className="space-y-3 text-sm text-muted">
    <p>
      Each stint is placed on the Gantt as a horizontal bar spanning its actual race
      laps. Bar fill reflects the tyre compound; the border colour shows the strategy
      verdict (<span className="text-emerald-400 font-mono">optimal</span> /
      {' '}<span className="text-red-400 font-mono">overran</span> /
      {' '}<span className="text-blue-400 font-mono">early</span> /
      {' '}<span className="text-amber-400 font-mono">undercut forced</span> /
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
     -the argmin of Total_Cost(L) over every candidate lap in the horizon: wear
      on the set you are on, wear on the next set, and the pit-lane loss
      discounted by the chance a safety car has already appeared. Not stopping
      at all is one of the candidates.
    </p>
    <p>
      <strong className="text-[rgb(var(--color-text))]">Opportunity cost</strong> is
      Total_Cost(actual) minus Total_Cost(optimal), in seconds-so stopping too
      early carries a cost too, not only overrunning.
      &ldquo;unknown&rdquo; means the compound has no fitted degradation curve
      to minimise over, shown explicitly rather than as a silent null.
    </p>
    <p className="text-xs">
      Source:{' '}
      <code>fct_stint_features</code> &times; <code>fct_lap_residuals</code> (for
      lap windows) &times; <code>int_pit_strategy_value</code>.
    </p>
  </div>
)
