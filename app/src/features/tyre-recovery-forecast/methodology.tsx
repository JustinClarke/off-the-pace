import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      The recovery forecast analyses post-cliff tyre behaviour: after the degradation cliff onset
      has been passed, does the tyre show any pace recovery when the driver lifts off?
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Recovery rate</strong>: fraction of post-cliff laps where the model flags
        a partial pace recovery (<code>recovery_flag = true</code>). Very high across all
        compounds (~86–89%) because the model detects any positive deviation from the cliff slope,
        however small.</li>
      <li><strong>Avg recovery probability</strong>: the model's probabilistic estimate of how
        likely a lap with the observed surface/bulk load split is to show recovery.
        This is more discriminating than the binary flag: 21–29% on average.</li>
      <li><strong>Surface/bulk ratio</strong>: the ratio of surface thermal load to bulk mechanical
        load. Values below ~0.4 are bulk-driven (compound breakdown, hard to recover);
        values above ~0.4 are mixed or surface-driven (thermal, can partially recover with
        reduced push).</li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>int_tyre_surface_vs_bulk_decoupling</code>. All seasons, post-cliff laps only.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/tyre-recovery-forecast`
