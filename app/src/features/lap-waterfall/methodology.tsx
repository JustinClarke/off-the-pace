export const methodologyContent = (
  <>
    <p>
      Each bar shows the <strong>mean per-lap contribution</strong> of one causal
      factor to a driver's pace delta (lap time minus the field-pace baseline),
      averaged across all clean laps in the selected race. The eight terms form an
      additive identity they sum exactly to the observed pace delta:
    </p>
    <p className="mt-2 font-mono text-xs text-muted/80">
      pace_delta_s = fuel + compound + rubber + ambient + constructor + dirty_air
      + driver_skill + track_noise
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1 text-xs">
      <li><strong>Fuel</strong>: pace penalty from carrying fuel mass (degrades lap time).</li>
      <li><strong>Compound</strong>: inherent compound pace offset vs the season median tyre.</li>
      <li><strong>Rubber</strong>: tyre rubber pick-up / surface state effect across the stint.</li>
      <li><strong>Ambient</strong>: track and air temperature contribution.</li>
      <li><strong>Constructor</strong>: structural car pace relative to the field, OLS-estimated with CI.</li>
      <li><strong>Dirty Air</strong>: aerodynamic tax from running in another car's wake, deconfounded from driver skill.</li>
      <li><strong>Driver Skill</strong>: residual unexplained by any modelled factor negative means faster than circumstances predict.</li>
      <li><strong>Track noise</strong>: per-lap unexplained variance not attributable to any above term.</li>
    </ul>
    <p className="mt-2 text-xs text-muted/70">
      The first six terms sum to <code>total_explained_s</code>; the documented
      identity is in <code>int_lap_residual_decomposed.sql</code>.
    </p>
    <p className="mt-3">
      The <strong>closure badge</strong> checks the additive identity: if
      |Σ components − pace_delta_s| &lt; 1e-4, the decomposition is closed.
      The CI-enforced invariant <code>assert_additive_identity</code> runs on
      every lap in the warehouse; a non-zero gap here would indicate an export
      or aggregation bug.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>fct_lap_residuals</code>. Safety-car and major-outlier laps excluded.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/reference/models/fct/fct_lap_residuals'

