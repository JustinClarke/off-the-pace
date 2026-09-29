import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Driver circuit affinity measures how much better or worse a driver does against his
      teammate at a specific circuit than he does on average. The car is removed by the
      teammate comparison: each race's input is the driver's median lap-by-lap gap to his
      teammate in the same car, on laps both drivers ran clean.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Affinity</strong>: the driver's Bayesian-shrunk gap to his teammate at the
        circuit, minus his own average gap across every circuit. The circuit estimate is
        shrunk toward the driver's own mean, using 5 virtual races as the prior weight, so
        drivers with few visits are pulled toward zero affinity.</li>
      <li><strong>Sign convention</strong>: negative (green) = the driver does better against
        his teammate at this circuit than his own average; positive (red) = worse. Because
        each row is measured against that driver's own average, a row mixes green and red
        even for a driver who beats his teammate everywhere.</li>
      <li><strong>Confidence</strong>: fraction of the posterior from data vs prior
        (<code>n_obs / (n_obs + 5)</code>). Values below 0.17 (one race) are prior-dominated.</li>
      <li><strong>Filter</strong>: cells shown only when <code>n_obs ≥ 2</code> (two or more
        races at the circuit). Single-race visits are excluded as unreliable.</li>
    </ul>
    <p className="mt-3">
      Drivers are sorted by their overall gap to their teammates, biggest margin first.
      Circuits are sorted alphabetically. Empty cells indicate fewer than two race visits.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_driver_circuit_affinity</code> (column{' '}
      <code>affinity_vs_driver_mean_s</code>). Pools every season in the data, 2018–2025.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/driver-circuit-affinity`
