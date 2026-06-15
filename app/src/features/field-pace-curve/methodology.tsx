export const methodologyContent = (
  <>
    <p>
      The field pace curve shows the trimmed field average lap time as it evolves
      over race distance combining fuel-load drop, tyre degradation, and track
      rubbering-in into a single reference baseline.
    </p>
    <ul className="list-disc pl-4 mt-3 space-y-1">
      <li><strong>Smoothed curve</strong>: LOWESS smoothed field pace. Suppresses
        outlier laps from safety cars, pit entries, and stint boundaries. This is the
        primary reference for "what did the field actually run this lap?"</li>
      <li><strong>Raw trimmed mean</strong>: 20th–80th percentile lap time across all
        eligible cars per lap. The ribbon between the two series shows where smoothing
        diverges from the raw data wide ribbon = noisy lap (few cars, spread strategy).</li>
      <li><strong>Low-sample laps</strong>: laps with fewer than 4 eligible cars
        (pit windows, early laps) are flagged and should be interpreted with caution.</li>
    </ul>
    <p className="mt-3">
      The fuel-corrected rate of change of this curve is used as the
      <code> base_track_pace_s</code> input in the seven-term decomposition.
    </p>
    <p className="mt-3 text-muted/70">
      Source: <code>int_field_pace_curve</code>. Single race view.
    </p>
  </>
)

export const methodologyHref = 'https://offthepace.mintlify.app/reference/models/int/int_field_pace_curve'
