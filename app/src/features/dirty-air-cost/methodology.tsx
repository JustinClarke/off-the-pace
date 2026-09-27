import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      The dirty air cost leaderboard quantifies how many seconds each driver lost to running in
      disturbed airflow during the selected race.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Total cost</strong>: <code>cumulative_dirty_air_tax_race_s</code>, the race-end
        sum of the per-lap dirty air charge. Drivers who spent more laps closely following another
        car accumulate a larger total.</li>
      <li><strong>Avg per lap</strong>: mean <code>dirty_air_tax_s</code> over the driver&apos;s
        scored laps. Every charged lap is charged the same amount, so this is the share of laps
        spent following times that amount, not a measure of how close the driver followed.</li>
      <li><strong>Taxed laps</strong>: laps where any dirty air tax was applied
        (dirty_air_tax_s &gt; 0).</li>
    </ul>
    <p className="mt-3">
      The charge comes from one coefficient shared by every circuit and every season: a single
      OLS slope of lap pace against the field on whether the
      previous lap was spent following. A lap counts as following when the median gap to the
      car ahead through the middle third of the lap was under 1.5 s. A lap is charged that
      coefficient if the previous lap in the same stint was following, and nothing otherwise.
      The first lap of each stint and the lap after a safety car, VSC or red flag lap are never
      charged; pit laps and neutralised laps are not scored.
    </p>
    <p className="mt-3">
      Measured season by season, the cost of following is not constant (it was highest in 2018),
      but this leaderboard applies the one pooled coefficient to every race.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_dirty_air_tax_component</code>. Single race view.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/dirty-air-cost`
