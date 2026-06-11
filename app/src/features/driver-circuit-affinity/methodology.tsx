import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Driver circuit affinity measures how much faster or slower a driver tends to be at a
      specific circuit, relative to their own season-average pace, after removing constructor
      and field effects.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Shrunk affinity</strong>: Bayesian posterior mean pulling the raw observed
        circuit delta toward the driver's global mean, using 5 virtual races as a prior weight.
        Drivers with fewer observations are shrunk more aggressively toward neutral.</li>
      <li><strong>Sign convention</strong>: negative = faster than driver average at that circuit
        (green), positive = slower (red). Same as driver skill residual.</li>
      <li><strong>Confidence</strong>: fraction of the posterior from data vs prior
        (<code>n_obs / (n_obs + 5)</code>). Values below 0.17 (one race) are prior-dominated.</li>
      <li><strong>Filter</strong>: cells shown only when <code>n_obs ≥ 2</code> (two or more
        races at the circuit). Single-race visits are excluded as unreliable.</li>
    </ul>
    <p className="mt-3">
      Drivers are sorted fastest-to-slowest by median affinity across circuits.
      Circuits are sorted alphabetically. Empty cells indicate fewer than two race visits.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_driver_circuit_affinity</code>. All seasons 2018–2024.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/driver-circuit-affinity`
