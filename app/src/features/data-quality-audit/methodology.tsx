import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      The data quality audit summarises, for each race in the selected season, how many laps
      passed the pipeline's usability gate and the breakdown of excluded lap types.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Usable %</strong>: fraction of laps flagged <code>usable_for_modelling = true</code>.
        A lap is usable when it is not a safety car / VSC period, not an out-lap or in-lap,
        not rain-affected, and does not carry a major anomaly flag.</li>
      <li><strong>Neutralised</strong>: laps under safety car or virtual safety car
        (<code>correction_class = 'neutralisation'</code>). Pace is unrepresentative excluded
        from degradation and skill models.</li>
      <li><strong>Rain</strong>: laps where wet weather was detected. Degradation behaviour
        is qualitatively different and excluded from dry-compound models.</li>
      <li><strong>Out / In laps</strong>: the lap immediately after a pit stop (cold tyres) and
        the lap into the pits (lift-and-coast). Both excluded from degradation slopes.</li>
      <li><strong>Anomalies</strong>: laps with <code>anomaly_class != 'normal'</code>  
        mechanical events, mistakes, or clean cliff detections that carry special handling.</li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>int_lap_anomaly_flags</code>. Full season view.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/data-quality-audit`
