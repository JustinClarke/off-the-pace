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
    <p>
      <strong className="text-[rgb(var(--color-text))]">Horizon</strong> is this stint plus
      the next: it ends where the driver&rsquo;s next stint ends, the next set is the compound
      actually fitted (treated as new), and exactly one stop is assumed inside it. So the rest of
      the strategy is taken as the team actually ran it, and the verdict grades the lap the stop
      landed on, not the number of stops. Where no next stint exists (the driver&rsquo;s last
      stint), the model falls back to the race-remainder horizon, from this stint&rsquo;s first
      lap to the driver&rsquo;s last lap; <code className="text-xs">horizon_source</code> records
      which was used. The cost has no track-position term, so a stop that looks early may have
      been the right response to something the model does not measure.
    </p>
    <p>
      <strong className="text-[rgb(var(--color-text))]">On the 2018&ndash;2025 warehouse build of
      2026-10-31</strong>, 5,100 stints have both an actual stop and a model optimum: 4,835
      graded on the two-stint horizon and 265 on the race-remainder horizon.{' '}
      <code className="text-xs">overrun_laps</code> (actual laps on the set minus model-optimal
      laps, in valid laps; negative = earlier than the optimum) has a median of -2 valid laps per
      stint; per season the median ranges from 0 (2018) to -4 (2020). In 59% of those stints the
      stop came earlier than the model&rsquo;s optimum. The verdicts are 2,571 early, 1,526
      overran, 839 optimal and 164 undercut forced.
    </p>
    <p className="text-xs">
      Source:{' '}
      <code>fct_stint_features</code> &times; <code>fct_lap_residuals</code> (for
      the race&rsquo;s lap count) &times; <code>int_pit_strategy_value</code>.
    </p>
  </div>
)
