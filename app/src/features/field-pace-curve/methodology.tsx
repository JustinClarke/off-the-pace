import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyContent = (
  <>
    <p>
      The field pace curve shows the trimmed field average lap time as it evolves
      over race distance. Each lap time is corrected for fuel load and for the
      expected tyre compound cost (tyre cliff model) before it is averaged, so a
      downward slope is not fuel burn. The model names the remaining trend the
      rubber gradient (track rubbering-in plus anything the two corrections miss).
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Smoothed curve</strong>: 5-lap centred rolling average of the
        trimmed mean. The window never crosses a safety car, VSC or red flag lap,
        and the first two green laps after a safety car or red flag keep their own
        trimmed mean. This is the primary reference for "what did the field
        actually run this lap?"</li>
      <li><strong>Raw trimmed mean</strong>: mean corrected lap time per lap number
        after dropping the fastest 10% and slowest 10% of eligible laps (percent
        rank 0.10 to 0.90). The ribbon between the two series shows where smoothing
        diverges from the raw data wide ribbon = noisy lap (few cars, spread strategy).</li>
      <li><strong>Low-sample laps</strong>: lap numbers with fewer than 5 eligible
        laps (pit windows, early laps) are flagged and have no smoothed value.</li>
    </ul>
    <p className="mt-3">
      The smoothed curve is used directly as the
      <code> base_track_pace_s</code> input in the additive decomposition.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_field_pace_curve</code>. Single race view.
    </p>
  </>
)

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/field-pace-curve`
