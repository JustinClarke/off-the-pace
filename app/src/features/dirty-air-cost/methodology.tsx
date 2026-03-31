export const methodologyContent = (
  <>
    <p>
      The dirty air cost leaderboard quantifies how many seconds each driver lost to running in
      disturbed airflow during the selected race.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Total cost</strong>: <code>cumulative_dirty_air_tax_race_s</code> the race-end
        cumulative dirty air penalty from the OLS airflow model. Drivers who spent more laps closely
        following another car accumulate a larger penalty.</li>
      <li><strong>Avg per lap</strong>: mean <code>dirty_air_tax_s</code> per classified lap,
        capturing intensity not just duration. High average with low total = short stint in heavy traffic.</li>
      <li><strong>Taxed laps</strong>: laps where any dirty air tax was applied
        (dirty_air_tax_s &gt; 0).</li>
    </ul>
    <p className="mt-3">
      The model estimates dirty air via gap-to-car-ahead using a per-circuit OLS coefficient.
      Zero-gap laps (leader, SC restart, DRS opens) carry no tax.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_dirty_air_tax_component</code>. Single race view.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/reference/models/int/int_dirty_air_tax_component'
