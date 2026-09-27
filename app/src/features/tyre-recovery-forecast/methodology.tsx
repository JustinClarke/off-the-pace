import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      The recovery forecast analyses post-cliff tyre behaviour: after the degradation cliff onset
      has been passed, does the tyre show any pace recovery when the driver lifts off?
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Recovery rate</strong>: fraction of post-cliff laps where the driver's
        next two laps were, on average, faster relative to the field than this one
        (<code>recovery_flag = true</code>), by any margin. About 58–64% by compound; pure
        lap-to-lap noise would put it near 50%.</li>
      <li><strong>Avg recovery probability</strong>: a fixed formula, not a fitted model: a
        logistic curve in the surface/bulk ratio (50% at a ratio of 0.5), shrunk the further
        past the cliff the lap is. The table shows its average per compound.</li>
      <li><strong>Surface/bulk ratio</strong>: how much of the recent push load is fresh
        (surface, ~3-lap memory) against longer-lived (bulk, ~5-lap memory), each scaled so a
        steady push reads 0.5. It tops out at about 0.61, when all the push came on the current
        lap. Below 0.35 is labelled bulk-driven (hard to recover); everything above is mixed.
        There is no surface-driven label: its old 0.65 threshold could never be reached.</li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>int_tyre_surface_vs_bulk_decoupling</code>. All seasons, post-cliff laps only.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/tyre-recovery-forecast`
