export const methodologyContent = (
  <>
    <p>
      This heatmap shows how each constructor over- or under-performs at specific circuits
      relative to their own season average the so-called circuit × constructor interaction term.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Interaction term</strong>: the deviation of the constructor's race-average pace
        from their own season mean at a given circuit, estimated using exponentially weighted
        smoothing and Bayesian shrinkage toward zero (prior weight = 3 races).</li>
      <li><strong>Sign convention</strong>: negative = constructor outperforms their season average
        at that circuit (green), positive = underperforms (red). Ferrari at Monza, for instance,
        typically shows a negative (favorable) interaction due to their low-drag setup.</li>
      <li><strong>Average shown</strong>: cells display the multi-season average of the race-level
        interaction, requiring at least 2 races at the circuit to appear.</li>
    </ul>
    <p className="mt-3">
      Constructors are sorted by overall average interaction (lowest first). Circuits
      are sorted alphabetically. Empty cells indicate fewer than 2 race visits.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_circuit_x_constructor_interaction</code>. All seasons 2018–2024.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/reference/models/int/int_circuit_x_constructor_interaction'
