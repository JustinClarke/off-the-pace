import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/party-mode`

export const methodologyContent = (
  <>
    <p>
      Party Mode compares each constructor's <strong>qualifying structural pace</strong> against
      their <strong>race structural pace</strong> both estimated from the fixed-effects panel
      model, then differenced. A negative delta (party mode) means the team extracts more pace
      over a single lap than they sustain across a race stint.
    </p>
    <p className="mt-2">
      A positive delta (race spec) means the team's car comes into its own over a race distance
      they may lose time in qualifying but manage tyres or fuel better than rivals suggest.
      A team is labelled only when its gap is both larger than ±0.15s and clear of zero
      (the 95% CI excludes 0); otherwise the label is "no clear gap", which covers small
      real gaps and gaps too noisy to call. There is no "balanced" label: the CI was
      almost never narrow enough to support one. No delta, no label (a dash).
    </p>
    <p className="mt-2">
      <strong>Uncertainty.</strong> At race level the delta's standard error is
      √(se_quali² + se_race²) and the 95% CI is the delta ± 1.96 × SE, assuming the two
      estimates' errors are independent (different sessions' laps). The season view uses
      the races where both a qualifying and a race estimate exist (the k shown in the CSV
      as races_n): the delta is the average of the per-race deltas, and its SE is
      √(max(s², mean(se_q² + se_r²)) / k), the larger of the race-to-race spread of the
      delta and the estimation error, with a t interval on k − 1 degrees of freedom. Below
      3 races there is no season interval and no label. Until 2026-11 the season delta was
      AVG(quali) − AVG(race), which averaged different races when a race estimate was
      missing. At single-race level the SE is often wider than the ±0.15s band, which is why
      a point gap alone no longer earns a label. The two inputs also use different lap sets,
      and both come from the Structural Pace model, so this is not independent evidence of a
      team trait.
    </p>
    <p className="mt-2">
      The effect was most prominent in the turbo-hybrid era when engine manufacturers could
      publish separate qualifying and race engine maps. It persists today as an aerodynamic
      signature: high-downforce qualifying setup vs lower-drag race trim.
    </p>
  </>
)
