import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Each bar shows the <strong>mean per-lap contribution</strong> of one causal
      factor to a driver's pace delta (lap time minus the field-pace baseline),
      averaged across all clean laps in the selected race. The five identity terms
      sum exactly to the observed pace delta:
    </p>
    <p className="mt-2 font-mono text-xs text-muted/80">
      pace_delta_s = fuel + compound + constructor + dirty_air + driver_skill
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1 text-xs">
      <li><strong>Fuel</strong>: pace penalty from carrying fuel mass (degrades lap time).</li>
      <li><strong>Compound</strong>: inherent compound pace offset vs the season median tyre.</li>
      <li><strong>Constructor</strong>: structural car pace relative to the field, OLS-estimated with CI.</li>
      <li><strong>Dirty Air</strong>: aerodynamic tax from running in another car's wake, deconfounded from driver skill.</li>
      <li><strong>Driver Skill</strong>: residual unexplained by any modelled factor negative means faster than circumstances predict.</li>
      <li><strong>Track noise</strong> (diagnostic, not part of the identity): the part of the field-pace curve the rubber and ambient fits cannot explain.</li>
    </ul>
    <p className="mt-2 text-xs text-muted/70">
      Fuel, compound, constructor and dirty air sum to <code>total_explained_s</code>;
      driver skill is the remainder. Track rubber and ambient temperature are
      already inside the field baseline, so they are not bars. The identity is in <code>int_lap_residual_decomposed.sql</code>.
    </p>
    <p className="mt-3">
      The <strong>closure badge</strong> checks the additive identity: if
      |Σ five identity terms − pace_delta_s| &lt; 1e-4, the decomposition is closed.
      The CI-enforced invariant <code>assert_additive_identity</code> runs on
      every lap in the warehouse; a non-zero gap here would indicate an export
      or aggregation bug.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>fct_lap_residuals</code>, which is built from green racing laps only-
      neutralised laps never enter it. Major-outlier laps are excluded in this query.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/lap-waterfall`

