import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      Track evolution decomposes the lap-time baseline into two time-varying components:
      a linear pace trend and an ambient drift. Both are extracted from the field baseline
      and are informational; they are not terms of the five-term identity.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Pace trend</strong> (<code>rubber_component_s</code>): the change in field
        pace relative to the race mean, from one straight-line fit per race with the slope
        capped at zero. Positive means slower than the race mean (early laps); negative means
        faster (late laps). It is usually read as rubber build but also absorbs anything else
        that moves field pace steadily. Where a race has too few laps for a fit the value is
        not measured and the chart shows a gap.</li>
      <li><strong>Ambient component</strong>: the part of the remaining pace residual that
        tracks the lap's track temperature, fitted per race on track temperature only
        (humidity is not in the fit).</li>
      <li><strong>Rainfall</strong>: laps tagged with the rainfall flag are highlighted.
        Wet laps are not removed from the fit. Laps with no weather reading are neither wet nor dry.</li>
    </ul>
    <p className="mt-3 text-muted/70">
      Source: <code>int_track_evolution</code>. Single race view.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/track-evolution`
