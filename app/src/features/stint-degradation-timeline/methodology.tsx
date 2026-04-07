import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      The degradation timeline shows how much pace a tyre compound loses relative to fresh rubber,
      averaged across all stints run in the selected race.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Pace loss curve</strong>: the average <code>expected_compound_pace_s</code>
        across all clean stints of that compound the cumulative seconds lost vs lap 1 of the stint.</li>
      <li><strong>Shaded band</strong>: ±1 standard deviation across stints. A wide band means
        drivers were managing their tyres very differently (fuel load strategy, push vs save).</li>
      <li><strong>Cliff onset</strong>: the pre-fit lap count at which the degradation model
        expects exponential onset. Taken from <code>dim_compounds_season</code>.</li>
    </ul>
    <p className="mt-3">
      Safety car, in-lap, out-lap, and wet laps are excluded. Only <code>normal</code> and{' '}
      <code>clean_cliff</code> anomaly classes are included to suppress strategy artefacts.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>fct_cliff_prediction_features</code>. Single race view.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/stint-degradation-timeline`
