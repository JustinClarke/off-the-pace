import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/race-control`

export const methodologyContent = (
  <div className="space-y-3 text-sm text-muted">
    <p>
      <strong className="text-[rgb(var(--color-text))]">The timeline is a record, not a
      forecast.</strong> Each lap&apos;s status comes from the FIA track-status channel carried
      through <code className="text-xs">stg_laps</code> into{' '}
      <code className="text-xs">int_stint_geometry</code>, collapsed to one row per (race, lap).
      A lap is marked under caution if any car&apos;s lap carried that status code, which is the
      right reading when a deployment lands mid-lap. Contiguous laps are merged into one bar, so
      two deployments with no green lap between them read as a single window: against the
      event log in <code className="text-xs">stg_track_status</code> this reconstructs 129
      safety-car windows from 137 logged onsets over 2018–2025, agreeing exactly on 88 of the 98
      races that have safety-car laps.
    </p>
    <p>
      <strong className="text-[rgb(var(--color-text))]">Why there is no &ldquo;chance of a safety
      car at this circuit&rdquo;.</strong> It is the number people ask for and the one this
      dataset cannot support. Across 173 races (2018–2025) at 36 circuits the warehouse holds
      about 4.8 races per circuit. A one-way variance decomposition of the per-race caution rate
      grouped by circuit puts the between-circuit share at{' '}
      <strong className="text-[rgb(var(--color-text))]">0.000</strong> for &ldquo;did this race
      have any caution&rdquo; (the between-circuit mean square falls below the within-circuit one)
      and 0.015 for &ldquo;did this race have a safety car&rdquo;, which a permutation test puts at
      p = 0.37 — not distinguishable from zero. The naive estimator reads 0.32 and 0.27. A
      per-circuit any-caution rate at this volume carries a standard error of 20 points, and
      36 circuits of pure noise would spread about 93 points from best to worst. The observed
      spread is 100 points: ten circuits sit at exactly 100% and one at 0%. Baku had a caution in
      7 of 7 races; printing &ldquo;Baku: 100%&rdquo; would be reporting seven coin flips as a
      probability.
    </p>
    <p>
      <strong className="text-[rgb(var(--color-text))]">So the headline rate is pooled</strong> —
      every circuit, every season — and it is never shown without its denominator and a Wilson
      95% interval. The one real movement in the data is by season, not by venue, and the
      per-season table shows it rather than averaging it away.
    </p>
    <p>
      <strong className="text-[rgb(var(--color-text))]">The per-circuit strip is the shrunk rate
      only.</strong> <code className="text-xs">int_sc_hazard_history</code> carries a raw
      per-circuit hazard and an empirical-Bayes shrunk one; the raw column spans 0.000 to
      0.100 per lap and is never read into this app. The shrunk column spans 0.017 to 0.033, and
      the reason it is narrow is worth stating plainly: with a 600-lap pseudo-count, the weight a
      circuit&apos;s own history carries averages 0.20 (152 circuit-season rows, 2019–2025),
      so roughly four fifths of the value shown
      is the all-circuits pooled rate wearing a circuit&apos;s name. That is the correct answer at
      this volume, and the page prints the weight beside the number instead of letting a moving
      bar imply a circuit signal.
    </p>
    <p>
      <strong className="text-[rgb(var(--color-text))]">2018 is blank on purpose.</strong> The
      hazard model is season-lagged: the row for a circuit in season S uses races at that venue in
      seasons before S and nothing else. 2018 is the first season in the warehouse, so all 21 of
      its rows are null on every rate. That is displayed as <em>not measurable</em>, never as
      zero — a measured zero hazard and an unmeasurable one are different claims, and collapsing
      them would invent the stronger of the two. Fifteen later rows are null on the raw rate for
      the same reason (a circuit&apos;s debut season), but carry a shrunk rate, because a venue
      with no history shrinks all the way to the pooled prior.
    </p>
    <p className="text-xs">
      Sources: <code>race_caution_timeline</code> (derived from{' '}
      <code>int_stint_geometry</code>) &times; <code>int_sc_hazard_history</code> &times;{' '}
      <code>race_to_track</code>. Note that <code>fct_lap_residuals</code> carries the same three
      flag names and they are false on all 161,040 of its rows, because that mart is pre-filtered
      to green racing laps; it is not a caution source.
    </p>
  </div>
)
