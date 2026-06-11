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
      Balanced teams sit within ±0.15s of zero.
    </p>
    <p className="mt-2">
      The effect was most prominent in the turbo-hybrid era when engine manufacturers could
      publish separate qualifying and race engine maps. It persists today as an aerodynamic
      signature: high-downforce qualifying setup vs lower-drag race trim.
    </p>
  </>
)
